import json
import logging
import time  # Added import
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime, timezone
from .const import DOMAIN
from .energy_settings import (
    iqe_enabled,
    iqe_supported,
    set_iqe_entity_visibility,
)

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ sensor entities from a config entry."""
    logger.debug("Setting up sensor entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
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

    # AC System Sensors (Mode, State, and Priority Zone)
    for aircon_id, aircon_data in aircons.items():
        entities.extend([
            MyPlaceIQAirconSensor(
                coordinator,
                config_entry,
                aircon_id,
                aircon_data
            ),
            MyPlaceIQPriorityZoneSensor(
                coordinator,
                config_entry,
                aircon_id,
                aircon_data,
                zones
            ),
            MyPlaceIQActiveControlZoneSensor(
                coordinator,
                config_entry,
                aircon_id,
                aircon_data
            ),
        ])

    iqe_status_entities = []
    iqe_status_added = False
    if iqe_enabled(body):
        iqe_status_entities = _iqe_status_sensors(
            coordinator, config_entry, aircons
        )
        entities.extend(iqe_status_entities)
        iqe_status_added = bool(iqe_status_entities)
    if iqe_supported(body):
        def _add_status_when_enabled():
            nonlocal iqe_status_added
            try:
                updated_body = json.loads(coordinator.data["body"])
            except (KeyError, TypeError, ValueError) as err:
                logger.error("Failed to parse coordinator data for IQe status: %s", err)
                return
            enabled = iqe_enabled(updated_body)
            if enabled and not iqe_status_added:
                status_sensors = _iqe_status_sensors(
                    coordinator, config_entry, updated_body.get("aircons", {})
                )
                if status_sensors:
                    iqe_status_entities.extend(status_sensors)
                    async_add_entities(status_sensors)
                    iqe_status_added = True
                    logger.debug("Added %d IQe status sensors", len(status_sensors))
            for status_sensor in iqe_status_entities:
                set_iqe_entity_visibility(hass, status_sensor, enabled)

        config_entry.async_on_unload(
            coordinator.async_add_listener(_add_status_when_enabled)
        )

    # Zone Sensors (Temperature and State)
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if zone_data and zone_data.get("isVisible", False):
                entities.extend([
                    MyPlaceIQZoneSensor(
                        coordinator,
                        config_entry,
                        zone_id,
                        zone_data,
                        aircon_id
                    )
                ])

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d sensor entities", len(entities))
    else:
        logger.warning("No sensor entities created; check data structure")


def _iqe_status_sensors(coordinator, config_entry, aircons):
    """Build IQe status sensors for aircons that report IQe status."""
    return [
        MyPlaceIQIQeStatusSensor(coordinator, config_entry, aircon_id, aircon_data)
        for aircon_id, aircon_data in aircons.items()
        if "smartAirInfo" in aircon_data
    ]


class MyPlaceIQAirconSensor(CoordinatorEntity, SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """Sensor for MyPlaceIQ AC system mode."""

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data):
        super().__init__(coordinator)
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_mode"
        self._attr_has_entity_name = True
        self._attr_name = "HVAC Mode"
        self._attr_icon = "mdi:air-conditioner"
        self._attr_device_class = None
        self._attr_state_class = None
        self._last_known_is_on = None

    @property
    def state(self):
        """Return the state of the AC (mode or off)."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for aircon %s", self._attr_unique_id)
            return None
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            is_on = aircon.get("isOn",
                self._last_known_is_on if self._last_known_is_on is not None else False)
            if is_on:
                self._last_known_is_on = is_on
            state = aircon.get("mode", "unknown") if is_on else "off"
            logger.debug("Aircon %s mode state updated at %s: %s (isOn=%s, mode=%s)",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), state, is_on,
                         aircon.get("mode", "missing"))
            return state
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for aircon %s: %s",
                self._attr_unique_id, err)
            return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the AC."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for aircon attributes %s", self._attr_unique_id)
            return {}
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            attributes = {
                "is_on": aircon.get("isOn",
                    self._last_known_is_on if self._last_known_is_on is not None else False),
                "actual_temperature": aircon.get("actualTemperature"),
                "target_temperature_heat": aircon.get("targetTemperatureHeat"),
                "target_temperature_cool": aircon.get("targetTemperatureCool"),
                "fan_speed_heat": aircon.get("fanSpeedHeat"),
                "allowed_modes": aircon.get("allowedModes", []),
                "aircon_state": aircon.get("airconState")
            }
            logger.debug("Aircon %s attributes updated at %s: %s",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), attributes)
            return attributes
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for aircon attributes %s: %s",
                self._attr_unique_id, err)
            return {}

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }

class MyPlaceIQActiveControlZoneSensor(CoordinatorEntity, SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """Sensor reporting which zone is currently driving the aircon.

    With manual priority this is the zone the user chose; with QTemp it is
    the zone the hub itself picked as needing the most heating or cooling,
    which changes on its own. The hub reports it as activeControlZoneName.
    """

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data):
        super().__init__(coordinator)
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_active_control_zone"
        self._attr_name = "Active Control Zone"
        self._attr_icon = "mdi:thermometer-auto"

    def _get_aircon(self):
        """Return this aircon's current data, or None if unavailable."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None
        try:
            body = json.loads(data["body"])
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for active control zone %s: %s",
                         self._aircon_id, err)
            return None
        return body.get("aircons", {}).get(self._aircon_id)

    @property
    def state(self):
        """Return the name of the zone currently in control."""
        aircon = self._get_aircon()
        if not aircon:
            return None
        return aircon.get("activeControlZoneName") or None

    @property
    def extra_state_attributes(self):
        """Return how that zone was chosen."""
        aircon = self._get_aircon()
        if not aircon:
            return {}
        return {
            "zone_operation": aircon.get("airconSettings", {}).get("zoneOperation"),
            "zone_id": aircon.get("priorityZoneId"),
        }

    @property
    def device_info(self):
        """Return device information - attach to the parent aircon device."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }

def _epoch_ms_to_datetime(value):
    """Convert the hub's epoch-millisecond timestamps (0 = unset) to an aware datetime."""
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


class MyPlaceIQIQeStatusSensor(CoordinatorEntity, SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """What IQe is doing or planning to do for an aircon.

    State is the hub's run status (e.g. "none", "scheduled"). The attributes
    carry the planned action and when it starts and stops, plus the
    IQe configuration. Enabled weekdays can be changed from Home Assistant;
    usage mode remains read-only.
    """

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data):
        super().__init__(coordinator)
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_iqe_status"
        self._attr_name = "IQe Status"
        self._attr_icon = "mdi:solar-power-variant"
        self._attr_entity_registry_visible_default = iqe_enabled(
            json.loads(coordinator.data["body"])
        )

    def _get_data(self):
        """Return (smartAirInfo, energySettings) or (None, None)."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None, None
        try:
            body = json.loads(data["body"])
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for IQe status %s: %s",
                         self._aircon_id, err)
            return None, None
        info = body.get("aircons", {}).get(self._aircon_id, {}).get("smartAirInfo")
        return info, body.get("energySettings", {})

    @property
    def state(self):
        """Return the hub's IQe run status."""
        info, _ = self._get_data()
        return info.get("smartAirRunStatus") if info else None

    @property
    def extra_state_attributes(self):
        """Return the planned action, its schedule and the read-only IQe settings."""
        info, settings = self._get_data()
        if not info:
            return {}
        return {
            "planned_action": info.get("smartAirPlannedAction"),
            "is_active": info.get("isSmartAirActive"),
            "type": info.get("smartAirType"),
            "start": _epoch_ms_to_datetime(info.get("smartAirStartEpochUtc")),
            "stop": _epoch_ms_to_datetime(info.get("smartAirStopEpochUtc")),
            "house_power_source": info.get("housePowerSource", []),
            "usage_mode": settings.get("smartAirUsageMode"),
            "enabled_days": settings.get("smartAirEnabledDays"),
        }

    @property
    def device_info(self):
        """Return device information - attach to the parent aircon device."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }

class MyPlaceIQPriorityZoneSensor(CoordinatorEntity, SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """Sensor reporting how many priority zones are currently active for an aircon system.

    State: integer count of active priority zones (0 = none active).
    Attributes: per-zone name -> bool map, so automations can inspect individual zones.
    """

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data, zones):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        super().__init__(coordinator)
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_priority_zone"
        self._attr_name = "Priority Zones"
        self._attr_icon = "mdi:star-circle"
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT

    def _get_priority_zone_map(self, body):
        """Return {zone_name: isPriorityZoneActive} for all priority-type zones."""
        zones = body.get("zones", {})
        return {
            zone_data.get("name", zone_id): zone_data.get("isPriorityZone", False)
            for zone_id, zone_data in zones.items()
            if zone_data.get("zoneType") == "priority" or zone_data.get("isPriorityZoneAllowed", False)
        }

    @property
    def state(self):
        """Return the count of currently active priority zones."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for priority zone sensor %s",
                         self._attr_unique_id)
            return None
        try:
            body = json.loads(data["body"])
            priority_map = self._get_priority_zone_map(body)
            active_count = sum(1 for active in priority_map.values() if active)
            logger.debug("Priority zone count for aircon %s: %d / %d",
                         self._aircon_id, active_count, len(priority_map))
            return active_count
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse priority zone data for aircon %s: %s",
                         self._aircon_id, err)
            return None

    @property
    def extra_state_attributes(self):
        """Return per-zone priority state and the names of all active priority zones."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return {}
        try:
            body = json.loads(data["body"])
            priority_map = self._get_priority_zone_map(body)
            active_zones = [name for name, active in priority_map.items() if active]
            return {
                "priority_zones": priority_map,        # {zone_name: bool} — all priority zones
                "active_priority_zones": active_zones,  # [zone_name, ...] — only active ones
            }
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse priority zone attributes for aircon %s: %s",
                         self._aircon_id, err)
            return {}

    @property
    def device_info(self):
        """Return device information — attach to the parent aircon device."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }


class MyPlaceIQZoneSensor(CoordinatorEntity, SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """Sensor for MyPlaceIQ zone temperature."""

    def __init__(self, coordinator, config_entry, zone_id, zone_data, aircon_id):
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-positional-arguments
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_temperature"
        self._attr_has_entity_name = True
        self._attr_name = "HVAC Temperature"
        self._attr_icon = "mdi:thermostat"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def state(self):
        """Return the current temperature of the zone."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for zone temperature %s", self._attr_unique_id)
            return None
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            state = zone.get("temperatureSensorValue")
            logger.debug("Zone %s temperature state updated at %s: %s",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), state)
            return state
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for zone temperature %s: %s",
                self._attr_unique_id, err)
            return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the zone."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for zone attributes %s", self._attr_unique_id)
            return {}
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            attributes = {
                "is_on": zone.get("isOn", False),
                "aircon_mode": zone.get("airconMode"),
                "target_temperature_heat": zone.get("targetTemperatureHeat"),
                "target_temperature_cool": zone.get("targetTemperatureCool"),
                "zone_type": zone.get("zoneType"),
                "is_clickable": zone.get("isClickable", False),
                "is_priority_zone": zone.get("isPriorityZone", False),
                "is_priority_zone_active": zone.get("isPriorityZoneActive", False),
            }
            logger.debug("Zone %s attributes updated at %s: %s",
                         self._attr_unique_id, time.strftime("%H:%M:%S"), attributes)
            return attributes
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for zone attributes %s: %s",
                self._attr_unique_id, err)
            return {}

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_zone_{self._zone_id}")},
            "name": f"Zone {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Zone",
            "via_device": (DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")
        }
