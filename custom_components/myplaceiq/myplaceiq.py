import json
import logging
import uuid
import asyncio
import aiohttp
from homeassistant.exceptions import HomeAssistantError

logger = logging.getLogger(__name__)

# Confirmed by packet capture: the hub forcibly closes every WebSocket
# connection roughly 20 seconds after it was opened, regardless of
# activity. This is routine hub behavior, not a fault - reconnecting is
# the expected response, not an error path.
HUB_CONNECTION_LIFETIME_HINT = 20

class MyPlaceIQ:
    """Class to communicate with MyPlaceIQ API.

    Only GetFullDataEvent commands carry a client-generated "replyUuid",
    which the hub echoes back as the outer "uuid" of the matching reply -
    that's the only way to tell "the answer to my request" apart from
    "an unrelated push that happened to arrive around the same time".
    Set* commands have no such correlation; we rely on the fact that the
    hub broadcasts a confirming push within well under a second of a
    command actually taking effect (observed consistently in captures),
    which the coordinator merges into its cached state as it arrives.
    """

    def __init__(self, host: str, port: int, client_id: str, client_secret: str) -> None:
        """Initialize MyPlaceIQ API client."""
        self._url = f"ws://{host}:{port}/ws"
        self._client_id = client_id
        self._client_secret = client_secret
        # Serializes connect+send onto a single connection. The hub is a
        # local embedded controller that cannot reliably handle several
        # concurrent WebSocket sessions; firing commands for many entities
        # at once (e.g. a scene-runner script targeting several climate
        # entities) previously opened one new socket per command, and the
        # hub would silently drop some of them under load.
        self._lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reader_task: asyncio.Task | None = None
        # replyUuid -> Future, resolved by the reader loop when a reply
        # with a matching outer "uuid" arrives.
        self._pending_replies: dict[str, asyncio.Future] = {}
        # Called with the parsed body of every message that is NOT a
        # correlated reply - i.e. every unsolicited push from the hub.
        self._push_callback = None
        logger.debug("Initialized MyPlaceIQ with URL: %s", self._url)

    def set_push_callback(self, callback) -> None:
        """Register a callback invoked with the parsed body of every unsolicited push."""
        self._push_callback = callback

    async def _ensure_connected(self) -> aiohttp.ClientWebSocketResponse:
        """Return an open WebSocket, reconnecting if needed. Caller must hold self._lock."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        if self._ws is None or self._ws.closed:
            headers = {"client_id": self._client_id, "password": self._client_secret}
            logger.debug("Connecting to WebSocket at %s", self._url)
            self._ws = await self._session.ws_connect(self._url, headers=headers, timeout=5)
            if self._reader_task and not self._reader_task.done():
                self._reader_task.cancel()
            self._reader_task = asyncio.create_task(self._reader_loop(self._ws))
        return self._ws

    async def _reader_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Continuously drain one connection for as long as it lives.

        Every incoming message either resolves a pending GetFullDataEvent
        reply (matched by replyUuid) or is handed to the push callback as
        an unsolicited delta.
        """
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        outer = json.loads(msg.data)
                        body = json.loads(outer.get("body", "{}"))
                    except (json.JSONDecodeError, TypeError) as err:
                        logger.warning("Failed to parse incoming WebSocket message: %s", err)
                        continue
                    reply_uuid = outer.get("uuid")
                    fut = self._pending_replies.pop(reply_uuid, None) if reply_uuid else None
                    if fut is not None:
                        if not fut.done():
                            # Resolve with the raw envelope (outer), not the
                            # already-parsed body - send_command()'s callers
                            # (coordinator._async_update_data) expect the
                            # same {"uuid": ..., "body": "<json string>"}
                            # shape ws.receive_json() used to return, and
                            # do their own json.loads(response["body"]).
                            # Resolving with the parsed body here (as
                            # originally shipped) left response with no
                            # "body" key at all, tripping the "Invalid
                            # response from MyPlaceIQ" check on every poll.
                            fut.set_result(outer)
                    elif self._push_callback is not None:
                        try:
                            self._push_callback(body)
                        except Exception:  # pylint: disable=broad-except
                            logger.exception("Error handling unsolicited MyPlaceIQ push")
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.ERROR,
                ):
                    logger.debug("WebSocket closing (type=%s); reader loop exiting", msg.type)
                    break
        except asyncio.CancelledError:
            raise
        except (aiohttp.ClientError, ConnectionResetError) as err:
            logger.debug("Reader loop ended due to connection error: %s", err)
        finally:
            # The hub closes every connection after roughly
            # HUB_CONNECTION_LIFETIME_HINT seconds regardless of activity -
            # this is routine, not an error. Mark the connection dead so
            # the next send_command() call reconnects, and fail any reply
            # we were still waiting on rather than hanging forever.
            self._ws = None
            for fut in self._pending_replies.values():
                if not fut.done():
                    fut.set_exception(HomeAssistantError("Connection closed before reply received"))
            self._pending_replies.clear()

    async def _close(self) -> None:
        """Close the current connection. Caller must hold self._lock."""
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
                pass
        self._reader_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
            logger.debug("WebSocket closed")
        self._ws = None
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Client session closed")
        self._session = None
        for fut in self._pending_replies.values():
            if not fut.done():
                fut.set_exception(HomeAssistantError("Connection closed"))
        self._pending_replies.clear()

    async def async_close(self) -> None:
        """Close the connection, e.g. on integration unload."""
        async with self._lock:
            await self._close()

    async def send_command(self, command: dict, await_response: bool = False) -> dict:
        """Send a command to MyPlaceIQ, optionally awaiting a correlated response.

        Connect+send is serialized through self._lock so that a burst of
        entity updates reaches the hub one at a time over a single reused
        connection. The wait for a reply (when await_response is True) 
        happens outside the lock so other commands can still be sent while 
        we wait.
        """
        reply_uuid = None
        if await_response:
            reply_uuid = str(uuid.uuid1())
            command = json.loads(json.dumps(command))  # cheap deep copy before mutating
            if command.get("commands"):
                command["commands"][0]["replyUuid"] = reply_uuid

        message = {"uuid": str(uuid.uuid1()), "body": json.dumps(command)}
        logger.debug("Sending command message: %s (await_response: %s)", message, await_response)
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                async with self._lock:
                    ws = await self._ensure_connected()
                    fut = None
                    if await_response:
                        fut = asyncio.get_running_loop().create_future()
                        self._pending_replies[reply_uuid] = fut
                    logger.debug("Attempt %d/%d: sending on WebSocket at %s",
                        attempt, max_retries, self._url)
                    await ws.send_json(message)
                    logger.debug("Attempt %d/%d: command sent successfully", attempt, max_retries)

                if not await_response:
                    return {"status": "sent"}

                try:
                    response = await asyncio.wait_for(fut, timeout=10)
                except asyncio.TimeoutError as err:
                    self._pending_replies.pop(reply_uuid, None)
                    raise HomeAssistantError(
                        f"Timed out waiting for MyPlaceIQ reply (replyUuid={reply_uuid})"
                    ) from err
                logger.debug("Attempt %d/%d: received correlated response", attempt, max_retries)
                return response

            except (aiohttp.ClientError, aiohttp.WSMessageTypeError, HomeAssistantError) as err:
                logger.error("Attempt %d/%d: error sending command or receiving response: %s",
                             attempt, max_retries, err)
                # Connection may be in a bad state (or was just the hub's
                # routine ~20s close) - drop it so the next attempt
                # reconnects cleanly and gets a fresh full resync.
                async with self._lock:
                    await self._close()
                if attempt < max_retries:
                    logger.debug("Retrying after 1-second delay")
                    await asyncio.sleep(1)
                    continue
                raise HomeAssistantError(
                    f"Failed to send MyPlaceIQ command after {max_retries} attempts: {err}"
                ) from err

        raise HomeAssistantError(
            f"Failed to send MyPlaceIQ command after {max_retries} attempts")
