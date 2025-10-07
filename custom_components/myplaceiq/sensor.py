import json
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN

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

    # AC System Sensors (Mode and State)
    for aircon_id, aircon_data in aircons.items():
        entities.extend([
            MyPlaceIQAirconSensor(
                coordinator,
                config_entry,
                aircon_id,
                aircon_data
            ),
            MyPlaceIQAirconStateSensor(
                coordinator,
                config_entry,
                aircon_id,
                aircon_data
            )
        ])

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
                    ),
                    MyPlaceIQZoneStateSensor(
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

class MyPlaceIQAirconSensor(SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """Sensor for MyPlaceIQ AC system mode."""

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data):
        super().__init__()
        self.coordinator = coordinator
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_mode"
        self._attr_name = f"{self._name}_mode".replace(" ", "_").lower()
        self._attr_icon = "mdi:air-conditioner"
        self._attr_device_class = None  # State sensor (on/off/mode)
        self._attr_state_class = None

    @property
    def state(self):
        """Return the state of the AC (mode or off)."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("Invalid or missing coordinator data for aircon state: %s", data)
            return None
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            return aircon.get("mode", "unknown") if aircon.get("isOn", False) else "off"
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for aircon state: %s", err)
            return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the AC."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("Invalid or missing coordinator data for aircon attributes: %s", data)
            return {}
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            return {
                "is_on": aircon.get("isOn", False),
                "actual_temperature": aircon.get("actualTemperature"),
                "target_temperature_heat": aircon.get("targetTemperatureHeat"),
                "target_temperature_cool": aircon.get("targetTemperatureCool"),
                "fan_speed_heat": aircon.get("fanSpeedHeat"),
                "allowed_modes": aircon.get("allowedModes", []),
                "aircon_state": aircon.get("airconState")
            }
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for aircon attributes: %s", err)
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

class MyPlaceIQAirconStateSensor(SensorEntity):
    # pylint: disable=too-many-instance-attributes
    """Sensor for MyPlaceIQ AC system on/off state."""

    def __init__(self, coordinator, config_entry, aircon_id, aircon_data):
        super().__init__()
        self.coordinator = coordinator
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_state"
        self._attr_name = f"{self._name}_state".replace(" ", "_").lower()
        self._attr_icon = "mdi:power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the on/off state of the AC."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("Invalid or missing coordinator data for aircon state: %s", data)
            return None
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            return "on" if aircon.get("isOn", False) else "off"
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for aircon state: %s", err)
            return None

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }

class MyPlaceIQZoneSensor(SensorEntity):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments, too-many-positional-args
    """Sensor for MyPlaceIQ zone temperature."""

    def __init__(self, coordinator, config_entry, zone_id, zone_data, aircon_id):
        super().__init__()
        self.coordinator = coordinator
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_temperature"
        self._attr_name = f"{self._name}_temperature".replace(" ", "_").lower()
        self._attr_icon = "mdi:thermostat"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def state(self):
        """Return the current temperature of the zone."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("Invalid or missing coordinator data for zone state: %s", data)
            return None
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            return zone.get("temperatureSensorValue")
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for zone state: %s", err)
            return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the zone."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("Invalid or missing coordinator data for zone attributes: %s", data)
            return {}
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            return {
                "is_on": zone.get("isOn", False),
                "aircon_mode": zone.get("airconMode"),
                "target_temperature_heat": zone.get("targetTemperatureHeat"),
                "target_temperature_cool": zone.get("targetTemperatureCool"),
                "zone_type": zone.get("zoneType"),
                "is_clickable": zone.get("isClickable", False)
            }
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for zone attributes: %s", err)
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

class MyPlaceIQZoneStateSensor(SensorEntity):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments, too-many-positional-args
    """Sensor for MyPlaceIQ zone on/off state."""

    def __init__(self, coordinator, config_entry, zone_id, zone_data, aircon_id):
        super().__init__()
        self.coordinator = coordinator
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_state"
        self._attr_name = f"{self._name}_state".replace(" ", "_").lower()
        self._attr_icon = "mdi:toggle-switch"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the on/off state of the zone."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("Invalid or missing coordinator data for zone state: %s", data)
            return None
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._zone_id, {})
            return "on" if zone.get("isOn", False) else "off"
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse coordinator data for zone state: %s", err)
            return None

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
