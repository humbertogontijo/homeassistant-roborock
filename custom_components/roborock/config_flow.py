"""Config flow for yeelight_bt"""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from custom_components.roborock.api.api import RoborockClient
from .const import CONF_ENTRY_USERNAME, DOMAIN, PLATFORMS, CONF_ENTRY_CODE, CONF_USER_DATA, CONF_BASE_URL

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Roborock."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._client = None
        self._username = None
        self._base_url = None

    async def async_step_reauth(self, user_input=None):
        await self.hass.config_entries.async_remove(self.context["entry_id"])
        return await self._show_user_form(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input:
            self._username = user_input[CONF_ENTRY_USERNAME]
            await self.async_set_unique_id(self._username)
            self._abort_if_unique_id_configured()
            client = await self._request_code()
            if client:
                self._client = client
                self._base_url = client.base_url
                user_input[CONF_ENTRY_CODE] = ""
                return await self._show_code_form(user_input)
            else:
                self._errors["base"] = "auth"

            return await self._show_user_form(user_input)

        # Provide defaults for form
        user_input = {CONF_ENTRY_USERNAME: ""}

        return await self._show_user_form(user_input)

    async def async_step_code(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input:
            code = user_input[CONF_ENTRY_CODE]
            login_data = await self._login(code)
            if login_data:
                return self.async_create_entry(title="Roborock", data={
                    CONF_ENTRY_USERNAME: self._username,
                    CONF_USER_DATA: login_data,
                    CONF_BASE_URL: self._base_url
                })
            else:
                self._errors["base"] = "no_device"

            return await self._show_code_form(user_input)

        # Provide defaults for form
        user_input = {CONF_ENTRY_CODE: ""}

        return await self._show_code_form(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RoborockOptionsFlowHandler(config_entry)

    async def _show_user_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_USERNAME, default=user_input[CONF_ENTRY_USERNAME]
                    ): str
                }
            ),
            errors=self._errors,
        )

    async def _show_code_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_CODE, default=user_input[CONF_ENTRY_CODE]
                    ): str
                }
            ),
            errors=self._errors,
        )

    async def _request_code(self):
        """Return true if credentials is valid."""
        try:
            _LOGGER.debug("Requesting code for Roborock account")
            client = RoborockClient(self._username)
            await client.request_code()
            return client
        except Exception as e:
            _LOGGER.exception(e)
            self._errors["base"] = "auth"
            return None

    async def _login(self, code):
        """Return true if credentials is valid."""
        try:
            _LOGGER.debug("Requesting code for Roborock account")
            login_data = await self._client.code_login(code)
            return login_data
        except Exception as e:
            _LOGGER.exception(e)
            self._errors["base"] = "auth"
            return None


class RoborockOptionsFlowHandler(config_entries.OptionsFlow):
    """Roborock config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(x, default=self.options.get(x, True)): bool
                    for x in sorted(PLATFORMS)
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)
