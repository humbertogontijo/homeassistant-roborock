"""Tests for Roborock cameras."""
import pytest
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform
from .mock_data import HOME_DATA


@pytest.mark.asyncio
async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, CAMERA_DOMAIN)
    entity_registry = er.async_get(hass)

    duid = HOME_DATA.devices[0].duid

    entry = entity_registry.async_get("camera.roborock_s7_maxv_map")
    assert entry.unique_id == f"{duid}"


@pytest.mark.asyncio
async def test_camera_attributes(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests camera attributes."""
    await setup_platform(hass, CAMERA_DOMAIN)
    state = hass.states.get("camera.roborock_s7_maxv_map")

    assert state.state == STATE_IDLE
