import copy
import json
import logging
from math import isfinite
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, aircon_device_name

logger = logging.getLogger(__name__)

# The official app converts the "running current" it asks for (amps) into
# the watts stored in airconPowerTableW using a fixed 240 V - confirmed by
# capture: 31.5 A is sent as 7560 W.
NOMINAL_VOLTAGE_V = 240

# The free-electricity window is a zero-cost tariff between these minute
# offsets. The app offers these two fixed three-hour periods; both, and the
# "None" encoding (one all-day tariff, 0-0 at the normal cost), are confirmed
# by captures of the app.
FREE_ELECTRICITY_PERIODS = (
    ("11 am to 2 pm", 660, 840),
    ("12 pm to 3 pm", 720, 900),
)
FREE_ELECTRICITY_NONE = "None"


def free_electricity_enabled(settings: dict) -> bool | None:
    """Return whether a valid tariff schedule contains a free interval."""
    tariffs = settings.get("tariffs")
    if not isinstance(tariffs, list) or not tariffs:
        return None

    for tariff in tariffs:
        if not isinstance(tariff, dict):
            return None
        cost = tariff.get("cost")
        start = tariff.get("timeStartMins")
        stop = tariff.get("timeStopMins")
        if (
            isinstance(cost, bool)
            or not isinstance(cost, (int, float))
            or not isfinite(cost)
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(stop, int)
            or isinstance(stop, bool)
        ):
            return None
        # start == stop == 0 is a single all-day tariff, so a zero cost
        # there means the whole day is free; any other start == stop is an
        # empty interval.
        if cost == 0 and (start != stop or start == 0):
            return True
    return False


def free_electricity_period(settings: dict) -> str | None:
    """Return the recognized free-electricity window, if one is configured."""
    if free_electricity_enabled(settings) is not True:
        return None
    tariffs = settings.get("tariffs")
    for tariff in tariffs:
        if tariff.get("cost") != 0:
            continue
        for label, start, stop in FREE_ELECTRICITY_PERIODS:
            if (
                tariff.get("timeStartMins") == start
                and tariff.get("timeStopMins") == stop
            ):
                return label
    return None


def set_free_electricity_period(settings: dict, period: str | None) -> None:
    """Replace tariffs with the captured free-window format, or disable it."""
    tariffs = settings.get("tariffs")
    if (
        not isinstance(tariffs, list)
        or not tariffs
        or any(not isinstance(tariff, dict) for tariff in tariffs)
    ):
        raise HomeAssistantError("Cannot change free electricity without a valid tariff schedule")

    normal_tariff = next(
        (
            tariff for tariff in tariffs
            if isinstance(tariff.get("cost"), (int, float))
            and not isinstance(tariff.get("cost"), bool)
            and isfinite(tariff["cost"])
            and tariff["cost"] != 0
        ),
        tariffs[0],
    )
    normal_cost = normal_tariff.get("cost", 100.0)
    if (
        isinstance(normal_cost, bool)
        or not isinstance(normal_cost, (int, float))
        or not isfinite(normal_cost)
    ):
        normal_cost = 100.0

    if period is None:
        disabled_tariff = copy.deepcopy(normal_tariff)
        disabled_tariff.update(
            timeStartMins=0, timeStopMins=0, cost=normal_cost
        )
        settings["tariffs"] = [disabled_tariff]
        return

    selected = next(
        ((start, stop) for label, start, stop in FREE_ELECTRICITY_PERIODS
         if label == period),
        None,
    )
    if selected is None:
        raise HomeAssistantError(f"Unsupported free electricity period: {period}")

    start, stop = selected
    before = copy.deepcopy(normal_tariff)
    free = copy.deepcopy(normal_tariff)
    after = copy.deepcopy(normal_tariff)
    before.update(timeStartMins=0, timeStopMins=start, cost=normal_cost)
    free.update(timeStartMins=start, timeStopMins=stop, cost=0.0)
    after.update(timeStartMins=stop, timeStopMins=0, cost=normal_cost)
    settings["tariffs"] = [before, free, after]


def iqe_supported(body: dict) -> bool:
    """Return True if IQe is supported by the hub."""
    return bool(body.get("energySettings")) and bool(
        body.get("featureFlags", {}).get("isIqeEnabled", False)
    )


def iqe_enabled(body: dict) -> bool:
    """Return True if at least one IQe automation mode is enabled."""
    if not iqe_supported(body):
        return False
    settings = body["energySettings"]
    return any(
        settings.get(key) is True
        for key in ("smartAirCoolOn", "smartAirHeatOn")
    )


def iqe_aircon_id(body: dict):
    """Return the id of the aircon IQe controls, or the first aircon as a fallback."""
    aircons = body.get("aircons", {})
    configured = body.get("energySettings", {}).get("smartAirAirconId")
    if configured in aircons:
        return configured
    return next(iter(aircons), None)


class MyPlaceIQEnergySettingsEntity(CoordinatorEntity):
    """Base for entities that read and write the hub-wide IQe energySettings.

    energySettings is a single object for the whole hub, and the hub only
    accepts the complete object back (as the official app sends it). Every
    write therefore starts from the current cached settings and changes
    just one field, so a change from Home Assistant never resets the
    others. The cache is updated synchronously before the command is sent,
    so two quick changes accumulate instead of overwriting each other.

    Entities that only make sense while IQe is running set
    _iqe_managed_visibility and are hidden while it is not (see
    _iqe_visible). They always exist, so nothing goes "unavailable" after a
    restart. The integration only hides an entity at the moment IQe switches
    off, and only unhides one it hid itself, so an entity the user unhides
    is not re-hidden while IQe stays off.
    """

    _iqe_managed_visibility = False
    _iqe_last_visible = None

    def __init__(self, coordinator, myplaceiq, config_entry, aircon_id, aircon_name):
        # pylint: disable=too-many-arguments, too-many-positional-arguments
        super().__init__(coordinator)
        self._myplaceiq = myplaceiq
        self._config_entry = config_entry
        self._aircon_id = aircon_id
        self._aircon_name = aircon_name

    def _load_body(self) -> dict:
        """Return the parsed coordinator body, or raise if there is none."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            raise HomeAssistantError("Invalid or missing coordinator data")
        try:
            return json.loads(data["body"])
        except (json.JSONDecodeError, TypeError) as err:
            raise HomeAssistantError(f"Failed to parse coordinator data: {err}") from err

    def _energy_settings(self):
        """Return the current energySettings dict, or None if unavailable."""
        try:
            return self._load_body().get("energySettings") or None
        except HomeAssistantError:
            return None

    async def _async_update_energy_settings(self, mutator) -> None:
        """Apply mutator(settings) to a copy of the current settings and send it."""
        settings = copy.deepcopy(self._load_body().get("energySettings"))
        if not settings:
            raise HomeAssistantError("No energySettings known; cannot change IQe settings")
        mutator(settings)

        command = {
            "commands": [{
                "__type": "SetEnergySettings",
                "energySettings": settings,
            }]
        }

        def _apply(cached_body):
            cached_body["energySettings"] = copy.deepcopy(settings)

        self.coordinator.apply_local_update(_apply)
        logger.debug("Sending SetEnergySettings for %s", self._attr_unique_id)

        try:
            await self._myplaceiq.send_command(command)
        except HomeAssistantError:
            # The optimistic value is now wrong - resync from the hub.
            await self.coordinator.async_request_refresh_after_command()
            raise
        await self.coordinator.async_request_refresh_after_command()

    def _iqe_visible(self, body: dict) -> bool:
        """Return whether this entity is relevant right now (override per entity)."""
        return iqe_enabled(body)

    @property
    def entity_registry_visible_default(self) -> bool:
        """Start hidden if IQe is not running when the entity is first registered."""
        if not self._iqe_managed_visibility:
            return True
        try:
            return self._iqe_visible(self._load_body())
        except HomeAssistantError:
            return True

    def _sync_iqe_visibility(self, startup: bool = False) -> None:
        """Hide or show this entity in the registry as IQe switches on and off."""
        if not self._iqe_managed_visibility or self.hass is None or self.entity_id is None:
            return
        try:
            visible = self._iqe_visible(self._load_body())
        except HomeAssistantError:
            return

        registry = er.async_get(self.hass)
        entry = registry.async_get(self.entity_id)
        if entry is not None:
            if visible and entry.hidden_by == er.RegistryEntryHider.INTEGRATION:
                registry.async_update_entity(self.entity_id, hidden_by=None)
            elif (
                not visible
                and not startup
                and self._iqe_last_visible is not False
                and entry.hidden_by is None
            ):
                registry.async_update_entity(
                    self.entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
                )
        self._iqe_last_visible = visible

    async def async_added_to_hass(self) -> None:
        """Sync visibility once the entity is registered."""
        await super().async_added_to_hass()
        self._sync_iqe_visibility(startup=True)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Keep visibility in step with the hub before writing the new state."""
        self._sync_iqe_visibility()
        super()._handle_coordinator_update()

    @property
    def device_info(self):
        """Return device information - attach to the aircon IQe controls."""
        return {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")},
            "name": aircon_device_name(self._aircon_name),
            "manufacturer": "MyPlaceIQ",
            "model": "Aircon",
        }
