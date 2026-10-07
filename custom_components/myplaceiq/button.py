import json
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, aircon_device_name, zone_device_name

logger = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    # : disable=duplicate-code
    """Set up MyPlaceIQ button entities from a config entry."""
    logger.debug("Setting up button entities for MyPlaceIQ")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][config_entry.entry_id]["myplaceiq"]
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
    # pylint: enable=duplicate-code

    # AC System Buttons (Toggle and Modes)
    for aircon_id, aircon_data in aircons.items():
        entities.extend([
            MyPlaceIQButton(
                coordinator=coordinator,
                config_entry=config_entry,
                myplaceiq=myplaceiq,
                entity_id=aircon_id,
                entity_data=aircon_data,
                action="toggle",
                command_type="SetAirconOnOff",
                command_params=None,
                is_zone=False
            ),
            MyPlaceIQButton(
                coordinator=coordinator,
                config_entry=config_entry,
                myplaceiq=myplaceiq,
                entity_id=aircon_id,
                entity_data=aircon_data,
                action="mode_heat",
                command_type="SetAirconMode",
                command_params={"mode": "heat"},
                is_zone=False
            ),
            MyPlaceIQButton(
                coordinator=coordinator,
                config_entry=config_entry,
                myplaceiq=myplaceiq,
                entity_id=aircon_id,
                entity_data=aircon_data,
                action="mode_cool",
                command_type="SetAirconMode",
                command_params={"mode": "cool"},
                is_zone=False
            ),
            MyPlaceIQButton(
                coordinator=coordinator,
                config_entry=config_entry,
                myplaceiq=myplaceiq,
                entity_id=aircon_id,
                entity_data=aircon_data,
                action="mode_dry",
                command_type="SetAirconMode",
                command_params={"mode": "dry"},
                is_zone=False
            ),
            MyPlaceIQButton(
                coordinator=coordinator,
                config_entry=config_entry,
                myplaceiq=myplaceiq,
                entity_id=aircon_id,
                entity_data=aircon_data,
                action="mode_fan",
                command_type="SetAirconMode",
                command_params={"mode": "fan"},
                is_zone=False
            )
        ])

    # Zone Buttons (Toggle and Priority)
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if not zone_data or not zone_data.get("isVisible", False):
                continue

            # Toggle button (only for clickable zones)
            if zone_data.get("isClickable", False):
                entities.append(
                    MyPlaceIQButton(
                        coordinator=coordinator,
                        config_entry=config_entry,
                        myplaceiq=myplaceiq,
                        entity_id=zone_id,
                        entity_data=zone_data,
                        action="toggle",
                        command_type="SetZoneOpenClose",
                        command_params=None,
                        is_zone=True,
                        aircon_id=aircon_id
                    )
                )

            # Priority toggle button (for any zone where priority is allowed).
            # Under QTemp the hub reports every zone as not allowed, so we
            # cannot tell which zones qualify; create the button for all of
            # them so it exists when the user switches back to priority
            # mode, and refuse the press while QTemp is active.
            if (zone_data.get("isPriorityZoneAllowed", False)
                    or aircon_data.get("airconSettings", {}).get("zoneOperation") == "qTemp"):
                entities.append(
                    MyPlaceIQButton(
                        coordinator=coordinator,
                        config_entry=config_entry,
                        myplaceiq=myplaceiq,
                        entity_id=zone_id,
                        entity_data=zone_data,
                        action="toggle_priority",
                        command_type="SetPriorityZone",
                        command_params=None,
                        is_zone=True,
                        aircon_id=aircon_id
                    )
                )

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d button entities", len(entities))
    else:
        logger.warning("No button entities created; check data structure")

class MyPlaceIQButton(ButtonEntity):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    """Button for MyPlaceIQ AC or zone control."""

    def __init__(self, coordinator, config_entry, myplaceiq, entity_id, entity_data, action, command_type, command_params, is_zone, aircon_id=None): # pylint: disable=line-too-long
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
        self._name = entity_data.get("name", f"{'Zone' if is_zone else 'Aircon'}")
        self._attr_unique_id = f"{config_entry.entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}_{action}" # pylint: disable=line-too-long
        self._attr_has_entity_name = True
        self._attr_name = f"HVAC {self._action.replace('_', ' ').title()}"
        self._attr_icon = self._resolve_icon(action, is_zone)
        self._attr_entity_category = EntityCategory.CONFIG

    @staticmethod
    def _resolve_icon(action, is_zone):
        """Return an appropriate icon for the button action."""
        if action == "toggle_priority":
            return "mdi:star-circle"
        if is_zone or action == "toggle":
            return "mdi:toggle-switch"
        return "mdi:thermostat"

    def _perform_optimistic_update(self, body, attribute, new_value):
        """Perform an optimistic update to coordinator.data and refresh the appropriate sensor."""
        entity_type = "zones" if self._is_zone else "aircons"
        sensor_type = "state" if attribute == "isOn" else "mode"
        if entity_type in body and self._entity_id in body[entity_type]:
            body[entity_type][self._entity_id][attribute] = new_value
            self.coordinator.data = {"body": json.dumps(body)}
            # Notify the appropriate sensor to update
            state_sensor_id = f"sensor.{self._name.lower().replace(' ', '_')}_{sensor_type}"
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "homeassistant", "update_entity", {"entity_id": state_sensor_id}
                )
            )
            logger.debug(
                "Optimistically updated %s %s %s to %s", entity_type[:-1],
                    self._entity_id, attribute, new_value)
        else:
            logger.warning(
                "Could not perform optimistic update for %s %s %s: not found in data",
                    entity_type[:-1], self._entity_id, attribute)

    def _perform_priority_optimistic_update(self, body, new_priority_state):
        """Optimistically toggle isPriorityZone for this zone only."""
        zones = body.get("zones", {})
        zone = zones.get(self._entity_id, {})
        zone["isPriorityZone"] = new_priority_state
        zone["isPriorityZoneActive"] = new_priority_state
        zones[self._entity_id] = zone
        body["zones"] = zones
        self.coordinator.data = {"body": json.dumps(body)}
        logger.debug(
            "Optimistically set isPriorityZone=%s for zone %s on aircon %s",
            new_priority_state, self._entity_id, self._aircon_id
        )

    async def async_press(self):
        """Handle button press for AC or zone commands."""
        logger.debug("Button pressed: %s", self._attr_unique_id)
        try:
            data = self.coordinator.data
            if not isinstance(data, dict) or not data or "body" not in data:
                raise HomeAssistantError("Invalid or missing coordinator data")
            body = json.loads(data["body"])

            if self._command_type == "SetAirconOnOff" and self._action == "toggle":
                # Aircon toggle: dynamically determine isOn
                aircon = body.get("aircons", {}).get(self._entity_id, {})
                current_state = aircon.get("isOn", False)
                new_state = not current_state
                command = {
                    "commands": [
                        {
                            "__type": self._command_type,
                            "airconId": self._entity_id,
                            "isOn": new_state
                        }
                    ]
                }
                self._perform_optimistic_update(body, "isOn", new_state)
                logger.debug("Sent toggle command for aircon %s to isOn=%s",
                            self._entity_id, new_state)

            elif self._command_type == "SetZoneOpenClose" and self._action == "toggle":
                # Zone toggle: dynamically determine isOpen
                zone = body.get("zones", {}).get(self._entity_id, {})
                current_state = zone.get("isOn", False)
                new_state = not current_state
                command = {
                    "commands": [
                        {
                            "__type": self._command_type,
                            "zoneId": self._entity_id,
                            "isOpen": new_state
                        }
                    ]
                }
                self._perform_optimistic_update(body, "isOn", new_state)
                logger.debug("Sent toggle command for zone %s to isOpen=%s",
                            self._entity_id, new_state)

            elif self._command_type == "SetPriorityZone" and self._action == "toggle_priority":
                # Priority toggle: read current isPriorityZone and flip it
                zone = body.get("zones", {}).get(self._entity_id, {})
                if not zone.get("isPriorityZoneAllowed", False):
                    raise HomeAssistantError(
                        "Priority zone cannot be set for this zone right now "
                        "(QTemp selects the priority zone automatically)"
                    )
                current_priority = zone.get("isPriorityZone", False)
                new_priority = not current_priority
                command = {
                    "commands": [
                        {
                            "__type": self._command_type,
                            "zoneId": self._entity_id,
                            "priorityEnabled": new_priority
                        }
                    ]
                }
                self._perform_priority_optimistic_update(body, new_priority)
                logger.debug("Sent SetPriorityZone command for zone %s to priorityEnabled=%s",
                            self._entity_id, new_priority)

            else:
                # Mode commands: use predefined command_params
                command = {
                    "commands": [
                        {
                            "__type": self._command_type,
                            "airconId": self._entity_id,
                            **self._command_params
                        }
                    ]
                }
                if self._command_type == "SetAirconMode":
                    self._perform_optimistic_update(body, "mode", self._command_params["mode"])
                logger.debug("Sent %s command for aircon %s: %s",
                            self._action, self._entity_id, self._command_params)

            await self._myplaceiq.send_command(command)
            # Schedule a full coordinator refresh to sync with device
            self.hass.async_create_task(self.coordinator.async_request_refresh())
        except (json.JSONDecodeError, TypeError, HomeAssistantError) as err:
            logger.error("Failed to send %s command for %s %s: %s",
                        self._action, "zone" if self._is_zone else "aircon", self._entity_id, err)
            raise

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": 
                {(DOMAIN, f"{self._config_entry.entry_id}_{'zone' if self._is_zone else 'aircon'}_{self._entity_id}")}, # pylint: disable=line-too-long
            "name": (
                zone_device_name(self._name) if self._is_zone
                else aircon_device_name(self._name)
            ),
            "manufacturer": "MyPlaceIQ",
            "model": "Zone" if self._is_zone else "Aircon"
        }
        if self._is_zone:
            device_info["via_device"] = (DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}") # pylint: disable=line-too-long
        return device_info
