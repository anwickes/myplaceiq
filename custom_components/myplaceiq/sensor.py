"""Sensor entities for MyPlaceIQ integration."""
import logging
from typing import Dict, Any, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import (
    SensorEntity, SensorDeviceClass, SensorStateClass
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info, setup_entities, init_entity

logger = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up MyPlaceIQ sensor entities from a config entry."""
    logger.debug("Setting up sensor entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    def create_entities(
        _hass: HomeAssistant,  # Type hint only
        config_entry,
        coordinator,
        entity_id: str,
        entity_data: Dict[str, Any],
        aircon_id: Optional[str] = None
    ) -> List[SensorEntity]:
        """Create sensor entities for aircons and zones."""
        entities = []
        if aircon_id is None:  # Aircon sensors
            entities.extend([
                MyPlaceIQAirconSensor(
                    coordinator, config_entry, entity_id, entity_data
                ),
                MyPlaceIQAirconStateSensor(
                    coordinator, config_entry, entity_id, entity_data
                )
            ])
        else:  # Zone sensors
            if entity_data.get("isClickable", False):
                entities.extend([
                    MyPlaceIQZoneSensor(
                        coordinator, config_entry, entity_id,
                        entity_data, aircon_id
                    ),
                    MyPlaceIQZoneStateSensor(
                        coordinator, config_entry, entity_id,
                        entity_data, aircon_id
                    )
                ])
        return entities

    entities = setup_entities(hass, config_entry, coordinator, create_entities)
    async_add_entities(entities)

class MyPlaceIQAirconSensor(SensorEntity):
    """Sensor for MyPlaceIQ AC system mode."""
    def __init__(
        self, coordinator, config_entry,
        aircon_id: str, aircon_data: Dict[str, Any]
    ):
        """Initialize the aircon mode sensor."""
        super().__init__()
        init_entity(self, coordinator, None, config_entry, aircon_id,
                   aircon_data, "sensor")

    @property
    def state(self) -> Optional[str]:
        """Return the state of the AC (mode or off)."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        aircon = body.get("aircons", {}).get(self._entity_id, {})
        return aircon.get("mode", "unknown") if aircon.get("isOn", False) else "off"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the AC."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return {}
        aircon = body.get("aircons", {}).get(self._entity_id, {})
        return {
            "is_on": aircon.get("isOn", False),
            "actual_temperature": aircon.get("actualTemperature"),
            "target_temperature_heat": aircon.get("targetTemperatureHeat"),
            "target_temperature_cool": aircon.get("targetTemperatureCool")
        }

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(
            self._config_entry.entry_id, self._entity_id, self._name, False
        )

class MyPlaceIQAirconStateSensor(SensorEntity):
    """Sensor for MyPlaceIQ AC system on/off state."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator, config_entry,
        aircon_id: str, aircon_data: Dict[str, Any]
    ):
        """Initialize the aircon state sensor."""
        super().__init__()
        init_entity(self, coordinator, None, config_entry, aircon_id,
                   aircon_data, "sensor")

    @property
    def state(self) -> Optional[str]:
        """Return the on/off state of the AC."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        aircon = body.get("aircons", {}).get(self._entity_id, {})
        return "on" if aircon.get("isOn", False) else "off"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(
            self._config_entry.entry_id, self._entity_id, self._name, False
        )

class MyPlaceIQZoneSensor(SensorEntity):
    """Sensor for MyPlaceIQ zone temperature."""
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator, config_entry,
        zone_id: str, zone_data: Dict[str, Any], aircon_id: str
    ):
        """Initialize the zone temperature sensor."""
        super().__init__()
        init_entity(self, coordinator, None, config_entry, zone_id,
                   zone_data, "sensor", is_zone=True, aircon_id=aircon_id)

    @property
    def state(self) -> Optional[float]:
        """Return the current temperature of the zone."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        zone = body.get("zones", {}).get(self._entity_id, {})
        return zone.get("temperatureSensorValue")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional state attributes for the zone."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return {}
        zone = body.get("zones", {}).get(self._entity_id, {})
        return {
            "is_on": zone.get("isOn", False),
            "target_temperature_heat": zone.get("targetTemperatureHeat"),
            "target_temperature_cool": zone.get("targetTemperatureCool")
        }

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(
            self._config_entry.entry_id, self._entity_id,
            self._name, True, self._aircon_id
        )

class MyPlaceIQZoneStateSensor(SensorEntity):
    """Sensor for MyPlaceIQ zone on/off state."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator, config_entry,
        zone_id: str, zone_data: Dict[str, Any], aircon_id: str
    ):
        """Initialize the zone state sensor."""
        super().__init__()
        init_entity(self, coordinator, None, config_entry, zone_id,
                   zone_data, "sensor", is_zone=True, aircon_id=aircon_id)

    @property
    def state(self) -> Optional[str]:
        """Return the on/off state of the zone."""
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            return None
        zone = body.get("zones", {}).get(self._entity_id, {})
        return "on" if zone.get("isOn", False) else "off"

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(
            self._config_entry.entry_id, self._entity_id,
            self._name, True, self._aircon_id
        )
