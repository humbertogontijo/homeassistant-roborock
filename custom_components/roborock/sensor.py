"""Support for Roborock sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
import logging

from roborock.containers import (
    CleanRecordField,
    CleanSummaryField,
    ConsumableField,
    DNDTimerField,
    StatusField,
)
from roborock.typing import (
    RoborockDeviceInfo,
    RoborockDevicePropField,
    RoborockDockSummaryField,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import AREA_SQUARE_METERS, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
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


@dataclass
class RoborockSensorDescription(SensorEntityDescription):
    """A class that describes sensor entities."""

    attributes: tuple = ()
    parent_key: str = None
    keys: list[str] = None
    value: Callable = None
    translation_key: str = None
    translation_attr: str = None


VACUUM_SENSORS = {
    f"dnd_{ATTR_DND_START}": RoborockSensorDescription(
        key=ATTR_DND_START,
        keys=[DNDTimerField.START_HOUR, DNDTimerField.START_MINUTE],
        value=lambda values: parse_datetime_time(
            time(hour=values[0], minute=values[1])
        ),
        icon="mdi:minus-circle-off",
        name="DnD start",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=RoborockDevicePropField.DND_TIMER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"dnd_{ATTR_DND_END}": RoborockSensorDescription(
        key=ATTR_DND_END,
        keys=[DNDTimerField.END_HOUR, DNDTimerField.END_MINUTE],
        value=lambda values: parse_datetime_time(
            time(hour=values[0], minute=values[1])
        ),
        icon="mdi:minus-circle-off",
        name="DnD end",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=RoborockDevicePropField.DND_TIMER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_START}": RoborockSensorDescription(
        key=CleanRecordField.BEGIN,
        icon="mdi:clock-time-twelve",
        name="Last clean start",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=RoborockDevicePropField.LAST_CLEAN_RECORD,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_END}": RoborockSensorDescription(
        key=CleanRecordField.END,
        icon="mdi:clock-time-twelve",
        device_class=SensorDeviceClass.TIMESTAMP,
        parent_key=RoborockDevicePropField.LAST_CLEAN_RECORD,
        name="Last clean end",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_TIME}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key=CleanRecordField.DURATION,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        parent_key=RoborockDevicePropField.LAST_CLEAN_RECORD,
        name="Last clean duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"last_clean_{ATTR_LAST_CLEAN_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        key=CleanRecordField.AREA,
        value=lambda value: round(value / 1000000, 1),
        icon="mdi:texture-box",
        parent_key=RoborockDevicePropField.LAST_CLEAN_RECORD,
        name="Last clean area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_ERROR}": RoborockSensorDescription(
        key=StatusField.ERROR_CODE,
        icon="mdi:alert",
        translation_key="roborock_vacuum",
        translation_attr="state",
        attributes=(StatusField.ERROR_CODE,),
        parent_key=RoborockDevicePropField.STATUS,
        name="Current error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_CLEAN_TIME}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key=StatusField.CLEAN_TIME,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        parent_key=RoborockDevicePropField.STATUS,
        name="Current clean duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_CLEAN_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:texture-box",
        key=StatusField.CLEAN_AREA,
        value=lambda value: round(value / 1000000, 1),
        parent_key=RoborockDevicePropField.STATUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Current clean area",
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_TOTAL_DURATION}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        key=CleanSummaryField.CLEAN_TIME,
        icon="mdi:timer-sand",
        parent_key=RoborockDevicePropField.CLEAN_SUMMARY,
        name="Total duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_TOTAL_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        key=CleanSummaryField.CLEAN_AREA,
        value=lambda value: round(value / 1000000, 1),
        icon="mdi:texture-box",
        parent_key=RoborockDevicePropField.CLEAN_SUMMARY,
        name="Total clean area",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_COUNT}": RoborockSensorDescription(
        native_unit_of_measurement="",
        key=CleanSummaryField.CLEAN_COUNT,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        parent_key=RoborockDevicePropField.CLEAN_SUMMARY,
        name="Total clean count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"clean_history_{ATTR_CLEAN_SUMMARY_DUST_COLLECTION_COUNT}": RoborockSensorDescription(
        native_unit_of_measurement="",
        key=CleanSummaryField.DUST_COLLECTION_COUNT,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        parent_key=RoborockDevicePropField.CLEAN_SUMMARY,
        name="Total dust collection count",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_MAIN_BRUSH_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key=ConsumableField.MAIN_BRUSH_WORK_TIME,
        value=lambda value: MAIN_BRUSH_REPLACE_TIME - value,
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        parent_key=RoborockDevicePropField.CONSUMABLE,
        name="Main brush left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_SIDE_BRUSH_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key=ConsumableField.SIDE_BRUSH_WORK_TIME,
        value=lambda value: SIDE_BRUSH_REPLACE_TIME - value,
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        parent_key=RoborockDevicePropField.CONSUMABLE,
        name="Side brush left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_FILTER_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key=ConsumableField.FILTER_WORK_TIME,
        value=lambda value: FILTER_REPLACE_TIME - value,
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.DURATION,
        parent_key=RoborockDevicePropField.CONSUMABLE,
        name="Filter left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"consumable_{ATTR_CONSUMABLE_STATUS_SENSOR_DIRTY_LEFT}": RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key=ConsumableField.SENSOR_DIRTY_TIME,
        value=lambda value: SENSOR_DIRTY_REPLACE_TIME - value,
        icon="mdi:eye-outline",
        device_class=SensorDeviceClass.DURATION,
        parent_key=RoborockDevicePropField.CONSUMABLE,
        name="Sensor dirty left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_STATUS}": RoborockSensorDescription(
        key=StatusField.DOCK_ERROR_STATUS,
        icon="mdi:garage-open",
        parent_key=RoborockDevicePropField.STATUS,
        name="Dock status",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_WASHING_MODE}": RoborockSensorDescription(
        key=RoborockDockSummaryField.WASHING_MODE_TYPE,
        value=lambda value: value.value,
        icon="mdi:water",
        parent_key=RoborockDevicePropField.DOCK_SUMMARY,
        name="Dock washing mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_DUST_COLLECTION_MODE}": RoborockSensorDescription(
        key=RoborockDockSummaryField.DUST_COLLECTION_MODE,
        value=lambda value: value.value,
        parent_key=RoborockDevicePropField.DOCK_SUMMARY,
        name="Dock dust collection mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_DOCK_MOP_WASH_MODE}": RoborockSensorDescription(
        key=RoborockDockSummaryField.MOP_WASH,
        icon="mdi:water",
        parent_key=RoborockDevicePropField.DOCK_SUMMARY,
        name="Dock mop wash mode interval",
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

    for device_id, device_info in coordinator.api.device_map.items():
        unique_id = slugify(device_id)
        if coordinator.data:
            device_prop = coordinator.data.get(device_id)
            if device_prop:
                for sensor, description in VACUUM_SENSORS.items():
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
        device_info: RoborockDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockSensorDescription,
    ) -> None:
        """Initialize the entity."""
        SensorEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = description

    @property
    def translation_key(self):
        """Get the translation key for the entity."""
        return self.entity_description.translation_key

    @callback
    def _extract_attributes(self, data):
        """Return state attributes with valid values."""
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.parent_key)
            if not data:
                return None
        return {
            attr: getattr(data, attr)
            for attr in self.entity_description.attributes
            if hasattr(data, attr)
        }

    @property
    def native_value(self):
        data = self.coordinator.data.get(self._device_id)
        if not data:
            return None
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.parent_key)
            if not data:
                return None

        if self.entity_description.keys:
            native_value = [getattr(data, key) for key in self.entity_description.keys]
            if not any(native_value):
                native_value = None
        else:
            native_value = getattr(data, self.entity_description.key)

        if native_value is not None:
            if self.entity_description.value:
                native_value = self.entity_description.value(native_value)
            if self.device_class == SensorDeviceClass.TIMESTAMP and (
                native_datetime := datetime.fromtimestamp(native_value)
            ):
                native_value = native_datetime.astimezone(dt_util.UTC)

        # This is a work around while https://github.com/home-assistant/core/pull/65743 is not merged
        if self.entity_description.translation_key:
            native_value = self.translate(
                self.entity_description.translation_attr, native_value
            )

        return native_value

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data.get(self._device_id)
        return self._extract_attributes(data)
