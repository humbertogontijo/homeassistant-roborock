"""Support for Roborock time."""
from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from roborock.api import AttributeCache, RoborockClient
from roborock.command_cache import CacheableAttribute

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from . import EntryData, RoborockDataUpdateCoordinator
from .const import DOMAIN
from .device import RoborockEntity
from .roborock_typing import RoborockHassDeviceInfo

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockTimeDescriptionMixin:
    """Define an entity description mixin for time entities."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, datetime.time], Coroutine[Any, Any, dict]]
    # Attribute from cache
    get_value: Callable[[AttributeCache], datetime.time]


@dataclass
class RoborockTimeDescription(TimeEntityDescription, RoborockTimeDescriptionMixin):
    """Class to describe an Roborock time entity."""


TIME_DESCRIPTIONS: list[RoborockTimeDescription] = [
    RoborockTimeDescription(
        key="dnd_start",
        name="DnD start",
        translation_key="dnd_start",
        icon="mdi:bell-cancel",
        cache_key=CacheableAttribute.dnd_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                desired_time.hour,
                desired_time.minute,
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("start_hour"),
            minute=cache.value.get("start_minute")
            ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="dnd_end",
        name="DnD end",
        translation_key="dnd_end",
        icon="mdi:bell-ring",
        cache_key=CacheableAttribute.dnd_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                desired_time.hour,
                desired_time.minute,
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("end_hour"),
            minute=cache.value.get("end_minute")
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="valley_electricity_start",
        name="Off-Peak charging start",
        translation_key="valley_electricity_start",
        icon="mdi:bell-ring",
        cache_key=CacheableAttribute.valley_electricity_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                desired_time.hour,
                desired_time.minute,
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("start_hour"),
            minute=cache.value.get("start_minute")
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="valley_electricity_end",
        name="Off-Peak charging end",
        translation_key="valley_electricity_end",
        icon="mdi:bell-ring",
        cache_key=CacheableAttribute.valley_electricity_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                desired_time.hour,
                desired_time.minute,
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("end_hour"),
            minute=cache.value.get("end_minute")
        ),
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Only vacuums with mop should have binary sensor registered."""
    domain_data: EntryData = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = [device_entry_data["coordinator"] for device_entry_data in domain_data.get("devices").values()]

    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockTimeDescription]
    ] = [
        (coordinator, description)
        for coordinator in coordinators
        for description in TIME_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(coordinator.api.cache.get(description.cache_key).async_value()
          for coordinator, description in possible_entities),
        return_exceptions=True
    )
    valid_entities: list[RoborockTime] = []
    for (coordinator, description), result in zip(possible_entities, results):
        device_info = coordinator.data
        if result is None or isinstance(result, Exception):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockTime(
                    f"{description.key}_{slugify(coordinator.data.device.duid)}",
                    device_info,
                    description,
                    coordinator.api,
                )
            )
    async_add_entities(valid_entities)


class RoborockTime(RoborockEntity, TimeEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockTimeDescription

    def __init__(
            self,
            unique_id: str,
            device_info: RoborockHassDeviceInfo,
            description: RoborockTimeDescription,
            api: RoborockClient,
    ) -> None:
        """Initialize the entity."""
        TimeEntity.__init__(self)
        RoborockEntity.__init__(self, device_info, unique_id, api)
        self.entity_description = description

    @property
    def native_value(self) -> datetime.time | None:
        """Return the value reported by the time."""
        return self.entity_description.get_value(self.api.cache.get(self.entity_description.cache_key))

    async def async_set_value(self, value: datetime.time) -> None:
        """Set the time."""
        await self.entity_description.update_value(self.api.cache.get(self.entity_description.cache_key), value)
