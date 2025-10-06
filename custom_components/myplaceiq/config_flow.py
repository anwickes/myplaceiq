"""Config flow for MyPlaceIQ integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from aiohttp.client_exceptions import ClientConnectorError
from .const import (
    DOMAIN, CONF_HOST, CONF_PORT, CONF_CLIENT_ID,
    CONF_CLIENT_SECRET, CONF_POLL_INTERVAL
)
from .myplaceiq import MyPlaceIQ

logger = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="x.x.x.x"): str,
    vol.Required(CONF_PORT, default=8086): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=65535)
    ),
    vol.Required(CONF_CLIENT_ID): str,
    vol.Required(CONF_CLIENT_SECRET): str,
    vol.Optional(CONF_POLL_INTERVAL, default=60): vol.All(
        vol.Coerce(int), vol.Range(min=10, max=300)
    ),
})

class MyPlaceIQConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyPlaceIQ."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                myplaceiq = MyPlaceIQ(
                    self.hass,
                    {
                        "host": user_input[CONF_HOST],
                        "port": user_input[CONF_PORT],
                        "client_id": user_input[CONF_CLIENT_ID],
                        "client_secret": user_input[CONF_CLIENT_SECRET]
                    }
                )
                await myplaceiq.validate_connection()
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_CLIENT_ID]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"MyPlaceIQ {user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                    options={CONF_POLL_INTERVAL: user_input.get(CONF_POLL_INTERVAL, 60)}
                )
            except ClientConnectorError as err:
                logger.error("Connection error during config flow: %s", err)
                errors["base"] = "cannot_connect"
            except ValueError as err:
                logger.error("Invalid input during config flow: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MyPlaceIQOptionsFlow(config_entry)

class MyPlaceIQOptionsFlow(config_entries.OptionsFlow):
    """Handle MyPlaceIQ options flow."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            try:
                port = user_input[CONF_PORT]
                poll_interval = user_input.get(
                    CONF_POLL_INTERVAL,
                    self.config_entry.options.get(CONF_POLL_INTERVAL, 60)
                )
                if not isinstance(poll_interval, int) or poll_interval < 10 or poll_interval > 300:
                    errors[CONF_POLL_INTERVAL] = "invalid_poll_interval"
                elif not isinstance(port, int) or port < 1 or port > 65535:
                    errors[CONF_PORT] = "invalid_port"
                else:
                    new_unique_id = f"{DOMAIN}_{user_input[CONF_CLIENT_ID]}"
                    if new_unique_id != self.config_entry.unique_id:
                        await self.hass.config_entries.async_set_unique_id(
                            self.config_entry.entry_id, new_unique_id
                        )
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=user_input,
                        options={CONF_POLL_INTERVAL: poll_interval}
                    )
                    return self.async_create_entry(title="", data={})
            except ClientConnectorError as err:
                logger.error("Connection error during options flow: %s", err)
                errors["base"] = "cannot_connect"
            except ValueError as err:
                logger.error("Invalid input during options flow: %s", err)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_HOST,
                    default=self.config_entry.data.get(CONF_HOST, "x.x.x.x")
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self.config_entry.data.get(CONF_PORT, 8086)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_CLIENT_ID,
                    default=self.config_entry.data.get(CONF_CLIENT_ID, "")
                ): str,
                vol.Required(
                    CONF_CLIENT_SECRET,
                    default=self.config_entry.data.get(CONF_CLIENT_SECRET, "")
                ): str,
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=self.config_entry.options.get(CONF_POLL_INTERVAL, 60)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }),
            errors=errors
        )
