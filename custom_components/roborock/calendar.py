"""Support for Roborock calendar."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock import DnDTimer, RoborockBaseTimer, RoborockCommand, RoborockException, ValleyElectricityTimer

from . import DomainData
from .const import (
    DOMAIN,
    MODELS_VACUUM_WITH_MOP,
)
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo
import contextlib

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockCalendarDescriptionMixin:
    """A class that describes calendar entities."""

    base_class: type[RoborockBaseTimer]
    get_command: RoborockCommand
    update_command: RoborockCommand
    delete_command: RoborockCommand


@dataclass
class RoborockCalendarDescription(
    EntityDescription, RoborockCalendarDescriptionMixin
):
    """Class to describe an Roborock calendar entity."""


VACUUM_CALENDARS = {
    "valley_electricity_timer": RoborockCalendarDescription(
        key="valley_electricity_timer",
        name="Valley Electricity",
        translation_key="valley_electricity_timer",
        base_class=ValleyElectricityTimer,
        get_command=RoborockCommand.GET_VALLEY_ELECTRICITY_TIMER,
        update_command=RoborockCommand.SET_VALLEY_ELECTRICITY_TIMER,
        delete_command=RoborockCommand.CLOSE_VALLEY_ELECTRICITY_TIMER,
    ),
    "dnd_timer": RoborockCalendarDescription(
        key="dnd_timer",
        name="Do not disturb",
        translation_key="dnd_timer",
        base_class=DnDTimer,
        get_command=RoborockCommand.GET_DND_TIMER,
        update_command=RoborockCommand.SET_DND_TIMER,
        delete_command=RoborockCommand.CLOSE_DND_TIMER,
    )
}


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Only vacuums with mop should have binary sensor registered."""
    domain_data: DomainData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockCalendar] = []
    for coordinator in domain_data.get("coordinators"):
        device_info = coordinator.data
        model = device_info.model
        if model not in MODELS_VACUUM_WITH_MOP:
            return

        sensors = VACUUM_CALENDARS
        unique_id = slugify(device_info.device.duid)
        if coordinator.data:
            for sensor, description in sensors.items():
                initial_event_value = None
                message = "It seems the %s does not support the %s as the initial value is None"
                with contextlib.suppress(RoborockException):
                    initial_event_value = await coordinator.api.send_command(
                        description.get_command,
                        return_type=description.base_class
                    )

                if initial_event_value is None:
                    _LOGGER.debug(
                        message,
                        device_info.model,
                        sensor,
                    )
                    continue
                roborock_calendar = RoborockCalendar(
                    f"{sensor}_{unique_id}",
                    device_info,
                    coordinator,
                    description,
                    initial_event_value
                )
                roborock_calendar.event_value = initial_event_value
                entities.append(roborock_calendar)
        else:
            _LOGGER.warning("Failed setting up calendars no Roborock data")

    async_add_entities(entities)


class RoborockCalendar(RoborockCoordinatedEntity, CalendarEntity):
    """Representation of a Roborock calendar."""

    entity_description: RoborockCalendarDescription

    def __init__(
            self,
            unique_id: str,
            device_info: RoborockHassDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
            description: RoborockCalendarDescription,
            initial_event_value: RoborockBaseTimer
    ) -> None:
        """Initialize the entity."""
        CalendarEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = description
        self._event_value = initial_event_value

    @property
    def supported_features(self) -> int | None:
        """Supported features."""
        return (
                CalendarEntityFeature.CREATE_EVENT
                | CalendarEntityFeature.UPDATE_EVENT
                | CalendarEntityFeature.DELETE_EVENT
        )

    async def async_update(self) -> None:
        """Async update."""
        self._event_value = await self.coordinator.api.send_command(
            self.entity_description.get_command,
            return_type=self.entity_description.base_class
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        event_value = self._event_value
        return CalendarEvent(
            start=event_value.start_time,
            end=event_value.end_time,
            summary=self.entity_description.name,
            description=self.entity_description.name,
            location="Home",
            recurrence_id=self.entity_description.key,
            rrule="FREQ=DAILY",
            uid=self.entity_description.key
        ) if event_value and event_value.enabled else None

    async def async_get_events(
            self,
            hass: HomeAssistant,
            start_date: datetime.datetime,
            end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [self.event] if self.event else []

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""
        await self.async_update_event(self.entity_description.key, event=kwargs)

    async def async_delete_event(
            self,
            uid: str,
            recurrence_id: str | None = None,
            recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        await self.send(
            self.entity_description.delete_command,
            return_type=self.entity_description.base_class
        )

    async def async_delete_event_service(self) -> None:
        """Service to delete an event on the calendar."""
        await self.async_delete_event(self.entity_description.key)

    async def async_update_event(
            self,
            uid: str,
            event: dict[str, Any],
            recurrence_id: str | None = None,
            recurrence_range: str | None = None,
    ) -> None:
        """Update an event on the calendar."""
        start_time: datetime.datetime = event.get("dtstart")
        end_time: datetime.datetime = event.get("dtend")

        await self.send(
            self.entity_description.update_command,
            [start_time.hour, start_time.minute, end_time.hour, end_time.minute],
            return_type=self.entity_description.base_class
        )

    async def async_update_event_service(
            self,
            dtstart: datetime.time,
            dtend: datetime.time
    ) -> None:
        """Service to update an event on the calendar."""
        await self.async_update_event(self.entity_description.key, {"dtstart": dtstart, "dtend": dtend})
