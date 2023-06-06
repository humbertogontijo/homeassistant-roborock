"""Test Roborock Select platform."""
from unittest.mock import patch

import pytest
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import SERVICE_SELECT_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from roborock.exceptions import RoborockException

from tests.common import setup_platform


@pytest.mark.asyncio
async def test_disable_include_shared(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test allowed changing values for select entities."""
    mock_config_entry = await setup_platform(hass, SELECT_DOMAIN)
    with patch(
            "roborock.local_api.RoborockLocalClient.send_command",
    ) as mock_send_message:
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "deep"},
            blocking=True,
            target={"entity_id": "select.roborock_s7_maxv_mop_mode"},
        )
        # Test mop mode
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "deep"},
            blocking=True,
            target={"entity_id": "select.roborock_s7_maxv_mop_mode"},
        )
        assert mock_send_message.assert_called_once

    with patch(
            "roborock.local_api.RoborockLocalClient.send_command",
    ) as mock_send_message:
        # Test intensity mode
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "mild"},
            blocking=True,
            target={"entity_id": "select.roborock_s7_maxv_mop_intensity"},
        )
        assert mock_send_message.assert_called_once
    await mock_config_entry.async_unload(hass)


@pytest.mark.asyncio
async def test_update_failure(
        hass: HomeAssistant,
        bypass_api_fixture,
) -> None:
    """Test that changing a value will raise a homeassistanterror when it fails."""
    mock_config_entry = await setup_platform(hass, SELECT_DOMAIN)
    with patch(
            "roborock.local_api.RoborockLocalClient.send_command",
            side_effect=RoborockException(),
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            service_data={"option": "deep"},
            blocking=True,
            target={"entity_id": "select.roborock_s7_maxv_mop_mode"},
        )
    await mock_config_entry.async_unload(hass)
