import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import logging
from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_POLL_INTERVAL

logger = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="192.168.1.171"): str,
    vol.Required(CONF_PORT, default=8086): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    vol.Required(CONF_CLIENT_ID): str,
    vol.Required(CONF_CLIENT_SECRET): str,
    vol.Optional(CONF_POLL_INTERVAL, default=60): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
})

class MyPlaceIQConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyPlaceIQ."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            logger.debug("Received user input: %s", user_input)
            try:
                # Validate input
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                client_id = user_input[CONF_CLIENT_ID]
                client_secret = user_input[CONF_CLIENT_SECRET]
                poll_interval = user_input.get(CONF_POLL_INTERVAL, 60)

                # Test connection (optional, can be implemented if MyPlaceIQ supports a test endpoint)
                await self.async_set_unique_id(f"{DOMAIN}_{client_id}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"MyPlaceIQ {host}:{port}",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_SECRET: client_secret,
                    },
                    options={
                        CONF_POLL_INTERVAL: poll_interval,
                    },
                )
            except Exception as err:
                logger.error("Error during config flow: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        try:
            logger.debug("Initializing options flow for config entry: %s", config_entry.entry_id)
            return MyPlaceIQOptionsFlow(config_entry)
        except Exception as err:
            logger.error("Failed to initialize options flow: %s", err)
            raise

class MyPlaceIQOptionsFlow(config_entries.OptionsFlow):
    """Handle MyPlaceIQ options flow."""

    def __init__(self, config_entry):
        """Initialize options flow with config_entry."""
        self.config_entry = config_entry
        logger.debug("Initialized MyPlaceIQOptionsFlow for config entry: %s", config_entry.entry_id)

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is not None:
            try:
                logger.debug("Received options input: %s", user_input)
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                client_id = user_input[CONF_CLIENT_ID]
                client_secret = user_input[CONF_CLIENT_SECRET]
                poll_interval = user_input.get(CONF_POLL_INTERVAL, self.config_entry.options.get(CONF_POLL_INTERVAL, 60))

                # Validate inputs
                if not isinstance(poll_interval, int) or poll_interval < 10 or poll_interval > 300:
                    errors[CONF_POLL_INTERVAL] = "invalid_poll_interval"
                elif not isinstance(port, int) or port < 1 or port > 65535:
                    errors[CONF_PORT] = "invalid_port"
                else:
                    # Update unique_id if client_id changed
                    new_unique_id = f"{DOMAIN}_{client_id}"
                    if new_unique_id != self.config_entry.unique_id:
                        await self.hass.config_entries.async_set_unique_id(self.config_entry.entry_id, new_unique_id)
                    
                    # Update entry.data and entry.options
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_CLIENT_ID: client_id,
                            CONF_CLIENT_SECRET: client_secret,
                        },
                        options={
                            CONF_POLL_INTERVAL: poll_interval,
                        },
                    )
                    return self.async_create_entry(title="", data={})
            except Exception as err:
                logger.error("Error during options flow: %s", err)
                errors["base"] = "unknown"

        # Initialize defaults from current config entry
        current_host = self.config_entry.data.get(CONF_HOST, "192.168.1.100")
        current_port = self.config_entry.data.get(CONF_PORT, 8086)
        current_client_id = self.config_entry.data.get(CONF_CLIENT_ID, "")
        current_client_secret = self.config_entry.data.get(CONF_CLIENT_SECRET, "")
        current_poll_interval = self.config_entry.options.get(CONF_POLL_INTERVAL, 60)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Required(CONF_PORT, default=current_port): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(CONF_CLIENT_ID, default=current_client_id): str,
                vol.Required(CONF_CLIENT_SECRET, default=current_client_secret): str,
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll_interval): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }),
            errors=errors,
        )