"""Button entities for MyPlaceIQ integration."""
import json
import logging
from typing import Dict, Any, Optional, List
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info, setup_entities, init_entity, perform_optimistic_update

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ button entities from a config entry."""
    logger.debug("Setting up button entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][config_entry.entry_id]["myplaceiq"]

    def create_entities(
        hass: HomeAssistant,  # Used for type hint
        config_entry,
        coordinator,
        entity_id: str,
        entity_data: Dict[str, Any],
        aircon_id: Optional[str] = None
    ) -> List[ButtonEntity]:
        """Create button entities for aircons and zones."""
        entities = []
        if aircon_id is None:  # Aircon buttons
            entities.extend([
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, entity_id, entity_data,
                    "toggle", "SetAirconOnOff", None, False
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, entity_id, entity_data,
                    "mode_heat", "SetAirconMode", {"mode": "heat"}, False
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, entity_id, entity_data,
                    "mode_cool", "SetAirconMode", {"mode": "cool"}, False
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, entity_id, entity_data,
                    "mode_dry", "SetAirconMode", {"mode": "dry"}, False
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, entity_id, entity_data,
                    "mode_fan", "SetAirconMode", {"mode": "fan"}, False
                )
            ])
        else:  # Zone buttons
            if entity_data.get("isClickable", False):
                entities.append(
                    MyPlaceIQButton(
                        coordinator, config_entry, myplaceiq, entity_id, entity_data,
                        "toggle", "SetZoneOpenClose", None, True, aircon_id
                    )
                )
        return entities

    entities = setup_entities(hass, config_entry, coordinator, create_entities)
    async_add_entities(entities)

class MyPlaceIQButton(ButtonEntity):
    """Button for MyPlaceIQ AC or zone control."""
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator,
        config_entry,
        myplaceiq,
        entity_id: str,
        entity_data: Dict[str, Any],
        action: str,
        command_type: str,
        command_params: Optional[Dict[str, Any]] = None,
        is_zone: bool = False,
        aircon_id: Optional[str] = None
    ):
        """Initialize the button entity."""
        super().__init__()
        init_entity(self, coordinator, myplaceiq, config_entry, entity_id, entity_data, "button", action, is_zone, aircon_id)
        self._action = action
        self._command_type = command_type
        self._command_params = command_params
        self._is_zone = is_zone

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
            command["commands"].append({
                "__type": self._command_type,
                "airconId": self._entity_id,
                "isOn": new_state
            })
            perform_optimistic_update(
                self.hass, self.coordinator, "aircon", self._entity_id, "isOn", new_state
            )
            logger.debug("Sent toggle command for aircon %s to isOn=%s", self._entity_id, new_state)
        elif self._command_type == "SetZoneOpenClose" and self._action == "toggle":
            zone = body.get("zones", {}).get(self._entity_id, {})
            new_state = not zone.get("isOn", False)
            command["commands"].append({
                "__type": self._command_type,
                "zoneId": self._entity_id,
                "isOpen": new_state
            })
            perform_optimistic_update(
                self.hass, self.coordinator, "zone", self._entity_id, "isOn", new_state
            )
            logger.debug("Sent toggle command for zone %s to isOpen=%s", self._entity_id, new_state)
        else:
            command["commands"].append({
                "__type": self._command_type,
                "airconId": self._entity_id,
                **(self._command_params or {})
            })
            if self._command_type == "SetAirconMode":
                perform_optimistic_update(
                    self.hass, self.coordinator, "aircon", self._entity_id,
                    "mode", self._command_params["mode"]
                )
            logger.debug("Sent %s command for aircon %s: %s", self._action, self._entity_id, self._command_params)

        await self._myplaceiq.send_command(command)
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info(
            self._config_entry.entry_id, self._entity_id,
            self._name, self._is_zone, self._aircon_id
        )
