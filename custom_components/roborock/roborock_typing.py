from dataclasses import dataclass
from typing import Optional

from roborock import RoborockDeviceInfo, HomeDataProduct, RoborockDeviceProp


@dataclass
class RoborockHassDeviceInfo(RoborockDeviceInfo):
    product: HomeDataProduct
    is_map_valid: bool
    props: Optional[RoborockDeviceProp] = None
