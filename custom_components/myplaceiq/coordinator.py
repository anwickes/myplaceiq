import logging
import json
import time
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN

logger = logging.getLogger(__name__)

# How long to wait, after the *last* post-command refresh request, before
# actually polling. This is now a backstop rather than the primary
# confirmation path (see _handle_push below) - kept in case a push is
# ever dropped - so a generous cooldown is fine.
POST_COMMAND_REFRESH_COOLDOWN = 3


def _deep_merge(dst: dict, src: dict) -> dict:
    """Recursively merge src into dst in place, and return dst.

    MyPlaceIQ's push messages are partial - they only ever contain the
    fields that actually changed - so anything src doesn't mention must be
    left exactly as it was in dst. Nested dicts are merged key by key;
    any other value (including lists) in src replaces the corresponding
    value in dst outright, since there's no meaningful per-element merge
    for e.g. a list of allowed modes.
    """
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value
    return dst


class MyPlaceIQDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching MyPlaceIQ data."""

    def __init__(self, hass: HomeAssistant, myplaceiq, update_interval: int):
        """Initialize the coordinator."""
        self.myplaceiq = myplaceiq
        self.hass = hass
        self._last_valid_data = None
        # Canonical cached full state body, kept current by merging every
        # unsolicited push on top of it. None until the first successful
        # GetFullDataEvent poll completes - a partial push on its own is
        # never safe to treat as if it were the whole state.
        self._body: dict | None = None
        logger.debug("Initializing MyPlaceIQDataUpdateCoordinator with update_interval: %s seconds",
                     update_interval)
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self._post_command_debouncer = Debouncer(
            hass,
            logger,
            cooldown=POST_COMMAND_REFRESH_COOLDOWN,
            immediate=False,
            function=self.async_refresh,
        )
        # The hub streams a live delta to every open connection whenever
        # anything changes, independent of polling. Without this wired
        # up, nothing ever reads those pushes and HA only ever learns
        # about a change at its next scheduled poll
        self.myplaceiq.set_push_callback(self._handle_push)

    def _handle_push(self, body: dict) -> None:
        """Handle an unsolicited push from the hub (called from the reader task).

        Merges the partial delta into our cached full body and publishes
        it immediately via async_set_updated_data, instead of waiting for
        the next scheduled poll to notice.
        """
        if self._body is None:
            logger.debug("Ignoring push received before initial full sync: keys=%s",
                         list(body.keys()))
            return
        _deep_merge(self._body, body)
        self._publish_body()

    def _publish_body(self) -> None:
        """Publish the current merged body as the coordinator's data."""
        response = dict(self._last_valid_data or {})
        response["body"] = json.dumps(self._body)
        self._last_valid_data = response
        self.async_set_updated_data(response)

    def apply_local_update(self, updater) -> None:
        """Optimistically change the cached state and publish it immediately.

        updater is called with the canonical cached body (a dict) and may
        mutate it in place. This lets an entity reflect a command it has
        just sent without waiting for the hub's confirming push, which
        then overwrites/confirms the value through the normal merge path.
        Does nothing before the first full sync, for the same reason
        _handle_push ignores early pushes.
        """
        if self._body is None:
            return
        updater(self._body)
        self._publish_body()

    async def async_request_refresh_after_command(self):
        """Request a refresh after an entity sends a set_* command.

        This is a backstop, not the primary confirmation path: the
        hub's own push for the command we just sent normally arrives
        (and is merged via _handle_push) within well under a second.
        Debounced (trailing-edge, not immediate) so a burst of several
        entities each calling this collapses into a single poll fired
        after the *last* call, in case a push was ever dropped.
        """
        await self._post_command_debouncer.async_call()

    async def _async_update_data(self):
        """Fetch a full, authoritative snapshot from MyPlaceIQ."""
        start_time = time.time()
        logger.debug("Poll started at %s (interval: %s seconds)",
                     time.strftime("%H:%M:%S", time.localtime(start_time)),
                     self.update_interval.total_seconds())
        try:
            response = await self.myplaceiq.send_command(
                {"commands": [{"__type": "GetFullDataEvent"}]}, await_response=True)
            if not isinstance(response, dict) or "body" not in response:
                logger.error("Invalid response from MyPlaceIQ: %s", response)
                raise UpdateFailed("Invalid response from MyPlaceIQ")

            try:
                body = json.loads(response["body"])
            except json.JSONDecodeError as err:
                logger.error("Failed to parse response body: %s", err)
                raise UpdateFailed(f"Failed to parse response body: {err}") from err

            if not body.get("aircons") or not body.get("zones"):
                logger.warning("Incomplete response missing aircons or zones")
                if self._last_valid_data:
                    logger.debug("Using last valid data")
                    return self._last_valid_data
                raise UpdateFailed("Incomplete response and no valid cached data")

            # Log summary instead of full response
            aircons = body.get("aircons", {})
            logger.debug("Poll completed in %.3f seconds: %d aircon(s) [%s], zones=%d",
                         time.time() - start_time,
                         len(aircons),
                         ", ".join(
                             f"{aircon_id}: isOn={aircon.get('isOn', 'missing')}, "
                             f"mode={aircon.get('mode', 'missing')}"
                             for aircon_id, aircon in aircons.items()
                         ),
                         len(body.get("zones", {})))

            # GetFullDataEvent replies are always complete snapshots - this
            # is confirmed via replyUuid correlation in MyPlaceIQ, so it's
            # safe to wholesale-replace our cached body here (unlike a
            # push, which only ever merges partially - see _handle_push).
            self._body = body
            response["body"] = json.dumps(body)
            self._last_valid_data = response
            return response
        except Exception as err:
            logger.error("Poll failed in %.3f seconds: %s", time.time() - start_time, err)
            if self._last_valid_data:
                logger.debug("Returning last valid data")
                return self._last_valid_data
            raise UpdateFailed(f"Error fetching MyPlaceIQ data: {err}") from err
