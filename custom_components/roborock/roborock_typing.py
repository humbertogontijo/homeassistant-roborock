from dataclasses import dataclass
from typing import Optional, TypedDict

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from roborock import DeviceProp, HomeDataProduct, RoborockDeviceInfo
from roborock.code_mappings import ModelSpecification


class DomainData(TypedDict):
    coordinators: list[DataUpdateCoordinator]
    platforms: list[str]


class DeviceNetwork(TypedDict):
    ip: str
    mac: str


class ConfigEntryData(TypedDict):
    user_data: dict
    home_data: dict
    base_url: str
    username: str
    device_network: dict[str, DeviceNetwork]


@dataclass
class RoborockHassDeviceInfo(RoborockDeviceInfo):
    product: HomeDataProduct
    model_specification: ModelSpecification
    props: Optional[DeviceProp] = None
    is_map_valid: Optional[bool] = False
    map_mapping: Optional[dict[int, str]] = None
    room_mapping: Optional[dict[int, str]] = None
    current_room: Optional[int] = None
