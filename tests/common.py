"""Common methods used across tests for Roborock."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.roborock.const import (
    CONF_BASE_URL,
    CONF_ENTRY_USERNAME,
    CONF_USER_DATA,
    DOMAIN,
)

from .mock_data import BASE_URL, HOME_DATA, HOME_DATA_SHARED, USER_DATA, USER_EMAIL


async def setup_platform(
    hass: HomeAssistant, platform: str, include_shared: bool = True
) -> MockConfigEntry:
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
            "map_transformation.scale": 1.0,
            "map_transformation.rotate": "90",
            "map_transformation.trim.left": 5.0,
            "map_transformation.trim.right": 5.0,
            "map_transformation.trim.top": 5.0,
            "map_transformation.trim.bottom": 5.0,
            "include_shared": include_shared,
        },
    )
    mock_entry.add_to_hass(hass)

    home_data = HOME_DATA_SHARED if include_shared else HOME_DATA

    with patch("custom_components.roborock.PLATFORMS", [platform]), patch(
        "custom_components.roborock.RoborockClient.get_home_data",
        return_value=home_data,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return mock_entry
