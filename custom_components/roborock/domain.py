"""Domain dict for Roborock."""
from typing import TypedDict

from . import RoborockDataUpdateCoordinator


class DomainData(TypedDict):
    """Define integration domain data."""

    coordinators: list[RoborockDataUpdateCoordinator]
    platforms: list[str]
