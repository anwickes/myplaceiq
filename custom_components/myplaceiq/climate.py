import json
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

logger = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up MyPlaceIQ climate entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][entry.entry_id]["myplaceiq"]
    data = coordinator.data

    if not isinstance(data, dict) or not data or "body" not in data:
        logger.error("Invalid or missing coordinator data: %s", data)
        return

    try:
        body = json.loads(data["body"])
    except (json.JSONDecodeError, TypeError) as err:
        logger.error("Failed to parse coordinator data body: %s", err)
        return

    aircons = body.get("aircons", {})
    zones = body.get("zones", {})

    entities = []
    # System climate entity
    for aircon_id, aircon_data in aircons.items():
        entities.append(
            MyPlaceIQClimate(
                coordinator=coordinator,
                myplaceiq=myplaceiq,
                config_entry=entry,
                entity_id=aircon_id,
                entity_data=aircon_data,
                is_zone=False
            )
        )
    # Zone climate entities
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if zone_data and zone_data.get("isVisible", False):
                entities.append(
                    MyPlaceIQClimate(
                        coordinator=coordinator,
                        myplaceiq=myplaceiq,
                        config_entry=entry,
                        entity_id=zone_id,
                        entity_data=zone_data,
                        is_zone=True,
                        aircon_id=aircon_id
                    )
                )

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d climate entities", len(entities))
    else:
        logger.warning("No climate entities created; check data structure")

class MyPlaceIQClimate(ClimateEntity):
    """Representation of a MyPlaceIQ climate entity for zones or system."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16  # Adjust based on MyPlaceIQ specs
    _attr_max_temp = 30  # Adjust based on MyPlaceIQ specs

    def __init__(self, coordinator, myplaceiq, config_entry, entity_id, entity_data, is_zone, aircon_id=None):
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
            [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF] if is_zone else
            [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]
        )

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_{'zone' if self._is_zone else 'aircon'}_{self._entity_id}")},
            "name": f"{'Zone' if self._is_zone else 'Aircon'} {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Zone" if self._is_zone else "Aircon"
        }
        if self._is_zone:
            device_info["via_device"] = (DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")
        return device_info

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self):
        """Return the current temperature."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None
        try:
            body = json.loads(data["body"])
            target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
            return target.get("temperatureSensorValue" if self._is_zone else "actualTemperature")
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse current temperature: %s", err)
            return None

    @property
    def target_temperature(self):
        """Return the target temperature based on the aircon's mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
            mode = aircon.get("mode", "off")
            target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
            if mode == "heat":
                return target.get("targetTemperatureHeat")
            elif mode == "cool":
                return target.get("targetTemperatureCool")
            return None
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse target temperature: %s", err)
            return None

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return HVACMode.OFF
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
            if self._is_zone:
                zone = body.get("zones", {}).get(self._entity_id, {})
                return HVACMode.OFF if not zone.get("isOn", False) else (
                    HVACMode.HEAT if aircon.get("mode") == "heat" else
                    HVACMode.COOL if aircon.get("mode") == "cool" else
                    HVACMode.DRY if aircon.get("mode") == "dry" else
                    HVACMode.FAN_ONLY if aircon.get("mode") == "fan" else
                    HVACMode.OFF
                )
            else:
                return (
                    HVACMode.OFF if not aircon.get("isOn", False) else
                    HVACMode.HEAT if aircon.get("mode") == "heat" else
                    HVACMode.COOL if aircon.get("mode") == "cool" else
                    HVACMode.DRY if aircon.get("mode") == "dry" else
                    HVACMode.FAN_ONLY if aircon.get("mode") == "fan" else
                    HVACMode.OFF
                )
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse HVAC mode: %s", err)
            return HVACMode.OFF

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])
        aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
        mode = aircon.get("mode", "heat")  # Default to heat if mode is unset

        command = {
            "commands": [{
                "__type": (
                    "SetZoneHeatTemperature" if mode == "heat" else "SetZoneCoolTemperature"
                ) if self._is_zone else (
                    "SetAirconHeatTemperature" if mode == "heat" else "SetAirconCoolTemperature"
                ),
                "zoneId" if self._is_zone else "airconId": self._entity_id,
                "temperature": float(temperature)
            }]
        }

        # Optimistic update
        target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
        if mode == "heat":
            target["targetTemperatureHeat"] = temperature
        elif mode == "cool":
            target["targetTemperatureCool"] = temperature
        if self._is_zone:
            body["zones"][self._entity_id] = target
        else:
            body["aircons"][self._entity_id] = target
        self.coordinator.data["body"] = json.dumps(body)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])

        if self._is_zone:
            # Zones use SetZoneOpenClose for OFF, inherit aircon mode
            if hvac_mode not in [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]:
                logger.warning("Zone %s cannot set mode %s; only OFF is supported", self._entity_id, hvac_mode)
                return
            new_state = hvac_mode != HVACMode.OFF
            command = {
                "commands": [{
                    "__type": "SetZoneOpenClose",
                    "zoneId": self._entity_id,
                    "isOpen": new_state
                }]
            }
            # Optimistic update
            zone = body.get("zones", {}).get(self._entity_id, {})
            zone["isOn"] = new_state
            body["zones"][self._entity_id] = zone
        else:
            # System uses SetAirconMode or SetAirconOnOff
            command = {
                "commands": [{
                    "__type": "SetAirconOnOff" if hvac_mode == HVACMode.OFF else "SetAirconMode",
                    "airconId": self._entity_id,
                    "isOn" if hvac_mode == HVACMode.OFF else "mode": (
                        False if hvac_mode == HVACMode.OFF else
                        "heat" if hvac_mode == HVACMode.HEAT else
                        "cool" if hvac_mode == HVACMode.COOL else
                        "dry" if hvac_mode == HVACMode.DRY else
                        "fan"
                    )
                }]
            }
            # Optimistic update
            aircon = body.get("aircons", {}).get(self._entity_id, {})
            aircon["isOn"] = hvac_mode != HVACMode.OFF
            if hvac_mode != HVACMode.OFF:
                aircon["mode"] = (
                    "heat" if hvac_mode == HVACMode.HEAT else
                    "cool" if hvac_mode == HVACMode.COOL else
                    "dry" if hvac_mode == HVACMode.DRY else
                    "fan"
                )
            body["aircons"][self._entity_id] = aircon

        self.coordinator.data["body"] = json.dumps(body)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await self.coordinator.async_request_refresh()