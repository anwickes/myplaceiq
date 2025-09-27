import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import CONF_HOST, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, CONF_POLL_INTERVAL
from .myplaceiq import MyPlaceIQ

class MyPlaceIQConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyPlaceIQ."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Validate WebSocket connection
            try:
                myplaceiq = MyPlaceIQ(
                    user_input[CONF_HOST],
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                )
                await myplaceiq.send_command(
                    {
                        {"commands": [{"__type": "GetFullDataEvent"}]}
                    }
                )
                return self.async_create_entry(
                    title=f"MyPlaceIQ Hub ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            except HomeAssistantError as err:
                errors["base"] = "cannot_connect" if "connect" in str(err) else "invalid_auth"

        # Show the form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_HOST, default='imx6ul-redgum.local'): str,
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Optional(CONF_POLL_INTERVAL, default=60): int,
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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=self.config_entry.options.get(CONF_POLL_INTERVAL, 60),
                    ): int
                }
            ),
        )