"""Support for Roborock time."""
from __future__ import annotations

import datetime
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock.roborock_typing import RoborockCommand

from . import DomainData
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockTimeDescriptionMixin:
    """Define an entity description mixin for time entities."""

    # Gets the current time of the entity.
    get_time: Callable[[RoborockCoordinatedEntity], datetime.time]
    # Sets the current time of the entity.
    set_time: Callable[[RoborockCoordinatedEntity, datetime.time], Coroutine[Any, Any, dict]]


@dataclass
class RoborockTimeDescription(TimeEntityDescription, RoborockTimeDescriptionMixin):
    """Class to describe an Roborock time entity."""


TIME_DESCRIPTIONS: list[RoborockTimeDescription] = [
    RoborockTimeDescription(
        key="dnd_start",
        name="DnD start",
        translation_key="dnd_start",
        icon="mdi:bell-cancel",
        get_time=lambda data: data.coordinator.data.props.dnd_timer.start_time,
        set_time=lambda entity, desired_time: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                desired_time.hour,
                desired_time.minute,
                entity.coordinator.data.props.dnd_timer.end_hour,
                entity.coordinator.data.props.dnd_timer.end_minute,
            ],
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="dnd_end",
        name="DnD end",
        translation_key="dnd_end",
        icon="mdi:bell-ring",
        get_time=lambda data: data.coordinator.data.props.dnd_timer.end_time,
        set_time=lambda entity, desired_time: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                entity.coordinator.data.props.dnd_timer.start_hour,
                entity.coordinator.data.props.dnd_timer.start_minute,
                desired_time.hour,
                desired_time.minute,
            ],
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="valley_electricity_start",
        name="Valley electricity start",
        translation_key="valley_electricity_start",
        icon="mdi:bell-ring",
        get_time=lambda data: data.coordinator.data.props.valley_electricity_timer.start_time,
        set_time=lambda entity, desired_time: entity.send(
            RoborockCommand.SET_VALLEY_ELECTRICITY_TIMER,
            [
                entity.coordinator.data.props.valley_electricity_timer.start_hour,
                entity.coordinator.data.props.valley_electricity_timer.start_minute,
                desired_time.hour,
                desired_time.minute,
            ],
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="valley_electricity_end",
        name="Valley electricity end",
        translation_key="valley_electricity_end",
        icon="mdi:bell-ring",
        get_time=lambda data: data.coordinator.data.props.valley_electricity_timer.end_time,
        set_time=lambda entity, desired_time: entity.send(
            RoborockCommand.SET_VALLEY_ELECTRICITY_TIMER,
            [
                entity.coordinator.data.props.valley_electricity_timer.start_hour,
                entity.coordinator.data.props.valley_electricity_timer.start_minute,
                desired_time.hour,
                desired_time.minute,
            ],
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
    domain_data: DomainData = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[RoborockTime] = []
    for coordinator in domain_data.get("coordinators"):
        device_info = coordinator.data
        unique_id = slugify(device_info.device.duid)
        if coordinator.data:
            for description in TIME_DESCRIPTIONS:
                roborock_calendar = RoborockTime(
                    f"{description.key}_{unique_id}",
                    device_info,
                    coordinator,
                    description,
                )
                data = description.get_time(roborock_calendar)
                if data is None:
                    _LOGGER.debug(
                        "It seems the %s does not support the %s as the initial value is None",
                        device_info.model,
                        description.key,
                    )
                    continue
                entities.append(roborock_calendar)
        else:
            _LOGGER.warning("Failed setting up calendars no Roborock data")

    async_add_entities(entities)


class RoborockTime(RoborockCoordinatedEntity, TimeEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockTimeDescription

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockTimeDescription,
    ) -> None:
        """Initialize the entity."""
        TimeEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = description

    @property
    def native_value(self) -> datetime.time | None:
        """Return the value reported by the time."""
        return self.entity_description.get_time(self)

    async def async_set_value(self, value: datetime.time) -> None:
        """Set the time."""
        await self.entity_description.set_time(self, value)
