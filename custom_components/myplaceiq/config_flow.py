import voluptuous as vol
import socket
from homeassistant import config_entries
from homeassistant.core import callback
import logging

from .const import DOMAIN, CONF_HOST, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_POLL_INTERVAL

logger = logging.getLogger(__name__)

class MyPlaceIQConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyPlaceIQ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Validate that the host resolves to an IP address
            try:
                # Use socket.getaddrinfo to resolve the hostname
                await self.hass.async_add_executor_job(
                    socket.getaddrinfo, user_input[CONF_HOST], None
                )
            except socket.gaierror:
                errors["base"] = "cannot_resolve_host"
            except Exception as err:
                logger.error("Unexpected error resolving host %s: %s", user_input[CONF_HOST], err)
                errors["base"] = "unknown"
            else:
                # Defer WebSocket validation to runtime
                return self.async_create_entry(
                    title=f"MyPlaceIQ {user_input[CONF_HOST]}",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                        CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET],
                        CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default="imx6ul-redgum.local"): str,
                    vol.Required(CONF_PORT, default="8086"): str,
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_POLL_INTERVAL, default=60): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MyPlaceIQOptionsFlow(config_entry)

class MyPlaceIQOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for MyPlaceIQ."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage device options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=self._config_entry.data.get(CONF_POLL_INTERVAL, 60),
                    ): int
                }
            ),
        )