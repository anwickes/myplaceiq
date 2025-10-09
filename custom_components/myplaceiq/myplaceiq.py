import json
import logging
import uuid
from typing import Any, Dict, Optional
import aiohttp
from homeassistant.core import HomeAssistant

logger = logging.getLogger(__name__)

class MyPlaceIQ:
    """Class to communicate with MyPlaceIQ API."""
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize MyPlaceIQ API client."""
        self.hass = hass
        self._url = f"ws://{host}:{port}/ws"
        self._client_id = client_id
        self._client_secret = client_secret
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        logger.debug("Initialized MyPlaceIQ with URL: %s", self._url)

    async def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send a command to MyPlaceIQ and return the response."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        try:
            logger.debug(
                "Connecting to WebSocket at %s using command: %s",
                self._url,
                command
            )
            async with self._session.ws_connect(
                self._url,
                headers={"client_id": self._client_id, "password": self._client_secret},
            ) as ws:
                self._ws = ws
                message = {
                    "uuid": str(uuid.uuid1()),
                    "body": json.dumps(command)
                }
                logger.debug("Sending command message: %s", message)
                await ws.send_json(message)
                response = await ws.receive_json()
                logger.debug("Received response: %s", response)
                return response
        except Exception as err:
            logger.error("Error sending command: %s", err)
            raise
        finally:
            await self.close()

    async def close(self) -> None:
        """Close the WebSocket connection and session."""
        try:
            if self._ws and not self._ws.closed:
                await self._ws.close()
                logger.debug("WebSocket session closed")
            if self._session and not self._session.closed:
                await self._session.close()
                logger.debug("Client session closed")
        except Exception as err: # pylint: disable=broad-except
            logger.error("Error closing WebSocket or session: %s", err)
        finally:
            self._ws = None
            self._session = None
