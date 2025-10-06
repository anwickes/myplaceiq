"""Climate entities for MyPlaceIQ integration."""
import logging
from typing import Dict, Any, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info, setup_entities, init_entity, perform_optimistic_update

logger = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up MyPlaceIQ climate entities from a config entry."""
    logger.debug("Setting up climate entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][entry.entry_id]["myplaceiq"]

    def create_entities(
        _hass: HomeAssistant,  # Type hint only
        config_entry,
        coordinator,
        entity_id: str,
        entity_data: Dict[str, Any],
        aircon_id: Optional[str] = None
    ) -> List[ClimateEntity]:
        """Create climate entities for aircons and zones."""
        entities = []
        if aircon_id is None:  # Aircon climate
            entities.append(MyPlaceIQClimate(
                coordinator, config_entry, myplaceiq, {
                    'entity_id': entity_id, 'entity_data': entity_data,
                    'is_zone': False
                }
            ))
        else:  # Zone climate
            entities.append(MyPlaceIQClimate(
                coordinator, config_entry, myplaceiq, {
                    'entity_id': entity_id, 'entity_data': entity_data,
                    'is_zone': True, 'aircon_id': aircon_id
                }
            ))
        return entities

    entities = setup_entities(hass, entry, coordinator, create_entities)
    async_add_entities(entities)

class MyPlaceIQClimate(ClimateEntity):
    """Representation of a MyPlaceIQ climate entity for zones or system."""
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1.0

    def __init__(
        self,
        coordinator,
        config_entry,
        myplaceiq,
        config: Dict[str, Any]
    ):
        """Initialize the climate entity."""
        super().__init__()
        init_entity(self, coordinator, myplaceiq, config_entry, config)
        self._is_zone = config['is_zone']
        self._attr_hvac_modes = (
            [HVACMode.AUTO, HVACMode.OFF] if self._is_zone else
            [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY,
             HVACMode.FAN_ONLY, HVACMode.OFF]
        )

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info({
            'config_entry_id': self._config_entry.entry_id,
            'entity_id': self._entity_id,
            'name': self._name,
            'is_zone': self._is_zone,
            'aircon_id': self._aircon_id
        })

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
        return target.get("temperatureSensorValue" if self._is_zone else "actualTemperature")

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature based on the aircon's mode."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
        mode = aircon.get("mode", "heat")
        target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
        return target.get("targetTemperatureHeat" if mode == "heat" else "targetTemperatureCool")

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return HVACMode.OFF
        aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
        if self._is_zone:
            zone = body.get("zones", {}).get(self._entity_id, {})
            return HVACMode.OFF if not zone.get("isOn", False) else HVACMode.AUTO
        return (
            HVACMode.OFF if not aircon.get("isOn", False) else
            HVACMode.HEAT if aircon.get("mode") == "heat" else
            HVACMode.COOL if aircon.get("mode") == "cool" else
            HVACMode.DRY if aircon.get("mode") == "dry" else
            HVACMode.FAN_ONLY if aircon.get("mode") == "fan" else
            HVACMode.OFF
        )

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return

        aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
        mode = aircon.get("mode", "heat")
        cmd_type = (
            "SetZoneHeatTemperature" if mode == "heat" else "SetZoneCoolTemperature"
        ) if self._is_zone else (
            "SetAirconHeatTemperature" if mode == "heat" else "SetAirconCoolTemperature"
        )
        command = {
            "commands": [{
                "__type": cmd_type,
                "zoneId" if self._is_zone else "airconId": self._entity_id,
                "temperature": int(temperature)
            }]
        }

        perform_optimistic_update(
            self.hass, self.coordinator, {
                'entity_type': "zone" if self._is_zone else "aircon",
                'entity_id': self._entity_id,
                'attribute': "targetTemperatureHeat" if mode == "heat" else "targetTemperatureCool",
                'new_value': int(temperature)
            }
        )
        await self._myplaceiq.send_command(command)
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new HVAC mode."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return

        command = {"commands": []}
        if self._is_zone:
            if hvac_mode not in [HVACMode.AUTO, HVACMode.OFF]:
                logger.warning(
                    "Zone %s cannot set mode %s; only AUTO or OFF supported",
                    self._entity_id, hvac_mode
                )
                return
            new_state = hvac_mode == HVACMode.AUTO
            command["commands"].append({
                "__type": "SetZoneOpenClose",
                "zoneId": self._entity_id,
                "isOpen": new_state
            })
            perform_optimistic_update(
                self.hass, self.coordinator, {
                    'entity_type': "zone",
                    'entity_id': self._entity_id,
                    'attribute': "isOn",
                    'new_value': new_state
                }
            )
        else:
            if hvac_mode == HVACMode.OFF:
                command["commands"].append({
                    "__type": "SetAirconOnOff",
                    "airconId": self._entity_id,
                    "isOn": False
                })
                perform_optimistic_update(
                    self.hass, self.coordinator, {
                        'entity_type': "aircon",
                        'entity_id': self._entity_id,
                        'attribute': "isOn",
                        'new_value': False
                    }
                )
            else:
                mode_map = {
                    HVACMode.HEAT: "heat",
                    HVACMode.COOL: "cool",
                    HVACMode.DRY: "dry",
                    HVACMode.FAN_ONLY: "fan"
                }
                command["commands"].extend([
                    {
                        "__type": "SetAirconOnOff",
                        "airconId": self._entity_id,
                        "isOn": True
                    },
                    {
                        "__type": "SetAirconMode",
                        "airconId": self._entity_id,
                        "mode": mode_map.get(hvac_mode, "heat")
                    }
                ])
                perform_optimistic_update(
                    self.hass, self.coordinator, {
                        'entity_type': "aircon",
                        'entity_id': self._entity_id,
                        'attribute': "isOn",
                        'new_value': True
                    }
                )
                perform_optimistic_update(
                    self.hass, self.coordinator, {
                        'entity_type': "aircon",
                        'entity_id': self._entity_id,
                        'attribute': "mode",
                        'new_value': mode_map.get(hvac_mode, "heat")
                    }
                )

        await self._myplaceiq.send_command(command)
        self.hass.async_create_task(self.coordinator.async_request_refresh())
