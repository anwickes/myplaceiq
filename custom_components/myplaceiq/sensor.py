"""Sensor entities for MyPlaceIQ integration."""
import json
import logging
from typing import Dict, Any, Optional
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ sensor entities from a config entry."""
    logger.debug("Setting up sensor entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    body = parse_coordinator_data(coordinator.data)
    if not body:
        return

    aircons = body.get("aircons", {})
    zones = body.get("zones", {})
    entities = []

    for aircon_id, aircon_data in aircons.items():
        entities.extend([
            MyPlaceIQAirconSensor(coordinator, config_entry, aircon_id, aircon_data),
            MyPlaceIQAirconStateSensor(coordinator, config_entry, aircon_id, aircon_data)
        ])
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if zone_data and zone_data.get("isVisible", False):
                entities.extend([
                    MyPlaceIQZoneSensor(coordinator, config_entry, zone_id, zone_data, aircon_id),
                    MyPlaceIQZoneStateSensor(coordinator, config_entry, zone_id, zone_data, aircon_id)
                ])

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d sensor entities", len(entities))
    else:
        logger.warning("No sensor entities created; check data structure")

class MyPlaceIQAirconSensor(SensorEntity):
    """Sensor for MyPlaceIQ AC system mode."""

    def __init__(self, coordinator, config_entry, aircon_id: str, aircon_data: Dict[str, Any]):
        """Initialize the aircon mode sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_mode"
        self._attr_name = f"{self._name}_mode".replace(" ", "_").lower()
        self._attr_icon = "mdi:air-conditioner"

    @property
    def state(self) -> Optional[str]:
        """Return the state of the AC (mode or off)."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        aircon = body.get("aircons", {}).get(self._aircon_id, {})
        return aircon.get("mode", "unknown") if aircon.get("isOn", False) else "off"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the AC."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return {}
        aircon = body.get("aircons", {}).get(self._aircon_id, {})
        return {
            "is_on": aircon.get("isOn", False),
            "actual_temperature": aircon.get("actualTemperature"),
            "target_temperature_heat": aircon.get("targetTemperatureHeat"),
            "target_temperature_cool": aircon.get("targetTemperatureCool")
        }

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(self._config_entry.entry_id, self._aircon_id, self._name, False)

class MyPlaceIQAirconStateSensor(SensorEntity):
    """Sensor for MyPlaceIQ AC system on/off state."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, config_entry, aircon_id: str, aircon_data: Dict[str, Any]):
        """Initialize the aircon state sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_state"
        self._attr_name = f"{self._name}_state".replace(" ", "_").lower()
        self._attr_icon = "mdi:power"

    @property
    def state(self) -> Optional[str]:
        """Return the on/off state of the AC."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        aircon = body.get("aircons", {}).get(self._aircon_id, {})
        return "on" if aircon.get("isOn", False) else "off"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(self._config_entry.entry_id, self._aircon_id, self._name, False)

class MyPlaceIQZoneSensor(SensorEntity):
    """Sensor for MyPlaceIQ zone temperature."""
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, config_entry, zone_id: str, zone_data: Dict[str, Any], aircon_id: str):
        """Initialize the zone temperature sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_temperature"
        self._attr_name = f"{self._name}_temperature".replace(" ", "_").lower()
        self._attr_icon = "mdi:thermostat"

    @property
    def state(self) -> Optional[float]:
        """Return the current temperature of the zone."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        zone = body.get("zones", {}).get(self._zone_id, {})
        return zone.get("temperatureSensorValue")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the zone."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return {}
        zone = body.get("zones", {}).get(self._zone_id, {})
        return {
            "is_on": zone.get("isOn", False),
            "target_temperature_heat": zone.get("targetTemperatureHeat"),
            "target_temperature_cool": zone.get("targetTemperatureCool")
        }

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(self._config_entry.entry_id, self._zone_id, self._name, True, self._aircon_id)

class MyPlaceIQZoneStateSensor(SensorEntity):
    """Sensor for MyPlaceIQ zone on/off state."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, config_entry, zone_id: str, zone_data: Dict[str, Any], aircon_id: str):
        """Initialize the zone state sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._zone_id = zone_id
        self._aircon_id = aircon_id
        self._config_entry = config_entry
        self._name = zone_data.get("name", "Zone")
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_state"
        self._attr_name = f"{self._name}_state".replace(" ", "_").lower()
        self._attr_icon = "mdi:toggle-switch"

    @property
    def state(self) -> Optional[str]:
        """Return the on/off state of the zone."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        zone = body.get("zones", {}).get(self._zone_id, {})
        return "on" if zone.get("isOn", False) else "off"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(self._config_entry.entry_id, self._zone_id, self._name, True, self._aircon_id)
