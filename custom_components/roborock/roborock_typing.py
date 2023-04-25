from dataclasses import dataclass
from typing import Optional

from roborock import RoborockDeviceInfo, HomeDataProduct, RoborockDeviceProp, RoborockLocalDeviceInfo


@dataclass
class RoborockHassDeviceInfo(RoborockDeviceInfo):
    product: Optional[HomeDataProduct] = None
    is_map_valid: Optional[bool] = False
    props: Optional[RoborockDeviceProp] = None

@dataclass
class RoborockHassLocalDeviceInfo(RoborockHassDeviceInfo, RoborockLocalDeviceInfo):
    is_durty: Optional[bool] = False
