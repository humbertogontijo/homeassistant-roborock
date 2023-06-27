"""Support for Roborock calendar."""
from __future__ import annotations

import asyncio
import contextlib
import datetime
import logging
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.components.calendar import (
    CalendarEntity, CalendarEntityFeature,
    CalendarEvent, EVENT_END, EVENT_RRULE, EVENT_START,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util, slugify
from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event
from ical.store import EventStore, EventStoreError
from ical.types import Frequency, Range, Recur, RecurrenceId, Weekday
from pydantic import ValidationError
from roborock import RoborockBaseTimer, RoborockCommand, RoborockException, ServerTimer
from roborock.api import RoborockClient
from roborock.command_cache import CacheableAttribute

from . import EntryData
from .const import (
    DOMAIN,
    MODELS_VACUUM_WITH_MOP,
)
from .device import RoborockEntity
from .roborock_typing import RoborockHassDeviceInfo
from .store import LocalCalendarStore

_LOGGER = logging.getLogger(__name__)
PRODID = "github.com/humbertogontijo/homeassistant-roborock"
WEEKDAYS = [Weekday.SUNDAY, Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY, Weekday.THURSDAY, Weekday.FRIDAY,
            Weekday.SATURDAY]


@dataclass
class RoborockCalendarDescriptionMixin:
    """A class that describes calendar entities."""

    attr: CacheableAttribute
    get_command: RoborockCommand
    add_command: RoborockCommand
    set_command: RoborockCommand
    close_command: RoborockCommand


@dataclass
class RoborockCalendarDescription(
    EntityDescription, RoborockCalendarDescriptionMixin
):
    """Class to describe an Roborock calendar entity."""


VACUUM_CALENDARS = {
    "schedule": RoborockCalendarDescription(
        key="schedule",
        name="Schedule",
        translation_key="schedule",
        attr=CacheableAttribute.server_timer,
        get_command=RoborockCommand.GET_SERVER_TIMER,
        set_command=RoborockCommand.UPD_SERVER_TIMER,
        add_command=RoborockCommand.SET_SERVER_TIMER,
        close_command=RoborockCommand.DEL_SERVER_TIMER,
    )
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

    entities: list[RoborockCalendar] = []
    for _device_id, device_entry_data in domain_data.get("devices").items():
        coordinator = device_entry_data["coordinator"]
        device_info = coordinator.data
        model = device_info.model
        if model not in MODELS_VACUUM_WITH_MOP:
            return

        sensors = VACUUM_CALENDARS
        unique_id = slugify(device_info.device.duid)
        if coordinator.data:
            for sensor, description in sensors.items():
                message = "It seems the %s does not support the %s as the initial value is None"
                with contextlib.suppress(RoborockException):
                    initial_event_value = await coordinator.api.cache[description.attr].async_value()
                    if initial_event_value is None:
                        _LOGGER.debug(
                            message,
                            device_info.model,
                            sensor,
                        )
                        continue
                store = device_entry_data["calendar"]
                ics = await store.async_load()
                calendar = IcsCalendarStream.calendar_from_ics(ics)
                calendar.prodid = PRODID
                roborock_calendar = RoborockCalendar(
                    f"{sensor}_{unique_id}",
                    device_info,
                    description,
                    device_entry_data["calendar"],
                    calendar,
                    coordinator.api,
                    initial_event_value
                )
                entities.append(roborock_calendar)
        else:
            _LOGGER.warning("Failed setting up calendars no Roborock data")

    async_add_entities(entities, update_before_add=True)


class RoborockCalendar(RoborockEntity, CalendarEntity):
    """Representation of a Roborock calendar."""

    entity_description: RoborockCalendarDescription
    _attr_supported_features = (
            CalendarEntityFeature.CREATE_EVENT
            | CalendarEntityFeature.DELETE_EVENT
            | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(
            self,
            unique_id: str,
            device_info: RoborockHassDeviceInfo,
            description: RoborockCalendarDescription,
            store: LocalCalendarStore,
            calendar: Calendar,
            api: RoborockClient,
            initial_event_value: RoborockBaseTimer
    ) -> None:
        """Initialize the entity."""
        CalendarEntity.__init__(self)
        RoborockEntity.__init__(self, device_info, unique_id, api)
        self._event: CalendarEvent | None = None
        self._calendar = calendar
        self.entity_description = description
        self._store = store
        self._event_value = initial_event_value

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_update(self) -> None:
        """Update entity state with the next upcoming event."""
        now = dt_util.now()
        event_ids = []
        events = []
        for event in self._calendar.events:
            if event.uid not in event_ids:
                event_ids.append(event.uid)
                events.append(event)
        event_value = self.api.cache[self.entity_description.attr].value
        server_timers = []
        if event_value:
            if isinstance(event_value[0], list):
                server_timers = [ServerTimer(*server_timer).id for server_timer in event_value]
            else:
                server_timers = [ServerTimer(*event_value).id]
        removed_events = [event.__dict__ for event in events if _event_id(event) not in server_timers]
        await asyncio.gather(
            *[self.async_create_event(
                **{
                    **event,
                    EVENT_RRULE: event[EVENT_RRULE].as_rrule_str()
                }
            ) for event in removed_events]
        )

        next_events = (event for event in self._calendar.timeline_tz(now.tzinfo).active_after(now))
        if event := next(next_events, None):
            self._event = _get_calendar_event(event)
        else:
            self._event = None

    async def async_get_events(
            self,
            hass: HomeAssistant,
            start_date: datetime.datetime,
            end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events = self._calendar.timeline_tz(start_date.tzinfo).overlapping(
            start_date,
            end_date,
        )
        calendar_events = [_get_calendar_event(event) for event in events]
        return calendar_events

    async def _async_store(self) -> None:
        """Persist the calendar to disk."""
        content = IcsCalendarStream.calendar_to_ics(self._calendar)
        await self._store.async_store(content)

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""
        event = _parse_event(kwargs)
        if event.rrule.by_weekday:
            for weekday in event.rrule.by_weekday:
                if weekday.occurrence is not None:
                    raise HomeAssistantError("Scheduling by predefined weekday is not supported")
        if event.rrule.interval != 1:
            raise HomeAssistantError("Scheduling by interval is not supported")

        weekdays = ','.join(
            [str(WEEKDAYS.index(by_weekday.weekday)) for by_weekday in event.rrule.by_weekday]
            if event.rrule.by_weekday else ['*']
        )
        if event.rrule.freq == Frequency.DAILY:
            cronjob = f"{event.dtstart.minute} {event.dtstart.hour} * * *"
        elif event.rrule.freq == Frequency.WEEKLY:
            cronjob = f"{event.dtstart.minute} {event.dtstart.hour} * * {weekdays}"
        elif event.rrule.freq == Frequency.MONTHLY:
            cronjob = f"{event.dtstart.minute} {event.dtstart.hour} {event.dtstart.day} * {weekdays}"
        else:
            cronjob = f"{event.dtstart.minute} {event.dtstart.hour} {event.dtstart.day} {event.dtstart.month} " \
                      f"{weekdays}"
        await self.api.cache[self.entity_description.attr].add_value(
            {
                "data": [[_event_id(event),
                          [
                              cronjob,
                              ["start_clean", 106, "0", -1]]]],
                "need_retry": 1,
            }
        )
        EventStore(self._calendar).add(event)
        await self._async_store()
        if self.entity_id:
            await self.async_update_ha_state(force_refresh=True)

    async def async_delete_event(
            self,
            uid: str,
            recurrence_id: str | None = None,
            recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        if not recurrence_id or recurrence_range != Range.THIS_AND_FUTURE:
            raise HomeAssistantError("You can only remove all occurrences")
        try:
            for _index, event in enumerate(self._calendar.events):
                if event.uid == uid:
                    if RecurrenceId.to_value(recurrence_id) > event.dtstart:
                        raise HomeAssistantError(
                            "You need to remove the first event occurrence to remove all occurrences"
                        )
                    await self.api.cache[self.entity_description.attr].close_value([_event_id(event)])
                    break
            events = self._calendar.events.copy()
            [self._calendar.events.remove(event) for event in events]
        except EventStoreError as err:
            raise HomeAssistantError(f"Error while deleting event: {err}") from err
        await self._async_store()
        await self.async_update_ha_state(force_refresh=True)

    async def async_update_event(
            self,
            uid: str,
            event: dict[str, Any],
            recurrence_id: str | None = None,
            recurrence_range: str | None = None,
    ) -> None:
        """Update an existing event on the calendar."""
        await self.async_delete_event(uid, recurrence_id, recurrence_range)
        await self.async_create_event(**event)


def _event_id(event: Event):
    return event.uid


def _parse_event(event: dict[str, Any]) -> Event:
    """Parse an ical event from a home assistant event dictionary."""
    if rrule := event.get(EVENT_RRULE):
        event[EVENT_RRULE] = Recur.from_rrule(rrule)

    # This function is called with new events created in the local timezone,
    # however ical library does not properly return recurrence_ids for
    # start dates with a timezone. For now, ensure any datetime is stored as a
    # floating local time to ensure we still apply proper local timezone rules.
    # This can be removed when ical is updated with a new recurrence_id format
    # https://github.com/home-assistant/core/issues/87759
    for key in (EVENT_START, EVENT_END):
        if (
                (value := event[key])
                and isinstance(value, datetime.datetime)
                and value.tzinfo is not None
        ):
            event[key] = dt_util.as_local(value).replace(tzinfo=None)

    try:
        return Event.parse_obj(event)
    except ValidationError as err:
        _LOGGER.debug("Error parsing event input fields: %s (%s)", event, str(err))
        raise vol.Invalid("Error parsing event input fields") from err


def _get_calendar_event(event: Event) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    start: datetime.datetime | datetime.date
    end: datetime.datetime | datetime.date
    if isinstance(event.start, datetime.datetime) and isinstance(event.end, datetime.datetime):
        start = dt_util.as_local(event.start)
        end = dt_util.as_local(event.end)
        if (end - start) <= datetime.timedelta(seconds=0):
            end = start + datetime.timedelta(minutes=30)
    else:
        start = event.start
        end = event.end
        if (end - start) < datetime.timedelta(days=0):
            end = start + datetime.timedelta(days=1)

    return CalendarEvent(
        summary=event.summary,
        start=start,
        end=end,
        description=event.description,
        uid=event.uid,
        rrule=event.rrule.as_rrule_str() if event.rrule else None,
        recurrence_id=event.recurrence_id,
        location=event.location,
    )
