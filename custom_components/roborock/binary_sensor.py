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

from . import EntryData
from .const import (
    DOMAIN,
    MODELS_VACUUM_WITH_MOP,
    MODELS_VACUUM_WITH_SEPARATE_MOP,
)
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo

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
    ATTR_WATER_BOX_ATTACHED: RoborockBinarySensorDescription(
        key="water_box_status",
        name="Water box attached",
        translation_key="water_box_attached",
        icon="mdi:water",
        parent_key="status",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ATTR_WATER_SHORTAGE: RoborockBinarySensorDescription(
        key="water_shortage_status",
        name="Water shortage",
        translation_key="water_shortage",
        icon="mdi:water",
        parent_key="status",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}

VACUUM_SENSORS_SEPARATE_MOP = {
    **VACUUM_SENSORS,
    ATTR_MOP_ATTACHED: RoborockBinarySensorDescription(
        key="water_box_carriage_status",
        name="Mop attached",
        translation_key="mop_attached",
        icon="mdi:square-rounded",
        parent_key="status",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Only vacuums with mop should have binary sensor registered."""
    domain_data: EntryData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockBinarySensor] = []
    for _device_id, device_entry_data in domain_data.get("devices").items():
        coordinator = device_entry_data["coordinator"]
        device_info = coordinator.data
        model = device_info.model
        if model not in MODELS_VACUUM_WITH_MOP:
            return

        sensors = VACUUM_SENSORS
        if model in MODELS_VACUUM_WITH_SEPARATE_MOP:
            sensors = VACUUM_SENSORS_SEPARATE_MOP
        unique_id = slugify(device_info.device.duid)
        if coordinator.data:
            device_prop = device_info.props
            if device_prop:
                for sensor, description in sensors.items():
                    parent_key_data = getattr(device_prop, description.parent_key)
                    if parent_key_data is None:
                        _LOGGER.debug(
                            "It seems the %s does not support the %s as the initial value is None",
                            device_info.model,
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

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockBinarySensorDescription,
    ) -> None:
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
        if native_value is not None:
            self._attr_is_on = native_value
            super()._handle_coordinator_update()

    def _determine_native_value(self):
        """Determine native value."""
        data = self.coordinator.data.props
        if data is None:
            return
        if self.entity_description.parent_key:
            data = getattr(data, self.entity_description.parent_key)
            if data is None:
                return

        native_value = getattr(data, self.entity_description.key)
        if native_value is not None and self.entity_description.value:
            return self.entity_description.value(native_value)

        return native_value
