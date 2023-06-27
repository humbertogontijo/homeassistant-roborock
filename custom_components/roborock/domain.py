"""Domain dict for Roborock."""
from typing import Optional, TypedDict

from . import RoborockDataUpdateCoordinator
from .store import LocalCalendarStore


class DeviceEntryData(TypedDict):
    """Define integration device entry data."""

    coordinator: RoborockDataUpdateCoordinator
    calendar: LocalCalendarStore


class EntryData(TypedDict):
    """Define integration entry data."""

    devices: dict[str, Optional[DeviceEntryData]]
    platforms: list[str]
