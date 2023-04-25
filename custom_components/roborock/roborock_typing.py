from dataclasses import dataclass
from typing import Optional

from roborock import RoborockDeviceInfo, HomeDataProduct, DeviceProp, RoborockLocalDeviceInfo, MultiMapsList


@dataclass
class RoborockHassDeviceInfo(RoborockDeviceInfo):
    product: Optional[HomeDataProduct] = None
    is_map_valid: Optional[bool] = False
    props: Optional[DeviceProp] = None
    map_mapping: Optional[dict[int, str]] = None
    room_mapping: Optional[dict[int, str]] = None
    current_room: Optional[int] = None

@dataclass
class RoborockHassLocalDeviceInfo(RoborockHassDeviceInfo, RoborockLocalDeviceInfo):
    is_durty: Optional[bool] = False
