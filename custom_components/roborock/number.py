"""Support for Roborock button."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
from collections.abc import Coroutine

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock.api import AttributeCache
from roborock.command_cache import CacheableAttribute

from . import EntryData
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo


@dataclass
class RoborockNumberDescriptionMixin:
    """Define an entity description mixin for button entities."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, bool], Coroutine[Any, Any, dict]]


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
        cache_key=CacheableAttribute.sound_volume,
        update_value=lambda cache, value: cache.update_value([value]),
    )
]


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock button platform."""
    domain_data: EntryData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockNumberEntity] = []
    for _device_id, device_entry_data in domain_data.get("devices").items():
        coordinator = device_entry_data["coordinator"]
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
        return self.api.cache.get(self.entity_description.cache_key).value

    async def async_set_native_value(self, value: float) -> None:
        """Set native value."""
        int_value = int(value)
        await self.entity_description.update_value(self.api.cache.get(self.entity_description.cache_key), int_value)
