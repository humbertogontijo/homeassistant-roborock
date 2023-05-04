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
from roborock import ROBOROCK_S7_MAXV, model_specifications
from roborock.roborock_typing import RoborockCommand

from .common import setup_platform
from .mock_data import HOME_DATA

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = HOME_DATA.devices[0].duid


@pytest.mark.asyncio
async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    mock_config_entry = await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == DEVICE_ID
    await mock_config_entry.async_unload(hass)


@pytest.mark.asyncio
async def test_vacuum_services(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test vacuum services."""
    mock_config_entry = await setup_platform(hass, VACUUM_DOMAIN)
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
        mock_local_api_command.assert_called_once_with(
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
    await mock_config_entry.async_unload(hass)

@pytest.mark.asyncio
async def test_vacuum_fan_speeds(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Test vacuum fan speeds."""
    mock_config_entry = await setup_platform(hass, VACUUM_DOMAIN)
    entity_registry = er.async_get(hass)
    entity_registry.async_get(ENTITY_ID)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "balanced"

    fanspeeds = state.attributes.get(ATTR_FAN_SPEED_LIST)

    for speed in model_specifications[ROBOROCK_S7_MAXV].fan_power_code.values():
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
    await mock_config_entry.async_unload(hass)
