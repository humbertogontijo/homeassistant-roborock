"""Typing for Roborock integration."""
from dataclasses import dataclass
from typing import Optional, TypedDict

from roborock import DeviceData, DeviceProp


class DeviceNetwork(TypedDict):
    """Define any network information needed."""

    ip: str
    mac: str


class ConfigEntryData(TypedDict):
    """Define data stored by integration."""

    user_data: dict
    home_data: dict
    base_url: str
    username: str
    device_network: dict[str, DeviceNetwork]


@dataclass
class RoborockHassDeviceInfo(DeviceData):
    """Define a help class to carry device information."""

    props: Optional[DeviceProp] = None
    is_map_valid: Optional[bool] = False
    map_mapping: Optional[dict[int, str]] = None
    room_mapping: Optional[dict[int, str]] = None
    current_room: Optional[int] = None
