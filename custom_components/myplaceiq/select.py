"""IQe configuration select entities."""

import json
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .energy_settings import (
    FREE_ELECTRICITY_PERIODS,
    FREE_ELECTRICITY_NONE,
    MyPlaceIQEnergySettingsEntity,
    free_electricity_period,
    iqe_aircon_id,
    iqe_enabled,
    iqe_supported,
    set_free_electricity_period,
    set_iqe_entity_visibility,
)

logger = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up IQe select entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][config_entry.entry_id]["myplaceiq"]
    try:
        body = json.loads(coordinator.data["body"])
    except (KeyError, TypeError, ValueError) as err:
        logger.error("Failed to parse coordinator data for IQe selects: %s", err)
        return

    if not iqe_supported(body):
        return

    entities = []
    added = False

    def _add_select(updated_body):
        aircon_id = iqe_aircon_id(updated_body)
        if aircon_id is None:
            return
        name = updated_body["aircons"][aircon_id].get("name", "Aircon")
        entity = MyPlaceIQIQeFreeElectricityPeriod(
            coordinator, myplaceiq, config_entry, aircon_id, name
        )
        entities.append(entity)
        async_add_entities([entity])

    if iqe_enabled(body):
        _add_select(body)
        added = bool(entities)

    def _update_select():
        nonlocal added
        try:
            updated_body = json.loads(coordinator.data["body"])
        except (KeyError, TypeError, ValueError) as err:
            logger.error("Failed to parse coordinator data for IQe selects: %s", err)
            return
        if not iqe_supported(updated_body):
            return
        enabled = iqe_enabled(updated_body)
        if enabled and not added:
            _add_select(updated_body)
            added = bool(entities)
        visible = enabled
        for entity in entities:
            set_iqe_entity_visibility(hass, entity, visible)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_update_select)
    )


class MyPlaceIQIQeFreeElectricityPeriod(MyPlaceIQEnergySettingsEntity, SelectEntity):
    """Select the free-electricity time window."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-outline"
    _attr_options = [
        FREE_ELECTRICITY_NONE,
        *(period[0] for period in FREE_ELECTRICITY_PERIODS),
    ]

    def __init__(self, coordinator, myplaceiq, config_entry, aircon_id, aircon_name):
        super().__init__(coordinator, myplaceiq, config_entry, aircon_id, aircon_name)
        self._attr_unique_id = f"{config_entry.entry_id}_hub_iqe_free_electricity_period"
        self._attr_has_entity_name = True
        self._attr_name = "HVAC IQe Free Electricity Hours"
        self._attr_entity_registry_visible_default = iqe_enabled(self._load_body())

    @property
    def current_option(self):
        """Return the free-electricity window configured on the hub."""
        settings = self._energy_settings()
        if settings is None:
            return None
        return free_electricity_period(settings) or FREE_ELECTRICITY_NONE

    async def async_select_option(self, option: str) -> None:
        """Set the free-electricity period using the captured tariff format."""
        if option not in self._attr_options:
            raise HomeAssistantError(f"Unsupported free electricity period: {option}")
        await self._async_update_energy_settings(
            lambda settings: set_free_electricity_period(
                settings, None if option == FREE_ELECTRICITY_NONE else option
            )
        )
