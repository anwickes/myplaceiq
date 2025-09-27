import json
import websockets
import random
import string
from homeassistant.exceptions import HomeAssistantError
from websockets.client import WebSocketClientProtocol

class MyPlaceIQ:
    """Class to handle WebSocket communication with MyPlaceIQ hub."""

    def __init__(self, host: str, port: str, client_id: str, client_secret: str):
        self._host = host
        self._client_id = client_id
        self._client_secret = client_secret
        self._ws_url = 'ws://{}:{}/ws'.format(host, port)

    async def connect(self):
        """Establish a WebSocket connection with authentication headers."""
        try:
            # Define custom protocol to include headers
            async def custom_connect(uri):
                headers = {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret
                }
                return await websockets.client.connect(uri, extra_headers=headers, ping_interval=None)
                # For older websockets versions, we avoid extra_headers and handle manually if needed
                # Note: Older versions may still support headers via WebSocketClientProtocol
            return await custom_connect(self._ws_url)
        except websockets.exceptions.WebSocketException as err:
            raise HomeAssistantError(f"Failed to connect to WebSocket: {err}")

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
            
            raise HomeAssistantError(f"Error fetching data: {err}")
