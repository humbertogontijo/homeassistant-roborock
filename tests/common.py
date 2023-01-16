"""Common methods used across tests for Roborock."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.roborock.const import (
    CONF_BASE_URL,
    CONF_ENTRY_USERNAME,
    CONF_MAP_TRANSFORM,
    CONF_USER_DATA,
    DOMAIN,
)

from .mock_data import BASE_URL, HOME_DATA, USER_DATA, USER_EMAIL


async def setup_platform(hass: HomeAssistant, platform: str) -> MockConfigEntry:
    """Set up the Roborock platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER_EMAIL,
        data={
            CONF_ENTRY_USERNAME: USER_EMAIL,
            CONF_USER_DATA: USER_DATA,
            CONF_BASE_URL: BASE_URL,
        },
        options={
            CONF_MAP_TRANSFORM: None,
        },
    )
    mock_entry.add_to_hass(hass)

    with patch("custom_components.roborock.PLATFORMS", [platform]), patch(
        "custom_components.roborock.RoborockClient.get_home_data",
        return_value=HOME_DATA,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return mock_entry
