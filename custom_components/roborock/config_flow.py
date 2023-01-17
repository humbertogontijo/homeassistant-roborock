"""Config flow for Roborock."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api.api import RoborockClient
from .api.containers import UserData
from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_CODE,
    CONF_ENTRY_USERNAME,
    CONF_USER_DATA,
    CONF_INCLUDE_SHARED,
    CONF_SCALE,
    CONF_ROTATE,
    CONF_TRIM,
    CONF_MAP_TRANSFORM,
    CONF_LEFT,
    CONF_RIGHT,
    CONF_TOP,
    CONF_BOTTOM,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._errors = {}
        self._client = None
        self._username = None
        self._base_url = None

    async def async_step_reauth(self, user_input=None):
        """Handle a reauth flow."""
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
                return self.async_create_entry(title=self._username, data={
                    CONF_ENTRY_USERNAME: self._username,
                    CONF_USER_DATA: login_data.data,
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
        """Show the configuration form to provide user email."""
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
        """Show the configuration form to provide authentication code."""
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
        except Exception as ex:
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return None

    async def _login(self, code) -> UserData:
        """Return UserData if login code is valid."""
        try:
            _LOGGER.debug("Logging into Roborock account using email provided code")
            login_data = await self._client.code_login(code)
            return login_data
        except Exception as ex:
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return


PERCENT_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
POSITIVE_FLOAT_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0))
ROTATION_SCHEMA = vol.In(["0", "90", "180", "270"])


def set_nested_dict(data: dict, key_string: str, value):
    """Set nested dict."""
    here = data
    keys = key_string.split(".")
    for key in keys[:-1]:
        here = here.setdefault(key, {})
    here[keys[-1]] = value


def get_nested_dict(data: dict, key_string: str, default=None):
    """Get nested dict."""
    here = data
    keys = key_string.split(".")
    for key in keys:
        here = here.get(key)
        # Check for None type since CONF_INCLUDE_SHARED can return False
        if here is None:
            return default
    return here


CAMERA_OPTIONS = {
    f"{CONF_MAP_TRANSFORM}.{CONF_SCALE}": {
        "store_type": float,
        "show_type": float,
        "default": 1,
        "schema": POSITIVE_FLOAT_SCHEMA
    },
    f"{CONF_MAP_TRANSFORM}.{CONF_ROTATE}": {
        "store_type": int,
        "show_type": str,
        "default": 0,
        "schema": ROTATION_SCHEMA
    },
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_LEFT}": {
        "store_type": int,
        "show_type": int,
        "default": 0,
        "schema": PERCENT_SCHEMA
    },
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_RIGHT}": {
        "store_type": int,
        "show_type": int,
        "default": 0,
        "schema": PERCENT_SCHEMA
    },
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_TOP}": {
        "store_type": int,
        "show_type": int,
        "default": 0,
        "schema": PERCENT_SCHEMA
    },
    f"{CONF_MAP_TRANSFORM}.{CONF_TRIM}.{CONF_BOTTOM}": {
        "store_type": int,
        "show_type": int,
        "default": 0,
        "schema": PERCENT_SCHEMA
    },
}

OPTIONS = CAMERA_OPTIONS.copy()

OPTIONS.update({
    CONF_INCLUDE_SHARED: {
        "store_type": bool,
        "show_type": bool,
        "default": True,
        "schema": bool
    },
})

class RoborockOptionsFlowHandler(config_entries.OptionsFlow):
    """Roborock config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, _=None):  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input:
            data = {}
            for key, value in user_input.items():
                store_type = OPTIONS.get(key).get("store_type")
                typed_value = store_type(value)
                set_nested_dict(data, key, typed_value)
            self.options = data
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        key,
                        default=schema.get("show_type")(get_nested_dict(self.options, key, schema.get("default")))
                    ): schema.get("schema")
                    for key, schema in OPTIONS.items()
                }
            ),
        )

    async def _update_options(self):
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)
