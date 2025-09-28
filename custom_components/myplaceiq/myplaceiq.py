import json
import websockets
import random
import string
import logging
from homeassistant.exceptions import HomeAssistantError
from websockets.client import WebSocketClientProtocol

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MyPlaceIQ:
    """Class to handle WebSocket communication with MyPlaceIQ hub."""

    def __init__(self, host: str, port: str, client_id: str, client_secret: str):
        self._host = host
        self._client_id = client_id
        self._client_secret = client_secret
        self._ws_url = 'ws://{}:{}/ws'.format(host, port)
        logger.debug("Initialized MyPlaceIQ with URL: {}".format(self._ws_url))

    async def connect(self):
        """Establish a WebSocket connection with authentication headers."""
        try:
            # Define custom protocol to include headers
            async def custom_connect(uri):
                headers = {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret
                }
                logger.info('testing')
                return await websockets.client.connect(uri, extra_headers=headers, ping_interval=None)
                # For older websockets versions, we avoid extra_headers and handle manually if needed
                # Note: Older versions may still support headers via WebSocketClientProtocol
            logger.info('testing2')
            return await custom_connect(self._ws_url)
        except websockets.exceptions.WebSocketException as err:
            raise HomeAssistantError(f"Failed to connect to WebSocket: {err}")

    async def connect(self):
        """Establish a WebSocket connection with authentication headers."""
        logger.debug("Attempting to connect to WebSocket: {} with headers client_id={}".format(self._ws_url, self._client_id))
        try:
            headers = {
                "client_id": self._client_id,
                "client_secret": self._client_secret
            }
            return await websockets.connect(self._ws_url, extra_headers=headers, ping_interval=None)
        except websockets.exceptions.WebSocketException as err:
            logger.error("WebSocket connection failed: {}".format(err))
            raise HomeAssistantError("Failed to connect to WebSocket: {}".format(err)) from err
        except OSError as err:
            logger.error("OS error during WebSocket connection: {}".format(err))
            raise HomeAssistantError("OS error during WebSocket connection: {}".format(err)) from err

    async def send_command(self, command: dict={}):
        """Send command to iq hub via websocket."""
        try:
            async with await self.connect() as ws:
                await ws.send(
                    json.dumps(
                        {
                            "uuid": ''.join(random.choices(string.ascii_letters + string.digits, k=20)),
                            "body": json.dumps(command)
                        }
                    )
                )
                response = json.loads(await ws.recv())
                if "system" not in response or "zones" not in response:
                    raise HomeAssistantError("Invalid response from hub")
                return response
        except (websockets.exceptions.WebSocketException, json.JSONDecodeError) as err:
            logger.info('testing3')
            raise HomeAssistantError(f"Error fetching data: {err}")

    async def send_command(self, command: dict = {}):
        """Send command to iq hub via websocket."""
        ws = None
        try:
            ws = await self.connect()
            logger.debug("Sending command to hub: {}".format(command))
            await ws.send(
                json.dumps(
                    {
                        "uuid": "".join(random.choices(string.ascii_letters + string.digits, k=20)),
                        "body": json.dumps(command)
                    }
                )
            )
            response = json.loads(await ws.recv())
            if "system" not in response or "zones" not in response:
                logger.error("Invalid response from hub: {}".format(response))
                raise HomeAssistantError("Invalid response from hub")
            logger.debug("Received data: {}".format(response))
            return response
        except (websockets.exceptions.WebSocketException, json.JSONDecodeError) as err:
            logger.error("Error fetching data: {}".format(err))
            raise HomeAssistantError("Error fetching data: {}".format(err)) from err
        finally:
            if ws is not None:
                await ws.close()
                logger.debug("WebSocket connection closed")
