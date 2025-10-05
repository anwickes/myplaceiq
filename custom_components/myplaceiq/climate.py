"""Climate entities for MyPlaceIQ integration."""
import json
import logging
from typing import Dict, Any, Optional, List
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info, setup_entities

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MyPlaceIQ climate entities from a config entry."""
    logger.debug("Setting up climate entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][entry.entry_id]["myplaceiq"]

    def create_entities(hass, config_entry, coordinator, entity_id: str, entity_data: Dict[str, Any], aircon_id: Optional[str] = None) -> List[ClimateEntity]:
        """Create climate entities for aircons and zones."""
        entities = []
        if aircon_id is None:  # Aircon climate
            entities.append(MyPlaceIQClimate(
                coordinator, myplaceiq, config_entry, entity_id, entity_data, False
            ))
        else:  # Zone climate
            entities.append(MyPlaceIQClimate(
                coordinator, myplaceiq, config_entry, entity_id, entity_data, True, aircon_id
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
        myplaceiq,
        config_entry,
        entity_id: str,
        entity_data: Dict[str, Any],
        is_zone: bool = False,
        aircon_id: Optional[str] = None
    ):
        """Initialize the climate entity."""
        super().__init__()
        self.coordinator = coordinator
        self._myplaceiq = myplaceiq
        self._config_entry = config_entry
        self._entity_id = entity_id
        self._is_zone = is_zone
        self._aircon_id = aircon_id if is_zone else entity_id
        self._name = entity_data.get("name", "Zone" if is_zone else "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}_climate"
        self._attr_name = f"{self._name}_climate".replace(" ", "_").lower()
        self._attr_icon = "mdi:thermostat"
        self._attr_hvac_modes = (
            [HVACMode.AUTO, HVACMode.OFF] if is_zone else
            [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]
        )

    def _perform_optimistic_update(self, body: Dict[str, Any], attribute: str, new_value: Any) -> None:
        """Perform an optimistic update to coordinator.data."""
        entity_type = "zones" if self._is_zone else "aircons"
        if entity_type in body and self._entity_id in body[entity_type]:
            body[entity_type][self._entity_id][attribute] = new_value
            self.coordinator.data = {"body": json.dumps(body)}
            self.async_write_ha_state()
            logger.debug(
                "Optimistically updated %s %s %s to %s",
                entity_type[:-1], self._entity_id, attribute, new_value
            )
        else:
            logger.warning(
                "Could not perform optimistic update for %s %s %s: not found in data",
                entity_type[:-1], self._entity_id, attribute
            )

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(
            self._config_entry.entry_id, self._entity_id,
            self._name, self._is_zone, self._aircon_id
        )

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

        self._perform_optimistic_update(
            body, "targetTemperatureHeat" if mode == "heat" else "targetTemperatureCool", int(temperature)
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
            self._perform_optimistic_update(body, "isOn", new_state)
        else:
            if hvac_mode == HVACMode.OFF:
                command["commands"].append({
                    "__type": "SetAirconOnOff",
                    "airconId": self._entity_id,
                    "isOn": False
                })
                self._perform_optimistic_update(body, "isOn", False)
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
                self._perform_optimistic_update(body, "isOn", True)
                self._perform_optimistic_update(body, "mode", mode_map.get(hvac_mode, "heat"))

        await self._myplaceiq.send_command(command)
        self.hass.async_create_task(self.coordinator.async_request_refresh())
