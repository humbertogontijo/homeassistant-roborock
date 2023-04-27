"""Tests for Roborock vacuums."""
from unittest.mock import patch

import pytest
from homeassistant.components.vacuum import ATTR_FAN_SPEED, ATTR_FAN_SPEED_LIST
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.components.vacuum import (
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from roborock.typing import RoborockCommand

from custom_components.roborock.vacuum import (
    ATTR_MOP_INTENSITY_LIST,
    ATTR_MOP_MODE_LIST,
)
from .common import setup_platform
from .mock_data import HOME_DATA

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = HOME_DATA.devices[0].duid


@pytest.mark.asyncio
async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID


@pytest.mark.asyncio
async def test_vacuum_services(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test vacuum services."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get(ENTITY_ID)
    with patch(
            "roborock.cloud_api.RoborockMqttClient.send_command"
    ) as mock_mqtt_api_command, patch(
        "roborock.local_api.RoborockLocalClient.send_command"
    ) as mock_local_api_command:
        calls = 0
        # Test starting
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_START, {"entity_id": ENTITY_ID}, blocking=True
        )
        calls += 1
        mock_mqtt_api_command.assert_called_once_with(
            RoborockCommand.APP_START, None
        )
        assert mock_mqtt_api_command.call_count + mock_local_api_command.call_count == calls

        # Test stopping
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_ID}, blocking=True
        )
        calls += 1
        assert mock_mqtt_api_command.call_count + mock_local_api_command.call_count == calls

        # Test pausing
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_ID}, blocking=True
        )
        calls += 1
        assert mock_mqtt_api_command.call_count + mock_local_api_command.call_count == calls

        # Test return to base
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_RETURN_TO_BASE,
            {"entity_id": ENTITY_ID},
            blocking=True,
        )
        calls += 1
        assert mock_mqtt_api_command.call_count + mock_local_api_command.call_count == calls

        # Test clean spot
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_CLEAN_SPOT, {"entity_id": ENTITY_ID}, blocking=True
        )
        calls += 1
        assert mock_mqtt_api_command.call_count + mock_local_api_command.call_count == calls

        # Test locate
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_ID}, blocking=True
        )
        calls += 1
        assert mock_mqtt_api_command.call_count + mock_local_api_command.call_count == calls


@pytest.mark.asyncio
async def test_vacuum_fan_speeds(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test vacuum fan speeds."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get(ENTITY_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "balanced"

    fanspeeds = state.attributes.get(ATTR_FAN_SPEED_LIST)

    for speed in ["off", "silent", "balanced", "turbo", "max", "max_plus", "custom"]:
        assert speed in fanspeeds
    # Test setting fan speed to "Turbo"
    with patch("custom_components.roborock.vacuum.RoborockVacuum.send") as mock_send:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {"entity_id": ENTITY_ID, "fan_speed": "Turbo"},
            blocking=True,
        )
        mock_send.assert_called_once_with(RoborockCommand.SET_CUSTOM_MODE, [])


@pytest.mark.asyncio
async def test_mop_modes(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test mop modes."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get(ENTITY_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("mop_mode") == "standard"

    mop_modes = state.attributes.get(ATTR_MOP_MODE_LIST)

    for mode in ["standard", "deep", "deep_plus", "custom"]:
        assert mode in mop_modes
    # Test setting mop mode to "deep"
    with patch("custom_components.roborock.vacuum.RoborockVacuum.send") as mock_send:
        await hass.services.async_call(
            "Roborock",
            "vacuum_set_mop_mode",
            {"entity_id": ENTITY_ID, "mop_mode": "deep"},
            blocking=True,
        )
        mock_send.assert_called_once_with(RoborockCommand.SET_MOP_MODE, [301])


@pytest.mark.asyncio
async def test_mop_intensity(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test mop intensity."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get(ENTITY_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("mop_intensity") == "intense"

    mop_intensities = state.attributes.get(ATTR_MOP_INTENSITY_LIST)

    for intensity in ["off", "mild", "moderate", "intense", "custom"]:
        assert intensity in mop_intensities

    # Test setting intensity to "mild"
    with patch("custom_components.roborock.vacuum.RoborockVacuum.send") as mock_send:
        await hass.services.async_call(
            "Roborock",
            "vacuum_set_mop_intensity",
            {"entity_id": ENTITY_ID, "mop_intensity": "mild"},
            blocking=True,
        )
        mock_send.assert_called_once_with(
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE, [201]
        )
