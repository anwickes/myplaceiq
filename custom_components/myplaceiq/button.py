"""Button entities for MyPlaceIQ integration."""
import logging
from typing import Dict, Any, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .utils import parse_coordinator_data, get_device_info, setup_entities, init_entity, perform_optimistic_update

logger = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up MyPlaceIQ button entities from a config entry."""
    logger.debug("Setting up button entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][config_entry.entry_id]["myplaceiq"]

    def create_entities(
        _hass: HomeAssistant,  # Type hint only
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
                    coordinator, config_entry, myplaceiq, {
                        'entity_id': entity_id, 'entity_data': entity_data,
                        'action': "toggle", 'command_type': "SetAirconOnOff",
                        'command_params': None, 'is_zone': False
                    }
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, {
                        'entity_id': entity_id, 'entity_data': entity_data,
                        'action': "mode_heat", 'command_type': "SetAirconMode",
                        'command_params': {"mode": "heat"}, 'is_zone': False
                    }
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, {
                        'entity_id': entity_id, 'entity_data': entity_data,
                        'action': "mode_cool", 'command_type': "SetAirconMode",
                        'command_params': {"mode": "cool"}, 'is_zone': False
                    }
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, {
                        'entity_id': entity_id, 'entity_data': entity_data,
                        'action': "mode_dry", 'command_type': "SetAirconMode",
                        'command_params': {"mode": "dry"}, 'is_zone': False
                    }
                ),
                MyPlaceIQButton(
                    coordinator, config_entry, myplaceiq, {
                        'entity_id': entity_id, 'entity_data': entity_data,
                        'action': "mode_fan", 'command_type': "SetAirconMode",
                        'command_params': {"mode": "fan"}, 'is_zone': False
                    }
                )
            ])
        else:  # Zone buttons
            if entity_data.get("isClickable", False):
                entities.append(
                    MyPlaceIQButton(
                        coordinator, config_entry, myplaceiq, {
                            'entity_id': entity_id, 'entity_data': entity_data,
                            'action': "toggle", 'command_type': "SetZoneOpenClose",
                            'command_params': None, 'is_zone': True,
                            'aircon_id': aircon_id
                        }
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
        config: Dict[str, Any]
    ):
        """Initialize the button entity."""
        super().__init__()
        init_entity(self, coordinator, myplaceiq, config_entry, config)
        self._action = config['action']
        self._command_type = config['command_type']
        self._command_params = config['command_params']
        self._is_zone = config['is_zone']

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
                self.hass, self.coordinator, {
                    'entity_type': "aircon", 'entity_id': self._entity_id,
                    'attribute': "isOn", 'new_value': new_state
                }
            )
            logger.debug("Sent toggle command for aircon %s to isOn=%s",
                         self._entity_id, new_state)
        elif self._command_type == "SetZoneOpenClose" and self._action == "toggle":
            zone = body.get("zones", {}).get(self._entity_id, {})
            new_state = not zone.get("isOn", False)
            command["commands"].append({
                "__type": self._command_type,
                "zoneId": self._entity_id,
                "isOpen": new_state
            })
            perform_optimistic_update(
                self.hass, self.coordinator, {
                    'entity_type': "zone", 'entity_id': self._entity_id,
                    'attribute': "isOn", 'new_value': new_state
                }
            )
            logger.debug("Sent toggle command for zone %s to isOpen=%s",
                         self._entity_id, new_state)
        else:
            command["commands"].append({
                "__type": self._command_type,
                "airconId": self._entity_id,
                **(self._command_params or {})
            })
            if self._command_type == "SetAirconMode":
                perform_optimistic_update(
                    self.hass, self.coordinator, {
                        'entity_type': "aircon", 'entity_id': self._entity_id,
                        'attribute': "mode", 'new_value': self._command_params["mode"]
                    }
                )
            logger.debug("Sent %s command for aircon %s: %s",
                         self._action, self._entity_id, self._command_params)

        await self._myplaceiq.send_command(command)
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return get_device_info({
            'config_entry_id': self._config_entry.entry_id,
            'entity_id': self._entity_id,
            'name': self._name,
            'is_zone': self._is_zone,
            'aircon_id': self._aircon_id
        })
