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

from . import RoborockDataUpdateCoordinator
from .api import RoborockStatusField
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


VACUUM_SENSORS = {
    ATTR_MOP_ATTACHED: RoborockBinarySensorDescription(
        key=RoborockStatusField.WATER_BOX_STATUS,
        name="Mop attached",
        icon="mdi:square-rounded",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
    ATTR_WATER_BOX_ATTACHED: RoborockBinarySensorDescription(
        key=RoborockStatusField.WATER_BOX_STATUS,
        name="Water box attached",
        icon="mdi:water",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
    ATTR_WATER_SHORTAGE: RoborockBinarySensorDescription(
        key=RoborockStatusField.WATER_SHORTAGE_STATUS,
        name="Water shortage",
        icon="mdi:water",
        entity_registry_enabled_default=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC
    ),
}

VACUUM_SENSORS_SEPARATE_MOP = {
    **VACUUM_SENSORS,
    ATTR_MOP_ATTACHED: RoborockBinarySensorDescription(
        key=RoborockStatusField.WATER_BOX_CARRIAGE_STATUS,
        name="Mop attached",
        icon="mdi:square-rounded",
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
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    for device in coordinator.api.devices:
        model = device.get("model")
        if model not in MODELS_VACUUM_WITH_MOP:
            return

        sensors = VACUUM_SENSORS
        if model in MODELS_VACUUM_WITH_SEPARATE_MOP:
            sensors = VACUUM_SENSORS_SEPARATE_MOP
        device_status = coordinator.data.get(device.get("duid"))
        if device_status:
            for sensor, description in sensors.items():
                data = device_status.get(description.key)
                if data is None:
                    _LOGGER.debug(
                        "It seems the %s does not support the %s as the initial value is None",
                        device.get("model"),
                        description.key,
                    )
                    continue
                entities.append(
                    RoborockBinarySensor(
                        f"{sensor}_{config_entry.unique_id}",
                        device,
                        coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class RoborockBinarySensor(RoborockCoordinatedEntity, BinarySensorEntity):
    """Representation of a Roborock binary sensor."""

    entity_description: RoborockBinarySensorDescription

    def __init__(self, unique_id: str, device: dict, coordinator: RoborockDataUpdateCoordinator,
                 description: RoborockBinarySensorDescription):
        """Initialize the entity."""
        BinarySensorEntity.__init__(self)
        super().__init__(device, coordinator, unique_id)
        self.entity_description = description
        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_is_on = self._determine_native_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self._determine_native_value()
        super()._handle_coordinator_update()

    def _determine_native_value(self):
        """Determine native value."""
        state = self._extract_value_from_attribute(
            self.entity_description.key
        )
        if self.entity_description.value is not None and state is not None:
            return self.entity_description.value(state)

        return state
