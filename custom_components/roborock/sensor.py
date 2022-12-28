"""Support for Roborock sensors."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription, SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    TIME_SECONDS
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

from custom_components.roborock.api.api import RoborockStatusField
from . import DOMAIN, RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)

ATTR_STATUS_CLEAN_TIME = "clean_time"
ATTR_STATUS_CLEAN_AREA = "clean_area"


@dataclass
class RoborockSensorDescription(SensorEntityDescription):
    """A class that describes sensor entities."""
    value: Callable = None

VACUUM_SENSORS = {
    f"current_{ATTR_STATUS_CLEAN_TIME}": RoborockSensorDescription(
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        key=RoborockStatusField.CLEAN_TIME,
        name="Current clean duration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    f"current_{ATTR_STATUS_CLEAN_AREA}": RoborockSensorDescription(
        native_unit_of_measurement=AREA_SQUARE_METERS,
        icon="mdi:texture-box",
        key=RoborockStatusField.CLEAN_AREA,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Current clean area",
        value=lambda value: value / 1000000,
    ),
}


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum sensors."""
    entities = []
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    for device in coordinator.api.devices:
        device_id = device.get("duid")
        device_status = coordinator.data.get(device_id)
        if device_status:
            unique_id = slugify(device_id)
            for sensor, description in VACUUM_SENSORS.items():
                data = device_status.get(description.key)
                if data is None:
                    _LOGGER.debug(
                        "It seems the %s does not support the %s as the initial value is None",
                        device.get("model"),
                        description.key,
                    )
                    continue
                entities.append(
                    RoborockSensor(
                        f"{sensor}_{unique_id}",
                        device,
                        coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class RoborockSensor(RoborockCoordinatedEntity, SensorEntity):
    """Representation of a Roborock sensor."""

    entity_description: RoborockSensorDescription

    def __init__(self, unique_id: str, device: dict, coordinator: RoborockDataUpdateCoordinator,
                 description: RoborockSensorDescription):
        """Initialize the entity."""
        SensorEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device, coordinator, unique_id)
        self.entity_description = description
        self._attr_native_value = self._determine_native_value()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        native_value = self._determine_native_value()
        # Sometimes (quite rarely) the device returns None as the sensor value, so we
        # check that the value is not None before updating the state.
        if native_value is not None:
            self._attr_native_value = native_value
            self.async_write_ha_state()

    def _determine_native_value(self):
        """Determine native value."""
        native_value = self._extract_value_from_attribute(
            self.entity_description.key
        )
        if native_value is not None:
            if self.entity_description.value:
                native_value = self.entity_description.value(native_value)
            if (
                    self.device_class == SensorDeviceClass.TIMESTAMP
                    and (native_datetime := dt_util.parse_datetime(str(native_value))) is not None
            ):
                return native_datetime.astimezone(dt_util.UTC)

        return native_value
