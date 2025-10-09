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

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    # pylint: disable=unused-argument
    """Set up the MyPlaceIQ integration."""
    hass.data.setdefault(DOMAIN, {})
    logger.debug("Initializing MyPlaceIQ integration")
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyPlaceIQ from a config entry."""
    logger.debug("Setting up MyPlaceIQ entry: %s with options: %s", entry.entry_id, entry.options)
    try:
        # Check if the entry is already being set up
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            logger.warning("Config entry %s is already being set up, skipping", entry.entry_id)
            return False

        myplaceiq = MyPlaceIQ(
            hass=hass,
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, 8086),
            client_id=entry.data[CONF_CLIENT_ID],
            client_secret=entry.data[CONF_CLIENT_SECRET]
        )
        coordinator = MyPlaceIQDataUpdateCoordinator(
            hass,
            myplaceiq,
            update_interval=entry.options.get(CONF_POLL_INTERVAL, 60)
        )
        await coordinator.async_refresh()  # Use the recommended method
        if not coordinator.last_update_success:
            raise ValueError("Initial data fetch failed")

        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "myplaceiq": myplaceiq
        }

        await hass.config_entries.async_forward_entry_setups(entry,
            ["sensor", "button", "climate"])
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
            return True  # Consider it unloaded if it doesn't exist

        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry,
            ["sensor", "button", "climate"])
        if unload_ok:
            # Close the WebSocket connection
            await hass.data[DOMAIN][entry.entry_id]["myplaceiq"].close()
            # Remove the entry from hass.data
            hass.data[DOMAIN].pop(entry.entry_id, None)
            logger.debug("Successfully unloaded entry: %s", entry.entry_id)
        else:
            logger.error("Failed to unload platforms for entry: %s", entry.entry_id)
        return unload_ok
    except Exception as err: # pylint: disable=broad-except
        logger.error("Error unloading MyPlaceIQ entry: %s", err)
        return False

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    logger.debug("Reloading MyPlaceIQ entry: %s with new options: %s",
        entry.entry_id, entry.options)
    # Skip reload if _skip_reload flag is set
    if entry.options.get("_skip_reload", False):
        logger.debug("Skipping reload for entry %s due to _skip_reload flag",
            entry.entry_id)
        return
    # Ensure the entry is unloaded before setting it up again
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
