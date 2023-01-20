"""Support for Roborock binary sensors."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import RoborockDataUpdateCoordinator
from .api.containers import StatusField
from .api.typing import RoborockDeviceInfo, RoborockDevicePropField
from .const import (
    DOMAIN,
    MODELS_VACUUM_WITH_MOP,
    MODELS_VACUUM_WITH_SEPARATE_MOP,
)
from .device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)

ATTR_MOP_ATTACHED = "is_water_box_carriage_attached"
ATTR_WATER_BOX_ATTACHED = "is_water_box_attached"
ATTR_WATER_SHORTAGE = "is_water_shortage"


@dataclass
class RoborockBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes binary sensor entities."""
    value: Callable = None
    parent_key: str = None


VACUUM_SENSORS = {

    ATTR_MOP_ATTACHED: RoborockBinarySensorDescription(
        key=StatusField.WATER_BOX_STATUS,
        name="Mop attached",
        icon="mdi:square-rounded",
        parent_key=RoborockDevicePropField.STATUS,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
    ATTR_WATER_BOX_ATTACHED: RoborockBinarySensorDescription(
        key=StatusField.WATER_BOX_STATUS,
        name="Water box attached",
        icon="mdi:water",
        parent_key=RoborockDevicePropField.STATUS,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
    ATTR_WATER_SHORTAGE: RoborockBinarySensorDescription(
        key=StatusField.WATER_SHORTAGE_STATUS,
        name="Water shortage",
        icon="mdi:water",
        parent_key=RoborockDevicePropField.STATUS,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
}

VACUUM_SENSORS_SEPARATE_MOP = {
    **VACUUM_SENSORS,
    ATTR_MOP_ATTACHED: RoborockBinarySensorDescription(
        key=StatusField.WATER_BOX_CARRIAGE_STATUS,
        name="Mop attached",
        icon="mdi:square-rounded",
        parent_key=RoborockDevicePropField.STATUS,
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
}


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Only vacuums with mop should have binary sensor registered."""
    entities = []
    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    for device_id, device_info in coordinator.api.device_map.items():
        model = device_info.product.model
        if model not in MODELS_VACUUM_WITH_MOP:
            return

        sensors = VACUUM_SENSORS
        if model in MODELS_VACUUM_WITH_SEPARATE_MOP:
            sensors = VACUUM_SENSORS_SEPARATE_MOP
        unique_id = slugify(device_id)
        if coordinator.data:
            device_prop = coordinator.data.get(device_id)
            if device_prop:
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
                        RoborockBinarySensor(
                            f"{sensor}_{unique_id}",
                            device_info,
                            coordinator,
                            description,
                        )
                    )
        else:
            _LOGGER.warning("Failed setting up binary sensors no Roborock data")

    async_add_entities(entities)


class RoborockBinarySensor(RoborockCoordinatedEntity, BinarySensorEntity):
    """Representation of a Roborock binary sensor."""

    entity_description: RoborockBinarySensorDescription

    def __init__(self, unique_id: str, device_info: RoborockDeviceInfo, coordinator: RoborockDataUpdateCoordinator,
                 description: RoborockBinarySensorDescription):
        """Initialize the entity."""
        BinarySensorEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_is_on = self._determine_native_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        native_value = self._determine_native_value()
        if native_value:
            self._attr_is_on = native_value
            super()._handle_coordinator_update()

    def _determine_native_value(self):
        """Determine native value."""
        data = self.coordinator.data.get(self._device_id)
        if not data:
            return
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.parent_key)
            if not data:
                return

        native_value = getattr(data, self.entity_description.key)
        if native_value and self.entity_description.value:
            return self.entity_description.value(native_value)

        return native_value
