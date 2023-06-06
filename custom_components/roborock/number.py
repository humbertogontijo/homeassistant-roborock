"""Support for Roborock button."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock.roborock_typing import RoborockCommand

from . import DomainData
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo


@dataclass
class RoborockNumberDescriptionMixin:
    """Define an entity description mixin for button entities."""

    value_fn: Callable[[RoborockHassDeviceInfo], float]
    api_command: RoborockCommand


@dataclass
class RoborockNumberDescription(
    NumberEntityDescription, RoborockNumberDescriptionMixin
):
    """Describes a Roborock button entity."""


NUMBER_DESCRIPTIONS = [
    RoborockNumberDescription(
        key="sound_volume",
        native_unit_of_measurement="%",
        native_max_value=100,
        native_min_value=0,
        native_step=1,
        translation_key="sound_volume",
        name="Sound Volume",
        value_fn=lambda data: data.sound_volume,
        api_command=RoborockCommand.CHANGE_SOUND_VOLUME
    )
]


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock button platform."""
    domain_data: DomainData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockNumberEntity] = []
    for coordinator in domain_data.get("coordinators"):
        device_info = coordinator.data
        for description in NUMBER_DESCRIPTIONS:
            entities.append(
                RoborockNumberEntity(
                    f"{description.key}_{slugify(device_info.device.duid)}",
                    device_info,
                    coordinator,
                    description,
                )
            )
    async_add_entities(entities)


class RoborockNumberEntity(RoborockCoordinatedEntity, NumberEntity):
    """A class to define Roborock button entities."""

    entity_description: RoborockNumberDescription

    def __init__(
            self,
            unique_id: str,
            device_info: RoborockHassDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
            entity_description: RoborockNumberDescription,
    ) -> None:
        """Create a button entity."""
        super().__init__(device_info, coordinator, unique_id)
        self.entity_description = entity_description

    @property
    def native_value(self) -> float | None:
        """Get native value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set native value."""
        int_value = int(value)
        await self.send(self.entity_description.api_command, [int_value])
