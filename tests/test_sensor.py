"""Tests for Roborock sensors."""
from datetime import datetime, time

import pytest
from custom_components.roborock.api.containers import CleanRecordField, DNDTimerField
from custom_components.roborock.const import (
    FILTER_REPLACE_TIME,
    MAIN_BRUSH_REPLACE_TIME,
    SENSOR_DIRTY_REPLACE_TIME,
    SIDE_BRUSH_REPLACE_TIME,
)
from custom_components.roborock.device import parse_datetime_time
from custom_components.roborock.sensor import (
    ATTR_CLEAN_SUMMARY_COUNT,
    ATTR_CLEAN_SUMMARY_DUST_COLLECTION_COUNT,
    ATTR_CLEAN_SUMMARY_TOTAL_AREA,
    ATTR_CLEAN_SUMMARY_TOTAL_DURATION,
    ATTR_CONSUMABLE_STATUS_FILTER_LEFT,
    ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT,
    ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT,
    ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT,
    ATTR_DND_END,
    ATTR_DND_START,
    ATTR_LAST_CLEAN_AREA,
    ATTR_LAST_CLEAN_END,
    ATTR_LAST_CLEAN_START,
    ATTR_LAST_CLEAN_TIME,
    ATTR_STATUS_CLEAN_AREA,
    ATTR_STATUS_CLEAN_TIME,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import setup_platform
from .mock_data import (
    CLEAN_RECORD,
    CLEAN_SUMMARY,
    CONSUMABLE,
    DND_TIMER,
    HOME_DATA,
    STATUS,
)


@pytest.mark.asyncio
async def test_registry_entries(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, SENSOR_DOMAIN)
    entity_registry = er.async_get(hass)

    duid = HOME_DATA.devices[0].duid

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_dnd_start")
    assert entry.unique_id == f"dnd_{ATTR_DND_START}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_dnd_end")
    assert entry.unique_id == f"dnd_{ATTR_DND_END}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_last_clean_duration")
    assert entry.unique_id == f"last_clean_{ATTR_LAST_CLEAN_TIME}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_last_clean_area")
    assert entry.unique_id == f"last_clean_{ATTR_LAST_CLEAN_AREA}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_current_clean_duration")
    assert entry.unique_id == f"current_{ATTR_STATUS_CLEAN_TIME}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_current_clean_area")
    assert entry.unique_id == f"current_{ATTR_STATUS_CLEAN_AREA}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_last_clean_start")
    assert entry.unique_id == f"last_clean_{ATTR_LAST_CLEAN_START}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_last_clean_end")
    assert entry.unique_id == f"last_clean_{ATTR_LAST_CLEAN_END}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_total_duration")
    assert (
        entry.unique_id == f"clean_history_{ATTR_CLEAN_SUMMARY_TOTAL_DURATION}_{duid}"
    )

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_total_clean_area")
    assert entry.unique_id == f"clean_history_{ATTR_CLEAN_SUMMARY_TOTAL_AREA}_{duid}"

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_total_clean_count")
    assert entry.unique_id == f"clean_history_{ATTR_CLEAN_SUMMARY_COUNT}_{duid}"

    entry = entity_registry.async_get(
        "sensor.roborock_s7_maxv_total_dust_collection_count"
    )
    assert (
        entry.unique_id
        == f"clean_history_{ATTR_CLEAN_SUMMARY_DUST_COLLECTION_COUNT}_{duid}"
    )

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_main_brush_left")
    assert (
        entry.unique_id
        == f"consumable_{ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT}_{duid}"
    )

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_side_brush_left")
    assert (
        entry.unique_id
        == f"consumable_{ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT}_{duid}"
    )

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_filter_left")
    assert (
        entry.unique_id
        == f"consumable_{ATTR_CONSUMABLE_STATUS_FILTER_LEFT}_{duid}"
    )

    entry = entity_registry.async_get("sensor.roborock_s7_maxv_sensor_dirty_left")
    assert (
        entry.unique_id
        == f"consumable_{ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT}_{duid}"
    )


@pytest.mark.asyncio
async def test_dnd_start(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests dnd_start is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_dnd_start")
    # Convert time from raw response data to what HA outputs for state
    value = [DND_TIMER[DNDTimerField.START_HOUR], DND_TIMER[DNDTimerField.START_MINUTE]]
    value = parse_datetime_time(time(hour=value[0], minute=value[1]))
    value = datetime.fromtimestamp(value)
    value = value.astimezone(dt_util.UTC)

    assert state.state == str(value).replace(" ", "T")
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP


@pytest.mark.asyncio
async def test_dnd_end(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests dnd_end is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_dnd_end")
    # Convert time from raw response data to what HA outputs for state
    value = [DND_TIMER[DNDTimerField.END_HOUR], DND_TIMER[DNDTimerField.END_MINUTE]]
    value = parse_datetime_time(time(hour=value[0], minute=value[1]))
    value = datetime.fromtimestamp(value)
    value = value.astimezone(dt_util.UTC)

    assert state.state == str(value).replace(" ", "T")
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP


@pytest.mark.asyncio
async def test_last_clean_duration(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests last_clean_duration is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_last_clean_duration")

    assert state.state == str(STATUS[ATTR_STATUS_CLEAN_TIME])
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION


@pytest.mark.asyncio
async def test_clean_area(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests last_clean_area is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_last_clean_area")

    assert state.state == str(round(STATUS[ATTR_STATUS_CLEAN_AREA] / 1000000, 1))
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None


@pytest.mark.asyncio
async def test_current_clean_duration(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests current_clean_duration is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_current_clean_duration")

    assert state.state == str(STATUS[ATTR_STATUS_CLEAN_TIME])
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION


@pytest.mark.asyncio
async def test_current_clean_area(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests current_clean_area is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_current_clean_area")

    assert state.state == str(round(STATUS[ATTR_STATUS_CLEAN_AREA] / 1000000, 1))
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None


@pytest.mark.asyncio
async def test_last_clean_start(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests last_clean_start is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_last_clean_start")
    # Convert time from raw response data to what HA outputs for state
    value = datetime.fromtimestamp(CLEAN_RECORD[CleanRecordField.BEGIN])
    value = value.astimezone(dt_util.UTC)

    assert state.state == str(value).replace(" ", "T")
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP


@pytest.mark.asyncio
async def test_last_clean_end(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests last_clean_end is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_last_clean_end")
    # Convert time from raw response data to what HA outputs for state
    value = datetime.fromtimestamp(CLEAN_RECORD[CleanRecordField.END])
    value = value.astimezone(dt_util.UTC)

    assert state.state == str(value).replace(" ", "T")
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP


@pytest.mark.asyncio
async def test_total_duration(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests total_duration is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_total_duration")

    assert state.state == str(CLEAN_SUMMARY["clean_time"])
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION


@pytest.mark.asyncio
async def test_total_clean_area(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests total_clean_area is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_total_clean_area")

    assert state.state == str(round(CLEAN_SUMMARY["clean_area"] / 1000000, 1))
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None


@pytest.mark.asyncio
async def test_total_clean_count(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests total_clean_count is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_total_clean_count")

    assert state.state == str(CLEAN_SUMMARY["clean_count"])
    assert state.attributes.get("state_class") == SensorStateClass.TOTAL_INCREASING


@pytest.mark.asyncio
async def test_total_dust_collection_count(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests total_dust_collection_count is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_total_dust_collection_count")

    assert state.state == str(CLEAN_SUMMARY["dust_collection_count"])
    assert state.attributes.get("state_class") == SensorStateClass.TOTAL_INCREASING


@pytest.mark.asyncio
async def test_main_brush_left(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests main_brush_left is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_main_brush_left")

    assert state.state == str(
        MAIN_BRUSH_REPLACE_TIME - CONSUMABLE["main_brush_work_time"]
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION


@pytest.mark.asyncio
async def test_side_brush_left(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests side_brush_left is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_side_brush_left")

    assert state.state == str(
        SIDE_BRUSH_REPLACE_TIME - CONSUMABLE["side_brush_work_time"]
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION


@pytest.mark.asyncio
async def test_filter_left(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests filter_left is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_filter_left")

    assert state.state == str(FILTER_REPLACE_TIME - CONSUMABLE["filter_work_time"])
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION


@pytest.mark.asyncio
async def test_sensor_dirty_left(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests sensor_dirty_left is getting the correct values."""
    await setup_platform(hass, SENSOR_DOMAIN)
    state = hass.states.get("sensor.roborock_s7_maxv_sensor_dirty_left")

    assert state.state == str(
        SENSOR_DIRTY_REPLACE_TIME - CONSUMABLE["sensor_dirty_time"]
    )
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION
