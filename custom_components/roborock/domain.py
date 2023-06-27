"""Domain dict for Roborock."""
from typing import Optional, TypedDict

from homeassistant.components.local_calendar import LocalCalendarStore

from . import RoborockDataUpdateCoordinator


class DeviceEntryData(TypedDict):
    """Define integration device entry data."""

    coordinator: RoborockDataUpdateCoordinator
    calendar: LocalCalendarStore


class EntryData(TypedDict):
    """Define integration entry data."""

    devices: dict[str, Optional[DeviceEntryData]]
    platforms: list[str]
