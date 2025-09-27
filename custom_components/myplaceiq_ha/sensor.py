from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from .const import DOMAIN
from .coordinator import MyPlaceIQDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [MyPlaceIQSystemSensor(coordinator, entry)]

    # Add a sensor for each zone
    zones = coordinator.data.get("zones", [])
    for zone in zones:
        entities.append(MyPlaceIQZoneSensor(coordinator, entry, zone["id"], zone["name"]))

    async_add_entities(entities)

class MyPlaceIQSystemSensor(SensorEntity):
    """Representation of a MyPlaceIQ system temperature sensor."""

    def __init__(self, coordinator: MyPlaceIQDataUpdateCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self.entry = entry
        self._attr_unique_id = '{}_system_temp'.format(entry.entry_id)
        self._attr_name = "MyPlaceIQ System Temperature"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unit_of_measurement = "°C"

    @property
    def state(self) -> StateType:
        return self.coordinator.data["system"].get("temperature")

    @property
    def available(self) -> bool:
        return self.coordinator.data.get("system") is not None

class MyPlaceIQZoneSensor(SensorEntity):
    """Representation of a MyPlaceIQ zone temperature sensor."""

    def __init__(self, coordinator: MyPlaceIQDataUpdateCoordinator, entry: ConfigEntry, zone_id: str, zone_name: str):
        self.coordinator = coordinator
        self.entry = entry
        self.zone_id = zone_id
        self._attr_unique_id = '{}_zone_{}_temp'.format(entry.entry_id, zone_id)
        self._attr_name = 'MyPlaceIQ Zone {} Temperature'.format(zone_id)
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unit_of_measurement = "°C"

    @property
    def state(self) -> StateType:
        for zone in self.coordinator.data["zones"]:
            if zone["id"] == self.zone_id:
                return zone.get("temperature")
        return None

    @property
    def available(self) -> bool:
        return any(zone["id"] == self.zone_id for zone in self.coordinator.data["zones"])
