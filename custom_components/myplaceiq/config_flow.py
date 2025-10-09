import logging
from datetime import timedelta
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_POLL_INTERVAL
)

logger = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="x.x.x.x"): str,
    vol.Required(CONF_PORT, default=8086):
        vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    vol.Required(CONF_CLIENT_ID): str,
    vol.Required(CONF_CLIENT_SECRET): str,
    vol.Optional(CONF_POLL_INTERVAL, default=60):
        vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
})

class MyPlaceIQConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyPlaceIQ."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            logger.debug("Received user input for config flow: %s", user_input)
            try:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                client_id = user_input[CONF_CLIENT_ID]
                client_secret = user_input[CONF_CLIENT_SECRET]
                poll_interval = user_input.get(CONF_POLL_INTERVAL, 60)

                await self.async_set_unique_id(f"{DOMAIN}_{client_id}")
                self._abort_if_unique_id_configured()

                logger.debug("Creating config entry with poll_interval: %s", poll_interval)
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
            except Exception as err: # pylint: disable=broad-except
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
        logger.debug("Initializing options flow for config entry: %s", config_entry.entry_id)
        return MyPlaceIQOptionsFlow(config_entry)

class MyPlaceIQOptionsFlow(config_entries.OptionsFlow):
    """Handle MyPlaceIQ options flow."""

    def __init__(self, config_entry):
        """Initialize options flow with config_entry."""
        logger.debug("Initialized MyPlaceIQOptionsFlow for config entry: %s", config_entry.entry_id)

    async def async_step_init(self, user_input=None): # pylint: disable=too-many-locals
        """Manage the options."""
        errors = {}
        config_entry = self.hass.config_entries.async_get_entry(self._config_entry_id)
        if user_input is not None:
            logger.debug("Received options input: %s", user_input)
            try:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]
                client_id = user_input[CONF_CLIENT_ID]
                client_secret = user_input[CONF_CLIENT_SECRET]
                poll_interval = user_input.get(CONF_POLL_INTERVAL,
                    config_entry.options.get(CONF_POLL_INTERVAL, 60))

                # Validate inputs
                if not isinstance(poll_interval, int) or poll_interval < 10 or poll_interval > 300:
                    errors[CONF_POLL_INTERVAL] = "invalid_poll_interval"
                elif not isinstance(port, int) or port < 1 or port > 65535:
                    errors[CONF_PORT] = "invalid_port"
                else:
                    logger.debug("Updating config entry with new poll_interval: %s", poll_interval)
                    new_unique_id = f"{DOMAIN}_{client_id}"
                    if new_unique_id != config_entry.unique_id:
                        await self.hass.config_entries.async_set_unique_id(
                            config_entry.entry_id, new_unique_id)

                    # Update the config entry with a flag to skip reload
                    self.hass.config_entries.async_update_entry(
                        config_entry,
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_CLIENT_ID: client_id,
                            CONF_CLIENT_SECRET: client_secret,
                        },
                        options={
                            CONF_POLL_INTERVAL: poll_interval,
                            "_skip_reload": True,  # Flag to prevent reload
                        },
                    )

                    # Manually update the coordinator's update_interval
                    if config_entry.entry_id in self.hass.data.get(DOMAIN, {}):
                        coordinator = self.hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
                        coordinator.update_interval = timedelta(seconds=poll_interval)
                        await coordinator.async_refresh()
                        logger.debug("Updated coordinator update_interval to %s seconds",
                            poll_interval)

                    # Clear the skip_reload flag
                    self.hass.config_entries.async_update_entry(
                        config_entry,
                        options={
                            CONF_POLL_INTERVAL: poll_interval,
                            "_skip_reload": False,
                        },
                    )

                    logger.debug("Config entry updated successfully: %s", config_entry.options)
                    return self.async_create_entry(title="", data=None)
            except Exception as err: # pylint: disable=broad-except
                logger.error("Error during options flow: %s", err)
                errors["base"] = "unknown"

        current_host = config_entry.data.get(CONF_HOST, "x.x.x.x")
        current_port = config_entry.data.get(CONF_PORT, 8086)
        current_client_id = config_entry.data.get(CONF_CLIENT_ID, "")
        current_client_secret = config_entry.data.get(CONF_CLIENT_SECRET, "")
        current_poll_interval = config_entry.options.get(CONF_POLL_INTERVAL, 60)

        logger.debug("Showing options form with current poll_interval: %s", current_poll_interval)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Required(CONF_PORT, default=current_port):
                    vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(CONF_CLIENT_ID, default=current_client_id): str,
                vol.Required(CONF_CLIENT_SECRET, default=current_client_secret): str,
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll_interval):
                    vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            }),
            errors=errors,
        )
