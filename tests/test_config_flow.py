"""Test Roborock config flow."""
from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.roborock.api.containers import UserData
from custom_components.roborock.const import DOMAIN

from .common import setup_platform
from .mock_data import HOME_DATA, MOCK_CONFIG, USER_DATA, USER_EMAIL


@pytest.mark.asyncio
async def test_successful_config_flow(hass, bypass_api_fixture):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Check that user form requesting username (email) is shown
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    # Provide email address to config flow
    with patch(
        "custom_components.roborock.config_flow.RoborockClient.request_code",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": USER_EMAIL}
        )
        # Check that user form requesting a code is shown
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
    # Provide code from email to config flow
    with patch(
        "custom_components.roborock.config_flow.RoborockClient.code_login",
        return_value=UserData(USER_DATA),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )
    # Check config flow completed and a new entry is created
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USER_EMAIL
    assert result["data"] == MOCK_CONFIG
    assert result["result"]


@pytest.mark.asyncio
async def test_invalid_code(hass, bypass_api_fixture):
    """Test a failed config flow due to incorrect code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.roborock.config_flow.RoborockClient.request_code",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": USER_EMAIL}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
    # Raise exception for invalid code
    with patch(
        "custom_components.roborock.config_flow.RoborockClient.code_login",
        side_effect=Exception("invalid code"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )
    # Check the user form is presented with the error
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "no_device"}


@pytest.mark.asyncio
async def test_no_devices(hass, bypass_api_fixture):
    """Test a failed config flow due to no devices on Roborock account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.roborock.config_flow.RoborockClient.request_code",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": USER_EMAIL}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
    # Return None from code_login (no devices)
    with patch(
        "custom_components.roborock.config_flow.RoborockClient.code_login",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"code": "123456"}
        )
    # Check the user form is presented with the error
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "no_device"}


@pytest.mark.asyncio
async def test_unknown_user(hass, bypass_api_fixture):
    """Test a failed config flow due to credential validation failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.roborock.config_flow.RoborockClient.request_code",
        side_effect=Exception("unknown user"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "USER_EMAIL"}
        )
    # Check the user form is presented with the error
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "auth"}


@pytest.mark.asyncio
async def test_options_flow(hass, bypass_api_fixture):
    """Test options flow."""
    # Create a new MockConfigEntry and add to HASS (we're bypassing config
    # flow entirely)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entry.add_to_hass(hass)
    # Initialize an options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Verify that the first options step is a user form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    # Change map transformation options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "map_transformation.scale": 1.2,
            "map_transformation.rotate": "90",
            "map_transformation.trim.left": 5.0,
            "map_transformation.trim.right": 5.0,
            "map_transformation.trim.top": 5.0,
            "map_transformation.trim.bottom": 5.0,
            "include_shared": True,
        },
    )
    # Verify that the flow finishes
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    # Verify the options were set
    assert dict(entry.options) == {
        "map_transformation": {
            "scale": 1.2,
            "rotate": 90,
            "trim": {"left": 5, "right": 5, "top": 5, "bottom": 5},
        },
        "include_shared": True,
    }


@pytest.mark.asyncio
async def test_disable_include_shared(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, VACUUM_DOMAIN, include_shared=False)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("vacuum.roborock_s7_maxv")
    assert entry.unique_id == HOME_DATA.devices[0].duid

    entry = entity_registry.async_get("vacuum.roborock_s7_maxv_shared")
    assert entry is None
