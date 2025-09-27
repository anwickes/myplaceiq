import json
import websockets
import random
import string
from homeassistant.exceptions import HomeAssistantError

class MyPlaceIQ:
    """Class to handle WebSocket communication with MyPlaceIQ hub."""

    def __init__(self, host: str, client_id: str, client_secret: str):
        self._host = host
        self._client_id = client_id
        self._client_secret = client_secret
        self._ws_url = f"ws://{host}/ws"

    async def connect(self):
        """Establish a WebSocket connection with authentication headers."""
        try:
            headers = {
                "client_id": self._client_id,
                "password": self._client_secret
            }
            return await websockets.connect(self._ws_url, extra_headers=headers, ping_interval=None)
        except websockets.exceptions.WebSocketException as err:
            raise HomeAssistantError(f"Failed to connect to WebSocket: {err}")

    async def send_command(self, command: dict={}):
        """Fetch system and zone data from the hub."""
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
