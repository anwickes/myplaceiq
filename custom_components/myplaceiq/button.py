"""Button entities for MyPlaceIQ integration."""
import json
import logging
from typing import Dict, Any, Optional
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ button entities from a config entry."""
    logger.debug("Setting up button entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][config_entry.entry_id]["myplaceiq"]
    body = parse_coordinator_data(coordinator.data)
    if not body:
        return

    aircons = body.get("aircons", {})
    zones = body.get("zones", {})
    entities = []

    # AC System Buttons (Toggle and Modes)
    for aircon_id, aircon_data in aircons.items():
        entities.extend([
            MyPlaceIQButton(coordinator, config_entry, myplaceiq, aircon_id, aircon_data, "toggle", "SetAirconOnOff", None, False),
            MyPlaceIQButton(coordinator, config_entry, myplaceiq, aircon_id, aircon_data, "mode_heat", "SetAirconMode", {"mode": "heat"}, False),
            MyPlaceIQButton(coordinator, config_entry, myplaceiq, aircon_id, aircon_data, "mode_cool", "SetAirconMode", {"mode": "cool"}, False),
            MyPlaceIQButton(coordinator, config_entry, myplaceiq, aircon_id, aircon_data, "mode_dry", "SetAirconMode", {"mode": "dry"}, False),
            MyPlaceIQButton(coordinator, config_entry, myplaceiq, aircon_id, aircon_data, "mode_fan", "SetAirconMode", {"mode": "fan"}, False)
        ])

    # Zone Buttons
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if zone_data and zone_data.get("isVisible", False) and zone_data.get("isClickable", False):
                entities.append(
                    MyPlaceIQButton(coordinator, config_entry, myplaceiq, zone_id, zone_data, "toggle", "SetZoneOpenClose", None, True, aircon_id)
                )

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d button entities", len(entities))
    else:
        logger.warning("No button entities created; check data structure")

class MyPlaceIQButton(ButtonEntity):
    """Button for MyPlaceIQ AC or zone control."""
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, config_entry, myplaceiq, entity_id: str, entity_data: Dict[str, Any], action: str, command_type: str, command_params: Optional[Dict[str, Any]], is_zone: bool, aircon_id: Optional[str] = None):
        """Initialize the button entity."""
        super().__init__()
        self.coordinator = coordinator
        self._myplaceiq = myplaceiq
        self._entity_id = entity_id
        self._config_entry = config_entry
        self._action = action
        self._command_type = command_type
        self._command_params = command_params
        self._is_zone = is_zone
        self._aircon_id = aircon_id if is_zone else entity_id
        self._name = entity_data.get("name", "Zone" if is_zone else "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}_{action}"
        self._attr_name = f"{self._name}_{action}".replace(" ", "_").lower()
        self._attr_icon = "mdi:toggle-switch" if is_zone or action == "toggle" else "mdi:thermostat"

    def _perform_optimistic_update(self, body: Dict[str, Any], attribute: str, new_value: Any) -> None:
        """Perform an optimistic update to coordinator.data and refresh the appropriate sensor."""
        entity_type = "zones" if self._is_zone else "aircons"
        sensor_type = "state" if attribute == "isOn" else "mode"
        if entity_type in body and self._entity_id in body[entity_type]:
            body[entity_type][self._entity_id][attribute] = new_value
            self.coordinator.data = {"body": json.dumps(body)}
            state_sensor_id = f"sensor.{self._name.lower().replace(' ', '_')}_{sensor_type}"
            self.hass.async_create_task(
                self.hass.services.async_call("homeassistant", "update_entity", {"entity_id": state_sensor_id})
            )
            logger.debug("Optimistically updated %s %s %s to %s", entity_type[:-1], self._entity_id, attribute, new_value)
        else:
            logger.warning("Could not perform optimistic update for %s %s %s: not found in data", entity_type[:-1], self._entity_id, attribute)

    async def async_press(self) -> None:
        """Handle button press for AC or zone commands."""
        logger.debug("Button pressed: %s", self._attr_name)
        body = parse_coordinator_data(self.coordinator.data)
        if not body:
            raise HomeAssistantError("Invalid or missing coordinator data")

        command = {"commands": []}
        if self._command_type == "SetAirconOnOff" and self._action == "toggle":
            aircon = body.get("aircons", {}).get(self._entity_id, {})
            new_state = not aircon.get("isOn", False)
            command["commands"].append({"__type": self._command_type, "airconId": self._entity_id, "isOn": new_state})
            self._perform_optimistic_update(body, "isOn", new_state)
            logger.debug("Sent toggle command for aircon %s to isOn=%s", self._entity_id, new_state)
        elif self._command_type == "SetZoneOpenClose" and self._action == "toggle":
            zone = body.get("zones", {}).get(self._entity_id, {})
            new_state = not zone.get("isOn", False)
            command["commands"].append({"__type": self._command_type, "zoneId": self._entity_id, "isOpen": new_state})
            self._perform_optimistic_update(body, "isOn", new_state)
            logger.debug("Sent toggle command for zone %s to isOpen=%s", self._entity_id, new_state)
        else:
            command["commands"].append({"__type": self._command_type, "airconId": self._entity_id, **(self._command_params or {})})
            if self._command_type == "SetAirconMode":
                self._perform_optimistic_update(body, "mode", self._command_params["mode"])
            logger.debug("Sent %s command for aircon %s: %s", self._action, self._entity_id, self._command_params)

        await self._myplaceiq.send_command(command)
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(self._config_entry.entry_id, self._entity_id, self._name, self._is_zone, self._aircon_id)
