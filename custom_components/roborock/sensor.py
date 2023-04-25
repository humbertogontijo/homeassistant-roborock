"""Support for Roborock sensors."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import AREA_SQUARE_METERS, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from .const import (
    DOMAIN,
    FILTER_REPLACE_TIME,
    MAIN_BRUSH_REPLACE_TIME,
    SENSOR_DIRTY_REPLACE_TIME,
    SIDE_BRUSH_REPLACE_TIME,
)
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity, parse_datetime_time
from .roborock_typing import RoborockHassDeviceInfo

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY = "battery"
ATTR_DND_START = "start"
ATTR_DND_END = "end"
ATTR_LAST_CLEAN_TIME = "duration"
ATTR_LAST_CLEAN_AREA = "area"
ATTR_STATUS_ERROR = "error"
ATTR_STATUS_CLEAN_TIME = "clean_time"
ATTR_STATUS_CLEAN_AREA = "clean_area"
ATTR_LAST_CLEAN_START = "start"
ATTR_LAST_CLEAN_END = "end"
ATTR_CLEAN_SUMMARY_TOTAL_DURATION = "total_duration"
ATTR_CLEAN_SUMMARY_TOTAL_AREA = "total_area"
ATTR_CLEAN_SUMMARY_COUNT = "count"
ATTR_CLEAN_SUMMARY_DUST_COLLECTION_COUNT = "dust_collection_count"
ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT = "main_brush_left"
ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT = "side_brush_left"
ATTR_CONSUMABLE_STATUS_FILTER_LEFT = "filter_left"
ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT = "sensor_dirty_left"
ATTR_DOCK_STATUS = "dock_status"
ATTR_DOCK_WASHING_MODE = "dock_washing_mode"
ATTR_DOCK_DUST_COLLECTION_MODE = "dock_dust_collection_mode"
ATTR_DOCK_MOP_WASH_MODE = "dock_mop_wash_mode"
ATTR_SELECTED_MAP = "map_selected"
ATTR_CURRENT_ROOM = "room"


@dataclass
class RoborockSensorDescription(SensorEntityDescription):
    """A class that describes sensor entities."""

    attributes: tuple = ()
    parent_key: str = None
    keys: list[str] = None
    value: Callable = None


VACUUM_SENSORS = {
    f"dnd_{ATTR_DND_START}": RoborockSensorDescription(
        key=ATTR_DND_START,
        keys=["start_hour", "start_minute"],
        value=lambda values, _: parse_datetime_time(
            time(hour=values[0], minute=values[1])
        ),
        icon="mdi:minus-circle-off",
        name="DnD start",
        translation_key="dnd_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key="dnd_timer",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"dnd_{ATTR_DND_END}": RoborockSensorDescription(
        key=ATTR_DND_END,
        keys=["end_hour", "end_minute"],
        value=lambda values, _: parse_datetime_time(
            time(hour=values[0], minute=values[1])
        ),
        icon="mdi:minus-circle-off",
        name="DnD end",
        translation_key="dnd_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key="dnd_timer",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_START}": RoborockSensorDescription(
        key="begin",
        icon="mdi:clock-time-twelve",
        name="Last clean start",
        translation_key="last_clean_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key="last_clean_record",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_END}": RoborockSensorDescription(
        key="end",
        icon="mdi:clock-time-twelve",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key="last_clean_record",
        name="Last clean end",
        translation_key="last_clean_end",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_TIME}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="duration",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        parent_key="last_clean_record",
        name="Last clean duration",
        translation_key="last_clean_duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        key="area",
        value=lambda value, _: round(value / 1000000, 1),
        icon="mdi:texture-box",
        parent_key="last_clean_record",
        name="Last clean area",
        translation_key="last_clean_area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_ERROR}": RoborockSensorDescription(
        key="error_code",
        icon="mdi:alert",
        name="Current error",
        translation_key="current_error",
        attributes=("error_code",),
        parent_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_CLEAN_TIME}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="clean_time",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        parent_key="status",
        name="Current clean duration",
        translation_key="current_clean_duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_CLEAN_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:texture-box",
        key="clean_area",
        value=lambda value, _: round(value / 1000000, 1),
        parent_key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Current clean area",
        translation_key="current_clean_area",
    ),
    f"current_{ATTR_SELECTED_MAP}": RoborockSensorDescription(
        key="map_status",
        value=lambda value, device_info:
        slugify(device_info.map_mapping.get((value - 3) // 4))
        if device_info and device_info.map_mapping else None,
        icon="mdi:floor-plan",
        parent_key="status",
        name="Current selected map",
        translation_key="current_map_selected",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_CURRENT_ROOM}": RoborockSensorDescription(
        # TODO: Find a better way of doing this
        key="state",
        value=lambda _, device_info:
        slugify(device_info.room_mapping.get(device_info.current_room))
        if device_info.room_mapping and device_info.current_room else None,
        icon="mdi:floor-plan",
        parent_key="status",
        name="Current room",
        translation_key="current_room",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_TOTAL_DURATION}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        key="clean_time",
        icon="mdi:timer-sand",
        parent_key="clean_summary",
        name="Total duration",
        translation_key="total_duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_TOTAL_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        key="clean_area",
        value=lambda value, _: round(value / 1000000, 1),
        icon="mdi:texture-box",
        parent_key="clean_summary",
        name="Total clean area",
        translation_key="total_clean_area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_COUNT}": RoborockSensorDescription(
        native_unit_of_measurement="",
        key="clean_count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        parent_key="clean_summary",
        name="Total clean count",
        translation_key="total_clean_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_DUST_COLLECTION_COUNT}": RoborockSensorDescription(
        native_unit_of_measurement="",
        key="dust_collection_count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        parent_key="clean_summary",
        name="Total dust collection count",
        translation_key="total_dust_collection_count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="main_brush_work_time",
        value=lambda value, _: MAIN_BRUSH_REPLACE_TIME - value,
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        parent_key="consumable",
        name="Main brush left",
        translation_key="main_brush_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="side_brush_work_time",
        value=lambda value, _: SIDE_BRUSH_REPLACE_TIME - value,
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        parent_key="consumable",
        name="Side brush left",
        translation_key="side_brush_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_FILTER_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="filter_work_time",
        value=lambda value, _: FILTER_REPLACE_TIME - value,
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.DURATION,
        parent_key="consumable",
        name="Filter left",
        translation_key="filter_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="sensor_dirty_time",
        value=lambda value, _: SENSOR_DIRTY_REPLACE_TIME - value,
        icon="mdi:eye-outline",
        device_class=SensorDeviceClass.DURATION,
        parent_key="consumable",
        name="Sensor dirty left",
        translation_key="sensor_dirty_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_STATUS}": RoborockSensorDescription(
        key="dock_error_status",
        icon="mdi:garage-open",
        parent_key="status",
        name="Dock status",
        translation_key="dock_status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

VACUUM_WITH_DOCK_SENSORS = {
    **VACUUM_SENSORS,
    f"current_{ATTR_DOCK_WASHING_MODE}": RoborockSensorDescription(
        key="wash_towel_mode",
        value=lambda value, _: value.wash_mode.value,
        icon="mdi:water",
        parent_key="dock_summary",
        name="Dock washing mode",
        translation_key="dock_washing_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_DUST_COLLECTION_MODE}": RoborockSensorDescription(
        key="dust_collection_mode",
        value=lambda value, _: value.mode.value,
        parent_key="dock_summary",
        name="Dock dust collection mode",
        translation_key="dock_dust_collection_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_MOP_WASH_MODE}": RoborockSensorDescription(
        key="smart_wash_params",
        value=lambda value, _: value.wash_interval,
        icon="mdi:water",
        parent_key="dock_summary",
        name="Dock mop wash mode interval",
        translation_key="dock_mop_wash_mode_interval",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum sensors."""
    entities = []
    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    for device_id, device_info in coordinator.devices_info.items():
        unique_id = slugify(device_id)
        if coordinator.data:
            device_prop = coordinator.data.get(device_id)
            if device_prop:
                sensors = VACUUM_SENSORS
                if device_prop.dock_summary:
                    sensors = VACUUM_WITH_DOCK_SENSORS
                for sensor, description in sensors.items():
                    parent_key_data = getattr(device_prop, description.parent_key)
                    if not parent_key_data:
                        _LOGGER.debug(
                            "It seems the %s does not support the %s as the initial value is None",
                            device_info.product.model,
                            sensor,
                        )
                        continue
                    entities.append(
                        RoborockSensor(
                            f"{sensor}_{unique_id}",
                            device_info,
                            coordinator,
                            description,
                        )
                    )
        else:
            _LOGGER.warning("Failed setting up sensors no Roborock data")

    async_add_entities(entities)


class RoborockSensor(RoborockCoordinatedEntity, SensorEntity):
    """Representation of a Roborock sensor."""

    entity_description: RoborockSensorDescription

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockSensorDescription,
    ) -> None:
        """Initialize the entity."""
        SensorEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = description
        self._attr_native_value = self._determine_native_value()
        self._attr_extra_state_attributes = self._extract_attributes(
            coordinator.data.get(self._device_id)
        )

    @callback
    def _extract_attributes(self, data):
        """Return state attributes with valid values."""
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.parent_key)
            if data is None:
                return
        return {
            attr: getattr(data, attr)
            for attr in self.entity_description.attributes
            if hasattr(data, attr)
        }

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        native_value = self._determine_native_value()
        # Sometimes (quite rarely) the device returns None as the sensor value so we
        # check that the value: before updating the state.
        if native_value is not None:
            data = self.coordinator.data.get(self._device_id)
            self._attr_native_value = native_value
            self._attr_extra_state_attributes = self._extract_attributes(data)
            super()._handle_coordinator_update()

    def _determine_native_value(self):
        """Determine native value."""
        data = self.coordinator.data.get(self._device_id)
        if data is None:
            return
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.parent_key)
            if data is None:
                return

        if self.entity_description.keys:
            native_value = [getattr(data, key) for key in self.entity_description.keys]
            if not any(native_value):
                native_value = None
        else:
            native_value = getattr(data, self.entity_description.key)

        if native_value is not None:
            if self.entity_description.value:
                device_info = self.coordinator.devices_info.get(self._device_id)
                native_value = self.entity_description.value(native_value, device_info)
            if self.device_class == SensorDeviceClass.TIMESTAMP and (
                native_datetime := datetime.fromtimestamp(native_value)
            ):
                native_value = native_datetime.astimezone(dt_util.UTC)

        return native_value
