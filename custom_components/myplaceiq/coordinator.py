"""Data update coordinator for MyPlaceIQ integration."""
import json
import logging
from datetime import timedelta
from typing import Dict, Any
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import DOMAIN
from .utils import parse_coordinator_data

logger = logging.getLogger(__name__)

class MyPlaceIQDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching MyPlaceIQ data."""

    def __init__(self, hass: HomeAssistant, myplaceiq, update_interval: int):
        """Initialize the coordinator."""
        if not isinstance(update_interval, int) or update_interval < 10 or update_interval > 300:
            raise ValueError("Update interval must be between 10 and 300 seconds")
        self.myplaceiq = myplaceiq
        self.hass = hass
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval)
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from MyPlaceIQ."""
        logger.debug("Fetching data from MyPlaceIQ")
        response = await self.myplaceiq.send_command({
            "commands": [{"__type": "GetFullDataEvent"}]
        })
        body = parse_coordinator_data({"body": response.get("body", {})})
        if not body:
            raise ValueError("Invalid response from MyPlaceIQ")
        return {"body": json.dumps(body)}
