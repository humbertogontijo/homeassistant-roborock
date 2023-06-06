"""Config flow for Roborock."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from roborock.api import RoborockApiClient
from roborock.containers import UserData

from . import ConfigEntryData, DeviceNetwork
from .const import (
    CAMERA,
    CONF_BASE_URL,
    CONF_BOTTOM,
    CONF_CLOUD_INTEGRATION,
    CONF_ENTRY_CODE,
    CONF_ENTRY_PASSWORD,
    CONF_ENTRY_USERNAME,
    CONF_INCLUDE_IGNORED_OBSTACLES,
    CONF_INCLUDE_NOGO,
    CONF_INCLUDE_SHARED,
    CONF_LEFT,
    CONF_MAP_TRANSFORM,
    CONF_RIGHT,
    CONF_ROTATE,
    CONF_SCALE,
    CONF_TOP,
    CONF_TRIM,
    CONF_USER_DATA,
    DOMAIN,
    VACUUM,
)
from .utils import get_nested_dict, set_nested_dict

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}
        self._client: RoborockApiClient | None = None
        self._auth_method: str | None = None
        self.username: str | None = None
        self.user_data: UserData | None = None
        self.discovered_devices: list[dict] | None = None

    # async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
    #     """Handle a reauth flow."""
    #     host = discovery_info.ip
    #     macaddress = discovery_info.macaddress
    #     entries = self.hass.config_entries.async_entries(DOMAIN)
    #     for entry in entries:
    #         data: ConfigEntryData = entry.data
    #         device_network = data.get("device_network")
    #         for _, network in device_network.items():
    #             if network.get("ip") == host:
    #                 network["mac"] = macaddress
    #             if network.get("mac") == macaddress:
    #                 network["ip"] = host
    #             await self.async_set_unique_id(entry.unique_id)
    #             self._abort_if_unique_id_configured(updates=data)
    #     return await self.async_step_user()

    async def async_step_reauth(self, _user_input: dict[str, Any]) -> FlowResult:
        """Handle a reauth flow."""
        await self.hass.config_entries.async_remove(self.context["entry_id"])
        return await self.async_step_user()

    async def async_step_user(
            self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user", menu_options=[CONF_ENTRY_CODE, CONF_ENTRY_PASSWORD]
        )

    async def async_step_email(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        self._errors.clear()

        if user_input and user_input[CONF_ENTRY_USERNAME]:
            username = user_input[CONF_ENTRY_USERNAME]
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()
            self.username = username
            if self._auth_method == CONF_ENTRY_CODE:
                client = await self._request_code(username)
                if client:
                    self._client = client
                    return await self.async_step_code(user_input)
                self._errors["base"] = "auth"
            elif self._auth_method == CONF_ENTRY_PASSWORD:
                client = RoborockApiClient(username)
                if client:
                    self._client = client
                    return await self.async_step_password(user_input)
                self._errors["base"] = "auth"

        return self.async_show_form(
            step_id="email",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_USERNAME, default=user_input.get(
                            CONF_ENTRY_USERNAME) if user_input else None
                    ): str
                }
            ),
            errors=self._errors,
            last_step=False,
        )

    async def async_step_code(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        self._errors.clear()

        if not user_input:
            self._auth_method = CONF_ENTRY_CODE
            return self._show_email_form()

        code = user_input.get(CONF_ENTRY_CODE)
        if code:
            self.user_data = await self._code_login(code)
            if self.username and self.user_data:
                return self._create_entry(self.username, self.user_data)
            self._errors["base"] = "no_device"

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_CODE, default=user_input.get(CONF_ENTRY_CODE)
                    ): str
                }
            ),
            errors=self._errors,
        )

    async def async_step_password(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        self._errors.clear()

        if not user_input:
            self._auth_method = CONF_ENTRY_PASSWORD
            return self._show_email_form()

        pwd = user_input.get(CONF_ENTRY_PASSWORD)
        if pwd:
            self.user_data = await self._pass_login(pwd)
            if self.username and self.user_data:
                return self._create_entry(self.username, self.user_data)
            self._errors["base"] = "no_device"

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_PASSWORD, default=user_input.get(CONF_ENTRY_PASSWORD)
                    ): str
                }
            ),
            errors=self._errors,
        )

    def _show_email_form(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show the configuration form to provide user email."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="email",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENTRY_USERNAME, default=user_input.get(CONF_ENTRY_USERNAME)
                    ): str
                }
            ),
            errors=self._errors,
            last_step=False,
        )

    def _create_entry(self, username: str, user_data: UserData) -> FlowResult:
        """Finished config flow and create entry."""
        return self.async_create_entry(
            title=username,
            data={
                CONF_ENTRY_USERNAME: username,
                CONF_USER_DATA: user_data.as_dict(),
                CONF_BASE_URL: self._client.base_url,
            },
        )

    async def _request_code(self, username: str) -> RoborockApiClient | None:
        """Return true if credentials is valid."""
        try:
            _LOGGER.debug("Requesting code for Roborock account")
            client = RoborockApiClient(username)
            await client.request_code()
            return client
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return None

    async def _code_login(self, code: str) -> UserData | None:
        """Return UserData if login code is valid."""
        try:
            _LOGGER.debug("Logging into Roborock account using email provided code")
            login_data = await self._client.code_login(code)
            return login_data
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return None

    async def _pass_login(self, password: str) -> UserData | None:
        """Return UserData if login code is valid."""
        try:
            _LOGGER.debug("Logging into Roborock account using email provided code")
            login_data = await self._client.pass_login(password)
            return login_data
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception(ex)
            self._errors["base"] = "auth"
            return None

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
    ) -> RoborockOptionsFlowHandler:
        """Get the options flow for this handler."""
        return RoborockOptionsFlowHandler(config_entry)


def discriminant(_: Any, validators: tuple):
    """Handle discriminant function fo rotation schema."""
    return reversed(list(validators))


DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_DEVICE_ID): str,
    }
)

POSITIVE_FLOAT_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0))
ROTATION_SCHEMA = vol.All(
    vol.Coerce(int),
    vol.Coerce(str),
    vol.In(["0", "90", "180", "270"]),
    discriminant=discriminant,
)
PERCENT_SCHEMA = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

CAMERA_VALUES = {
    f"{CONF_MAP_TRANSFORM}:{CONF_SCALE}": 1.0,
    f"{CONF_MAP_TRANSFORM}:{CONF_ROTATE}": 0,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_LEFT}": 0.0,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_RIGHT}": 0.0,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_TOP}": 0.0,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_BOTTOM}": 0.0,
    CONF_INCLUDE_IGNORED_OBSTACLES: True,
    CONF_INCLUDE_NOGO: True,
}

CAMERA_SCHEMA = {
    f"{CONF_MAP_TRANSFORM}:{CONF_SCALE}": POSITIVE_FLOAT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}:{CONF_ROTATE}": ROTATION_SCHEMA,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_LEFT}": PERCENT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_RIGHT}": PERCENT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_TOP}": PERCENT_SCHEMA,
    f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_BOTTOM}": PERCENT_SCHEMA,
    CONF_INCLUDE_IGNORED_OBSTACLES: vol.Coerce(bool),
    CONF_INCLUDE_NOGO: vol.Coerce(bool),
}

VACUUM_VALUES = {CONF_INCLUDE_SHARED: True}

VACUUM_SCHEMA = {CONF_INCLUDE_SHARED: vol.Coerce(bool)}

OPTION_VALUES = {
    VACUUM: VACUUM_VALUES,
    CAMERA: CAMERA_VALUES,
}

OPTION_SCHEMA = {
    **{f"{VACUUM}.{vs_key}": vs_value for vs_key, vs_value in VACUUM_SCHEMA.items()},
    **{f"{CAMERA}.{cs_key}": cs_value for cs_key, cs_value in CAMERA_SCHEMA.items()},
}

ROBOROCK_VALUES = {CONF_CLOUD_INTEGRATION: False}

ROBOROCK_SCHEMA = {CONF_CLOUD_INTEGRATION: vol.Coerce(bool)}


class RoborockOptionsFlowHandler(config_entries.OptionsFlow):
    """Roborock config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize HACS options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)
        self.discovered_devices = None

    async def async_step_init(
            self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:  # pylint: disable=unused-argument
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(
            self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[CAMERA, VACUUM, DOMAIN],
        )

    async def async_step_menu(
            self, _user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        return self.async_show_menu(
            step_id="user",
            menu_options=[CAMERA, VACUUM, "configure_device"],
        )

    async def async_step_configure_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Finished config flow and create entry."""
        errors = {}
        if user_input:
            host = user_input.get(CONF_HOST)
            device_id = user_input.get(CONF_DEVICE_ID)
            if not host or not device_id:
                errors["base"] = "host_required"
            else:
                data: ConfigEntryData = self.config_entry.data
                device_network = data.get("device_network")
                device_network.update({host: DeviceNetwork(ip=host, mac="")})
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                return await self._update_options()

        return self.async_show_form(
            step_id="configure_device",
            data_schema=vol.Schema(DEVICE_SCHEMA),
            errors=errors,
        )

    async def async_step_camera(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setup of camera."""
        return await self._async_step_platform(
            CAMERA, CAMERA_SCHEMA, CAMERA_VALUES, user_input
        )

    async def async_step_vacuum(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setup of vacuum."""
        return await self._async_step_platform(
            VACUUM, VACUUM_SCHEMA, VACUUM_VALUES, user_input
        )

    async def async_step_roborock(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setup of integration."""
        return await self._async_step_platform(
            DOMAIN, ROBOROCK_SCHEMA, ROBOROCK_VALUES, user_input
        )

    async def _async_step_platform(
            self,
            platform: str,
            schema: dict[str, Any],
            values: dict[str, Any],
            user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle setup of various platforms."""
        if user_input:
            data: dict = {}
            for key, value in user_input.items():
                set_nested_dict(data, key, value)
            if self.options:
                self.options[platform] = data
            else:
                self.options = {platform: data}
            return await self._update_options()
        options = self.options.get(platform) if self.options else None
        return self.async_show_form(
            step_id=platform,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        key,
                        default=schema.get(key)(
                            get_nested_dict(options or {}, key, value)
                        ),
                    ): schema.get(key)
                    for key, value in values.items()
                }
            ),
        )

    async def _update_options(self) -> FlowResult:
        """Update config entry options."""
        return self.async_create_entry(title="", data=self.options)
