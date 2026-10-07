import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_POLL_INTERVAL
)
from .coordinator import MyPlaceIQDataUpdateCoordinator
from .myplaceiq import MyPlaceIQ

logger = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "button", "climate", "switch"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool: # pylint: disable=unused-argument
    """Set up the MyPlaceIQ integration."""
    hass.data.setdefault(DOMAIN, {})
    logger.debug("Initializing MyPlaceIQ integration")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyPlaceIQ from a config entry."""
    logger.debug("Setting up MyPlaceIQ entry: %s with options: %s", entry.entry_id, entry.options)
    try:
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            logger.warning("Config entry %s is already being set up, skipping", entry.entry_id)
            return False

        myplaceiq = MyPlaceIQ(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, 8086),
            client_id=entry.data[CONF_CLIENT_ID],
            client_secret=entry.data[CONF_CLIENT_SECRET]
        )
        coordinator = MyPlaceIQDataUpdateCoordinator(
            hass,
            myplaceiq,
            update_interval=entry.options.get(CONF_POLL_INTERVAL, 30)
        )
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            raise ValueError("Initial data fetch failed")

        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "myplaceiq": myplaceiq
        }

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        logger.debug("Added update listener for entry: %s", entry.entry_id)
        return True
    except Exception as err:
        logger.error("Failed to set up MyPlaceIQ integration: %s", err)
        raise

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    logger.debug("Unloading MyPlaceIQ entry: %s", entry.entry_id)
    try:
        if entry.entry_id not in hass.data.get(DOMAIN, {}):
            logger.warning("Config entry %s not found in hass.data", entry.entry_id)
            return True

        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id, None)
            logger.debug("Successfully unloaded entry: %s", entry.entry_id)
        else:
            logger.error("Failed to unload platforms for entry: %s", entry.entry_id)
        return unload_ok
    except Exception as err: # pylint: disable=broad-exception-caught
        logger.error("Error unloading MyPlaceIQ entry: %s", err)
        return False

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    logger.debug("Reloading MyPlaceIQ entry: %s with new options: %s",
        entry.entry_id, entry.options)
    await hass.config_entries.async_reload(entry.entry_id)
