"""WebSocket communication for MyPlaceIQ integration."""
import json
import logging
import random
import string
from typing import Dict, Any
import aiohttp
from aiohttp.client_exceptions import ClientConnectorError
from homeassistant.exceptions import HomeAssistantError

logger = logging.getLogger(__name__)

class MyPlaceIQ:
    """Class to handle WebSocket communication with MyPlaceIQ hub."""

    def __init__(self, hass, config: Dict[str, Any]):
        """Initialize the MyPlaceIQ client."""
        self._hass = hass
        self._host = config["host"]
        self._port = config["port"]
        self._client_id = config["client_id"]
        self._client_secret = config["client_secret"]
        self._ws_url = f"ws://{self._host}:{self._port}/ws"

    async def validate_connection(self) -> bool:
        """Validate connection to the MyPlaceIQ hub."""
        logger.debug("Validating connection to %s", self._ws_url)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    self._ws_url,
                    headers={"client_id": self._client_id, "password": self._client_secret},
                    ssl=False
                ):
                    return True
        except ClientConnectorError as err:
            logger.error("Failed to connect to WebSocket %s: %s", self._ws_url, err)
            raise HomeAssistantError(f"Failed to connect to WebSocket: {err}") from err

    async def send_command(self, command: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send command to MyPlaceIQ hub via WebSocket."""
        logger.debug("Sending command to %s: %s", self._ws_url, command)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(
                    self._ws_url,
                    headers={"client_id": self._client_id, "password": self._client_secret},
                    ssl=False
                ) as ws:
                    message = {
                        "uuid": "".join(random.choices(string.ascii_letters + string.digits, k=20)),
                        "body": json.dumps(command or {})
                    }
                    await ws.send_str(json.dumps(message))
                    response = await ws.receive()
                    if response.type != aiohttp.WSMsgType.TEXT:
                        logger.error("Received non-text WebSocket message: %s", response.type)
                        raise HomeAssistantError(f"Invalid WebSocket message type: {response.type}")
                    return json.loads(response.data)
            except (ClientConnectorError, json.JSONDecodeError) as err:
                logger.error("Error in WebSocket communication: %s", err)
                raise HomeAssistantError(f"WebSocket error: {err}") from err
