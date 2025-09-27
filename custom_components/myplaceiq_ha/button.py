from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN
from .coordinator import MyPlaceIQDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the button platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        MyPlaceIQSystemButton(coordinator, entry, "on", "Turn On System"),
        MyPlaceIQSystemButton(coordinator, entry, "off", "Turn Off System"),
    ]

    # Add buttons for each zone
    zones = coordinator.data.get("zones", [])
    for zone in zones:
        entities.append(
            MyPlaceIQZoneButton(coordinator, entry, zone["id"], zone["name"], "on", f"Turn On Zone {zone['name']}")
        )
        entities.append(
            MyPlaceIQZoneButton(coordinator, entry, zone["id"], zone["name"], "off", f"Turn Off Zone {zone['name']}")
        )

    async_add_entities(entities)

class MyPlaceIQSystemButton(ButtonEntity):
    """Representation of a MyPlaceIQ system control button."""

    def __init__(self, coordinator: MyPlaceIQDataUpdateCoordinator, entry: ConfigEntry, action: str, name: str):
        self.coordinator = coordinator
        self.entry = entry
        self.action = action
        self._attr_unique_id = '{}_system_{}'.format(entry.entry_id, action)
        self._attr_name = name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_send_command(
            {"type": "control", "target": "system", "state": self.action}
        )

class MyPlaceIQZoneButton(ButtonEntity):
    """Representation of a MyPlaceIQ zone control button."""

    def __init__(
        self, coordinator: MyPlaceIQDataUpdateCoordinator, entry: ConfigEntry, zone_id: str, zone_name: str, action: str, name: str
    ):
        self.coordinator = coordinator
        self.entry = entry
        self.zone_id = zone_id
        self.action = action
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone_id}_{action}"
        self._attr_name = name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_send_command(
            {"type": "control", "target": "zone", "zone_id": self.zone_id, "state": self.action}
        )
