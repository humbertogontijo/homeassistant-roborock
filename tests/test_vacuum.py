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

from .common import setup_platform
from .mock_data import HOME_DATA

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = HOME_DATA["devices"][0]["duid"]


@pytest.mark.asyncio
async def test_registry_entries(hass: HomeAssistant) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID


@pytest.mark.asyncio
async def test_vacuum_services(hass: HomeAssistant) -> None:
    """Test vacuum services."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get("vacuum.roborock_s7_maxv")
    # Test starting
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_START, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(DEVICE_ID, "app_start", None, False)
    # Test stopping
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(DEVICE_ID, "app_stop", None, False)
    # Test pausing
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(DEVICE_ID, "app_stop", None, False)
    # Test return to base
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_RETURN_TO_BASE,
            {"entity_id": ENTITY_ID},
            blocking=True,
        )
        mock_api_command.assert_called_once_with(DEVICE_ID, "app_charge", None, False)
    # Test clean spot
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_CLEAN_SPOT, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(DEVICE_ID, "app_spot", None, False)
    # Test locate
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_ID}, blocking=True
        )
        mock_api_command.assert_called_once_with(DEVICE_ID, "find_me", None, False)


@pytest.mark.asyncio
async def test_vacuum_fan_speeds(hass: HomeAssistant) -> None:
    """Test vacuum fan speeds."""
    await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get("vacuum.roborock_s7_maxv")

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "Balanced"

    fanspeeds = state.attributes.get(ATTR_FAN_SPEED_LIST)

    for speed in ["Off", "Silent", "Balanced", "Turbo", "Max", "Max+", "Custom"]:
        assert speed in fanspeeds

    # Test setting fan speed to "Turbo"
    with patch(
        "custom_components.roborock.RoborockMqttClient.send_command"
    ) as mock_api_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {"entity_id": ENTITY_ID, "fan_speed": "Turbo"},
            blocking=True,
        )
        mock_api_command.assert_called()
