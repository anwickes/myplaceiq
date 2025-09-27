from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, CONF_HOST, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_POLL_INTERVAL
from .myplaceiq import MyPlaceIQ

class MyPlaceIQDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage polling MyPlaceIQ hub via WebSocket."""

    def __init__(self, hass: HomeAssistant, config_entry):
        self.hass = hass
        self.config_entry = config_entry
        self.myplaceiq = MyPlaceIQ(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_CLIENT_ID],
            config_entry.data[CONF_CLIENT_SECRET],
        )
        super().__init__(
            hass,
            name=DOMAIN,
            update_interval=timedelta(seconds=config_entry.options.get(CONF_POLL_INTERVAL, 60)),
        )

    async def _async_update_data(self):
        """Fetch data from the MyPlaceIQ hub."""
        try:
            return await self.myplaceiq.get_data()
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}")

    async def async_send_command(self, command: dict):
        """Send a command to the MyPlaceIQ hub."""
        try:
            await self.myplaceiq.set_data(command)
            await self.async_request_refresh()
        except Exception as err:
            raise UpdateFailed(f"Error sending command: {err}")