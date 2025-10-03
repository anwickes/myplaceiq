import json
import aiohttp
import random
import string
import logging
import socket
from aiohttp.client_exceptions import ClientConnectorError
from homeassistant.exceptions import HomeAssistantError

logger = logging.getLogger(__name__)

class MyPlaceIQ:
    """Class to handle WebSocket communication with MyPlaceIQ hub using aiohttp."""

    def __init__(self, hass, host: str, port: str, client_id: str, client_secret: str):
        self._hass = hass
        self._host = host
        self._port = port
        self._client_id = client_id
        self._client_secret = client_secret
        self._ws_url = f"ws://{host}:{port}/ws"
        logger.debug("Initialized MyPlaceIQ with URL: %s", self._ws_url)

    async def validate_connection(self):
        """Validate connection to the MyPlaceIQ hub."""
        logger.debug("Validating connection to %s", self._ws_url)
        try:
            socket.getaddrinfo(self._host, self._port)
        except socket.gaierror as err:
            logger.error("DNS resolution failed for %s: %s", self._host, err)
            raise HomeAssistantError(f"DNS resolution failed for {self._host}: {err}") from err
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    self._ws_url,
                    headers={"client_id": self._client_id, "password": self._client_secret},
                    ssl=False
                ) as ws:
                    logger.debug("WebSocket connection successful to %s", self._ws_url)
                    return True
        except ClientConnectorError as err:
            logger.error("Failed to connect to WebSocket %s: %s", self._ws_url, err)
            raise HomeAssistantError(f"Failed to connect to WebSocket: {err}") from err

    async def send_command(self, command: dict = {}):
        """Send command to iq hub via websocket."""
        logger.debug("Connecting to WebSocket at %s using command: %s", self._ws_url, command)
        session = None
        try:
            session = aiohttp.ClientSession()
            async with session.ws_connect(
                self._ws_url,
                headers={"client_id": self._client_id, "password": self._client_secret},
                ssl=False
            ) as ws:
                message = {
                    "uuid": "".join(random.choices(string.ascii_letters + string.digits, k=20)),
                    "body": json.dumps(command)
                }
                logger.debug("Sending command message: %s", message)
                await ws.send_str(json.dumps(message))
                response = await ws.receive()
                if response.type == aiohttp.WSMsgType.TEXT:
                    parsed_response = json.loads(response.data)
                    logger.debug("Received response: %s", parsed_response)
                    if not isinstance(parsed_response, dict):
                        logger.error("Invalid response type: %s", type(parsed_response))
                        return {}
                    return parsed_response
                else:
                    logger.error("Received non-text WebSocket message: %s", response.type)
                    raise HomeAssistantError(f"Invalid WebSocket message type: {response.type}")
        except ClientConnectorError as err:
            logger.error("WebSocket connection error: %s", err)
            raise HomeAssistantError(f"Failed to connect to WebSocket: {err}") from err
        except json.JSONDecodeError as err:
            logger.error("Failed to parse WebSocket response: %s", err)
            raise HomeAssistantError(f"Invalid response: {err}") from err
        except Exception as err:
            logger.error("Unexpected error in send_command: %s", err)
            raise HomeAssistantError(f"Error fetching data: {err}") from err
        finally:
            if session is not None:
                await session.close()
                logger.debug("WebSocket session closed")