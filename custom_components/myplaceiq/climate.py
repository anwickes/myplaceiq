import json
import logging
import time
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode, PRESET_NONE
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

logger = logging.getLogger(__name__)

PRESET_PRIORITY = "Priority"
PRESET_NORMAL = PRESET_NONE

# Fan speed is a whole-of-aircon setting. "auto" maps to the "MyFan"
# auto-load feature (isMyFanHeatingEnabled/isMyFanCoolingEnabled);
# the numeric modes map to a manual fanSpeedHeat/fanSpeedCool value.
# Fan speed is not controllable in dry mode at all - the official 
# app greys the control out there too, so no dry-mode command exists 
# to capture.
FAN_AUTO = "auto"

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

class MyPlaceIQClimate(CoordinatorEntity, ClimateEntity):
    # pylint: disable=too-many-instance-attributes
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def __init__(
        self,
        coordinator,
        myplaceiq,
        config_entry,
        entity_id,
        entity_data,
        is_zone,
        aircon_id=None
    ):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._myplaceiq = myplaceiq
        self._config_entry = config_entry
        self._entity_id = entity_id
        self._is_zone = is_zone
        self._aircon_id = aircon_id if is_zone else entity_id
        self._name = entity_data.get("name", "Zone" if is_zone else "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}_climate" # pylint: disable=line-too-long
        self._attr_name = f"{self._name}_climate".replace(" ", "_").lower()
        self._attr_icon = "mdi:thermostat"
        self._attr_hvac_modes = (
            [HVACMode.AUTO, HVACMode.OFF] if is_zone else
            [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]
        )
        if is_zone and entity_data.get("isPriorityZoneAllowed", False):
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
            )
            self._attr_preset_modes = [PRESET_PRIORITY, PRESET_NORMAL]
        else:
            self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_preset_modes = None

        if not is_zone:
            allowed_fan_speeds = entity_data.get("allowedFanSpeeds", 3)
            self._attr_fan_modes = [FAN_AUTO] + [
                str(speed) for speed in range(1, allowed_fan_speeds + 1)
            ]
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        self._last_known_is_on = None

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        logger.debug(
            "Coordinator update for %s at %s", self._attr_unique_id, time.strftime("%H:%M:%S"))
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_{'zone' if self._is_zone else 'aircon'}_{self._entity_id}")}, # pylint: disable=line-too-long
            "name": f"{'Zone' if self._is_zone else 'Aircon'} {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Zone" if self._is_zone else "Aircon"
        }
        if self._is_zone:
            device_info["via_device"] = (
                DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")
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
            aircon = body.get("aircons", {}).get(
                self._aircon_id if self._is_zone else self._entity_id, {})
            mode = aircon.get("mode", "heat")
            target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
            if mode == "heat":
                val = target.get("targetTemperatureHeat")
            elif mode == "cool":
                val = target.get("targetTemperatureCool")
            else:
                val = None
            return float(val) if val is not None else None
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse target temperature: %s", err)
            return None

    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for %s", self._attr_unique_id)
            return HVACMode.OFF
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(
                self._aircon_id if self._is_zone else self._entity_id, {})
            is_on = aircon.get(
                "isOn", self._last_known_is_on if self._last_known_is_on is not None else False
            )
            if is_on:
                self._last_known_is_on = is_on
            if self._is_zone:
                zone = body.get("zones", {}).get(self._entity_id, {})
                is_zone_on = zone.get("isOn", False)
                if is_zone_on:
                    self._last_known_is_on = is_zone_on
                state = HVACMode.OFF if not is_zone_on else HVACMode.AUTO
                logger.debug("Zone %s hvac_mode updated at %s: %s (isOn=%s)",
                             self._attr_unique_id, time.strftime("%H:%M:%S"), state, is_zone_on)
                return state
            state = (
                HVACMode.OFF if not is_on else
                HVACMode.HEAT if aircon.get("mode") == "heat" else
                HVACMode.COOL if aircon.get("mode") == "cool" else
                HVACMode.DRY if aircon.get("mode") == "dry" else
                HVACMode.FAN_ONLY if aircon.get("mode") == "fan" else
                HVACMode.OFF
            )
            logger.debug("Aircon %s hvac_mode updated at %s: %s (isOn=%s, mode=%s)",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), state, is_on,
                         aircon.get("mode", "missing"))
            return state
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse HVAC mode for %s: %s", self._attr_unique_id, err)
            return HVACMode.OFF

    @property
    def preset_mode(self):
        """Return the current preset mode for zone entities."""
        if not self._is_zone or self._attr_preset_modes is None:
            return None
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return PRESET_NORMAL
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._entity_id, {})
            is_priority = zone.get("isPriorityZone", False)
            preset = PRESET_PRIORITY if is_priority else PRESET_NORMAL
            logger.debug("Zone %s preset_mode: %s (isPriorityZone=%s)",
                         self._attr_unique_id, preset, is_priority)
            return preset
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse preset mode for %s: %s", self._attr_unique_id, err)
            return PRESET_NORMAL

    @property
    def fan_mode(self):
        """Return the current fan mode (aircon-level only)."""
        if self._is_zone:
            return None
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._entity_id, {})
            mode = aircon.get("mode", "heat")
            is_auto = (
                aircon.get("isMyFanCoolingEnabled", False) if mode == "cool"
                else aircon.get("isMyFanHeatingEnabled", False)
            )
            if is_auto:
                return FAN_AUTO
            speed = aircon.get("fanSpeedCool" if mode == "cool" else "fanSpeedHeat")
            return str(speed) if speed is not None else None
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse fan mode for %s: %s", self._attr_unique_id, err)
            return None

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode (aircon-level only): 'auto', '1', '2', or '3'."""
        if self._is_zone:
            logger.warning("Zone %s does not support fan mode", self._entity_id)
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])
        aircon = body.get("aircons", {}).get(self._entity_id, {})
        mode = aircon.get("mode", "heat")
        is_cool = mode == "cool"

        commands = []
        if fan_mode == FAN_AUTO:
            commands.append({
                "commands": [{
                    "__type": "SetMyFanCoolingEnabled" if is_cool else "SetMyFanHeatingEnabled",
                    "airconId": self._entity_id,
                    "isEnabled": True
                }]
            })
            aircon["isMyFanCoolingEnabled" if is_cool else "isMyFanHeatingEnabled"] = True
        else:
            try:
                speed = int(fan_mode)
            except ValueError:
                logger.warning("Unsupported fan mode %s for %s", fan_mode, self._entity_id)
                return
            # MyFan has to be explicitly switched off first, as its own
            # command, before the hub will accept a manual speed - it does
            # not happen implicitly just because a speed was sent.
            commands.append({
                "commands": [{
                    "__type": "SetMyFanCoolingEnabled" if is_cool else "SetMyFanHeatingEnabled",
                    "airconId": self._entity_id,
                    "isEnabled": False
                }]
            })
            commands.append({
                "commands": [{
                    "__type": "SetAirconCoolFanSpeed" if is_cool else "SetAirconHeatFanSpeed",
                    "airconId": self._entity_id,
                    "fanSpeed": speed
                }]
            })
            aircon["isMyFanCoolingEnabled" if is_cool else "isMyFanHeatingEnabled"] = False
            aircon["fanSpeedCool" if is_cool else "fanSpeedHeat"] = speed

        # Optimistic update
        body["aircons"][self._entity_id] = aircon
        self.coordinator.data["body"] = json.dumps(body)
        logger.debug("Optimistic update for %s: set fan_mode to %s", self._attr_name, fan_mode)
        self.async_write_ha_state()

        for command in commands:
            await self._myplaceiq.send_command(command)
        await self.coordinator.async_request_refresh_after_command()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])
        aircon = body.get("aircons", {}).get(
            self._aircon_id if self._is_zone else self._entity_id, {})
        mode = aircon.get("mode", "heat")

        command = {
            "commands": [{
                "__type": (
                    "SetZoneHeatTemperature" if mode == "heat" else "SetZoneCoolTemperature"
                ) if self._is_zone else (
                    "SetAirconHeatTemperature" if mode == "heat" else "SetAirconCoolTemperature"
                ),
                "zoneId" if self._is_zone else "airconId": self._entity_id,
                "temperature": float((round(temperature * 2))/2.0)
            }]
        }

        # Optimistic update
        target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
        if mode == "heat":
            target["targetTemperatureHeat"] = float((round(temperature * 2))/2.0)
        elif mode == "cool":
            target["targetTemperatureCool"] = float((round(temperature * 2))/2.0)
        if self._is_zone:
            body["zones"][self._entity_id] = target
        else:
            body["aircons"][self._entity_id] = target
        self.coordinator.data["body"] = json.dumps(body)
        logger.debug("Optimistic update for %s: set temperature to %s",
            self._attr_name, temperature)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await self.coordinator.async_request_refresh_after_command()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])

        if self._is_zone:
            if hvac_mode not in [HVACMode.AUTO, HVACMode.OFF]:
                logger.warning(
                    "Zone %s cannot set mode %s; only AUTO or OFF supported",
                    self._entity_id, hvac_mode)
                return
            new_state = hvac_mode == HVACMode.AUTO
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
            self._last_known_is_on = new_state
        else:
            commands = []
            if hvac_mode == HVACMode.OFF:
                commands.append({
                    "__type": "SetAirconOnOff",
                    "airconId": self._entity_id,
                    "isOn": False
                })
            else:
                commands.extend([
                    {
                        "__type": "SetAirconOnOff",
                        "airconId": self._entity_id,
                        "isOn": True
                    },
                    {
                        "__type": "SetAirconMode",
                        "airconId": self._entity_id,
                        "mode": (
                            "heat" if hvac_mode == HVACMode.HEAT else
                            "cool" if hvac_mode == HVACMode.COOL else
                            "dry" if hvac_mode == HVACMode.DRY else
                            "fan"
                        )
                    }
                ])
            command = {"commands": commands}
            # Optimistic update
            aircon = body.get("aircons", {}).get(self._entity_id, {})
            aircon["isOn"] = hvac_mode != HVACMode.OFF
            self._last_known_is_on = hvac_mode != HVACMode.OFF
            if hvac_mode != HVACMode.OFF:
                aircon["mode"] = (
                    "heat" if hvac_mode == HVACMode.HEAT else
                    "cool" if hvac_mode == HVACMode.COOL else
                    "dry" if hvac_mode == HVACMode.DRY else
                    "fan"
                )
            body["aircons"][self._entity_id] = aircon

        self.coordinator.data["body"] = json.dumps(body)
        logger.debug("Optimistic update for %s: set hvac_mode to %s, isOn=%s",
                     self._attr_name, hvac_mode, self._last_known_is_on)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await self.coordinator.async_request_refresh_after_command()

    async def async_set_preset_mode(self, preset_mode):
        """Set priority preset mode for zone entities."""
        if not self._is_zone or self._attr_preset_modes is None:
            logger.warning("Preset mode not supported for %s", self._attr_unique_id)
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])

        new_priority = preset_mode == PRESET_PRIORITY
        command = {
            "commands": [{
                "__type": "SetPriorityZone",
                "zoneId": self._entity_id,
                "priorityEnabled": new_priority
            }]
        }

        # Optimistic update
        zone = body.get("zones", {}).get(self._entity_id, {})
        zone["isPriorityZone"] = new_priority
        zone["isPriorityZoneActive"] = new_priority
        body["zones"][self._entity_id] = zone
        self.coordinator.data["body"] = json.dumps(body)
        logger.debug("Optimistic update for %s: set preset_mode to %s (isPriorityZone=%s)",
                     self._attr_name, preset_mode, new_priority)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await self.coordinator.async_request_refresh_after_command()
