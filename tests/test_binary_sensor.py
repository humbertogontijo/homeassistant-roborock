"""Tests for Roborock binary sensors."""
import pytest
from custom_components.roborock.binary_sensor import (
    ATTR_MOP_ATTACHED,
    ATTR_WATER_BOX_ATTACHED,
    ATTR_WATER_SHORTAGE,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform
from .mock_data import HOME_DATA


@pytest.mark.asyncio
async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    entity_registry = er.async_get(hass)

    duid = HOME_DATA.devices[0].duid

    entry = entity_registry.async_get("binary_sensor.roborock_s7_maxv_mop_attached")
    assert entry.unique_id == f"{ATTR_MOP_ATTACHED}_{duid}"

    entry = entity_registry.async_get(
        "binary_sensor.roborock_s7_maxv_water_box_attached"
    )
    assert entry.unique_id == f"{ATTR_WATER_BOX_ATTACHED}_{duid}"

    entry = entity_registry.async_get("binary_sensor.roborock_s7_maxv_water_shortage")
    assert entry.unique_id == f"{ATTR_WATER_SHORTAGE}_{duid}"


@pytest.mark.asyncio
async def test_mop_attached(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests mop_attached is getting the correct values."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    state = hass.states.get("binary_sensor.roborock_s7_maxv_mop_attached")

    assert state.state == STATE_ON
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.CONNECTIVITY
    )


@pytest.mark.asyncio
async def test_water_box_attached(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests water_box_attached is getting the correct values."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    state = hass.states.get("binary_sensor.roborock_s7_maxv_water_box_attached")

    assert state.state == STATE_ON
    assert (
        state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.CONNECTIVITY
    )


@pytest.mark.asyncio
async def test_water_shortage(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests water_shortage is getting the correct values."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)
    state = hass.states.get("binary_sensor.roborock_s7_maxv_water_shortage")

    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.PROBLEM
