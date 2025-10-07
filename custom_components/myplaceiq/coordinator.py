import logging
import json
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN

logger = logging.getLogger(__name__)

class MyPlaceIQDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching MyPlaceIQ data."""

    def __init__(self, hass: HomeAssistant, myplaceiq, update_interval: int):
        """Initialize the coordinator."""
        self.myplaceiq = myplaceiq
        self.hass = hass
        logger.debug(
            "Initializing MyPlaceIQDataUpdateCoordinator with update_interval: %s seconds",
                update_interval)
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Fetch data from MyPlaceIQ."""
        try:
            logger.debug("Fetching data from MyPlaceIQ")
            response = await self.myplaceiq.send_command(
                {"commands": [{"__type": "GetFullDataEvent"}]})
            if not isinstance(response, dict) or "body" not in response:
                logger.error("Invalid response from MyPlaceIQ: %s", response)
                raise ValueError("Invalid response from MyPlaceIQ")
            # Ensure body is a JSON string
            if isinstance(response["body"], dict):
                response["body"] = json.dumps(response["body"])
            logger.debug("Received data: %s", response)
            return response
        except Exception as err:
            logger.error("Error fetching data: %s", err)
            raise
