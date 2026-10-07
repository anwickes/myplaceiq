import copy
import json
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

logger = logging.getLogger(__name__)

# airconSettings.zoneOperation decides how the aircon picks the zone that
# drives the system. Confirmed by packet capture and on a real hub:
#   "priority" - the user picks the priority zone (SetPriorityZone)
#   "qTemp"    - the hub picks, based on which zone most needs heating or
#                cooling; manual priority selection is disabled (every
#                zone reports isPriorityZoneAllowed = false)
# The official app presents this as a single "Enable QTemp" toggle.
ZONE_OPERATION_QTEMP = "qTemp"
ZONE_OPERATION_PRIORITY = "priority"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MyPlaceIQ switch entities from a config entry."""
    logger.debug("Setting up switch entities for MyPlaceIQ")
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

    entities = []
    for aircon_id, aircon_data in body.get("aircons", {}).items():
        # Only offer the control where the hub reports the setting at all,
        # so controllers without QTemp support don't get a dead entity.
        if "zoneOperation" in aircon_data.get("airconSettings", {}):
            entities.append(
                MyPlaceIQQTempSwitch(
                    coordinator, myplaceiq, config_entry, aircon_id, aircon_data
                )
            )

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d switch entities", len(entities))
    else:
        logger.debug("No switch entities created; hub reports no zoneOperation setting")


class MyPlaceIQQTempSwitch(CoordinatorEntity, SwitchEntity):
    # pylint: disable=too-many-instance-attributes
    """Enable or disable QTemp for an aircon (off = manual priority zones)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, myplaceiq, config_entry, aircon_id, aircon_data):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        super().__init__(coordinator)
        self._myplaceiq = myplaceiq
        self._config_entry = config_entry
        self._aircon_id = aircon_id
        self._name = aircon_data.get("name", "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_aircon_{aircon_id}_qtemp"
        self._attr_name = f"{self._name}_qtemp".replace(" ", "_").lower()
        self._attr_icon = "mdi:thermometer-auto"

    def _load_body(self) -> dict:
        """Return the parsed coordinator body, or raise if there is none."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            raise HomeAssistantError("Invalid or missing coordinator data")
        try:
            return json.loads(data["body"])
        except (json.JSONDecodeError, TypeError) as err:
            raise HomeAssistantError(f"Failed to parse coordinator data: {err}") from err

    @property
    def is_on(self):
        """Return True if QTemp is active, None if the mode is not one we know."""
        try:
            body = self._load_body()
        except HomeAssistantError:
            return None
        aircon = body.get("aircons", {}).get(self._aircon_id, {})
        value = aircon.get("airconSettings", {}).get("zoneOperation")
        if value == ZONE_OPERATION_QTEMP:
            return True
        if value == ZONE_OPERATION_PRIORITY:
            return False
        if value is not None:
            # A mode we have not seen in a capture - report unknown rather
            # than claim QTemp is off, and make it easy to spot in a report.
            logger.debug("Unrecognised zoneOperation %r for aircon %s", value, self._aircon_id)
        return None

    async def async_turn_on(self, **_kwargs) -> None:
        """Enable QTemp."""
        await self._set_zone_operation(ZONE_OPERATION_QTEMP)

    async def async_turn_off(self, **_kwargs) -> None:
        """Disable QTemp, returning to manual priority zones."""
        await self._set_zone_operation(ZONE_OPERATION_PRIORITY)

    async def _set_zone_operation(self, zone_operation: str) -> None:
        """Change the zone operation.

        The hub only accepts the complete airconSettings object (as the
        official app sends), so start from the current settings and change
        just zoneOperation - sending a partial object would reset the rest.
        """
        body = self._load_body()
        aircon = body.get("aircons", {}).get(self._aircon_id)
        settings = copy.deepcopy(aircon.get("airconSettings")) if aircon else None
        if not settings:
            raise HomeAssistantError(
                f"No airconSettings known for aircon {self._aircon_id}; "
                "cannot change QTemp"
            )
        settings["zoneOperation"] = zone_operation

        command = {
            "commands": [{
                "__type": "SetAirconSettings",
                "airconId": self._aircon_id,
                "airconSettings": settings,
            }]
        }

        def _apply(cached_body):
            cached_body["aircons"][self._aircon_id]["airconSettings"]["zoneOperation"] = (
                zone_operation
            )

        self.coordinator.apply_local_update(_apply)
        logger.debug("Setting zoneOperation=%s for aircon %s", zone_operation, self._aircon_id)

        try:
            await self._myplaceiq.send_command(command)
        except HomeAssistantError:
            # The optimistic value is now wrong - resync from the hub.
            await self.coordinator.async_request_refresh_after_command()
            raise
        await self.coordinator.async_request_refresh_after_command()

    @property
    def device_info(self):
        """Return device information - attach to the parent aircon device."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": f"Aircon {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }
