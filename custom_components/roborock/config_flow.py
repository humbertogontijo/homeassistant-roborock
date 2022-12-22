"""Config flow for yeelight_bt"""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api import RoborockClient
from .const import CONF_ENTRY_USERNAME, DOMAIN, PLATFORMS, CONF_ENTRY_CODE

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Roborock."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._client = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            username = user_input[CONF_ENTRY_USERNAME]
            client = await self._request_code(
                username
            )
            if client:
                self._client = client
                user_input[CONF_ENTRY_CODE] = ""
                return await self._show_code_form(user_input)
            else:
                self._errors["base"] = "auth"

            return await self._show_user_form(user_input)

        user_input = {}
        # Provide defaults for form
        user_input[CONF_ENTRY_USERNAME] = ""

        return await self._show_user_form(user_input)

    async def async_step_code(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            code = user_input[CONF_ENTRY_CODE]
            login_data = await self._login(
                code
            )
            if login_data:
                return self.async_create_entry(
                    title="Roborock",
                    data=login_data
                )
            else:
                self._errors["base"] = "no_device"

            return await self._show_code_form(user_input)

        user_input = {}
        # Provide defaults for form
        user_input[CONF_ENTRY_CODE] = ""

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

    async def _request_code(self, username):
        """Return true if credentials is valid."""
        try:
            _LOGGER.debug("Requesting code for Roborock account")
            client = RoborockClient(username)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                client.request_code,
            )
            return client
        except:
            self._errors["base"] = "auth"
            return None

    async def _login(self, code):
        """Return true if credentials is valid."""
        try:
            _LOGGER.debug("Requesting code for Roborock account")
            loop = asyncio.get_running_loop()
            login_data = await loop.run_in_executor(
                None,
                self._client.code_login,
                code
            )
            return login_data
        except:
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
        if user_input is not None:
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
        return self.async_create_entry(
            title="", data=self.options
        )
