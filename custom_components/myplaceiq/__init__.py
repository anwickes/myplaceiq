import logging
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
        await coordinator.async_refresh()  # Replaced async_config_entry_first_refresh
        if not coordinator.last_update_success:
            raise ValueError("Initial data fetch failed")

        hass.data[DOMAIN][entry.entry_id] = {
            "coordinator": coordinator,
            "myplaceiq": myplaceiq
        }

        await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button", "climate"])
        entry.add_update_listener(async_reload_entry)
        logger.debug("Added update listener for entry: %s", entry.entry_id)
        return True
    except Exception as err:
        logger.error("Failed to set up MyPlaceIQ integration: %s", err)
        raise

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    logger.debug("Unloading MyPlaceIQ entry: %s", entry.entry_id)
    try:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "button", "climate"])
        if unload_ok and entry.entry_id in hass.data[DOMAIN]:
            await hass.data[DOMAIN][entry.entry_id]["myplaceiq"].close()
            hass.data[DOMAIN].pop(entry.entry_id)
        return unload_ok
    except Exception as err:
        logger.error("Error unloading MyPlaceIQ entry: %s", err)
        return False

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options are updated."""
    logger.debug("Reloading MyPlaceIQ entry: %s with new options: %s", entry.entry_id, entry.options)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
