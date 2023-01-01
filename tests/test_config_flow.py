"""Test Roborock config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
import pytest

from custom_components.roborock.api.containers import UserData
from custom_components.roborock.const import DOMAIN

from .mock_data import MOCK_CONFIG, USER_DATA, USER_EMAIL


@pytest.mark.asyncio
async def test_successful_config_flow(hass):
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
    assert result["title"] == "Roborock"
    assert result["data"] == MOCK_CONFIG
    assert result["result"]

@pytest.mark.asyncio
async def test_unknown_user(hass):
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
