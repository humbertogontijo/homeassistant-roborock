from enum import Enum

from custom_components.roborock.api.containers import HomeDataDevice, HomeDataProduct, Status, CleanSummary, Consumable, \
    DNDTimer, CleanRecord


class RoborockDevicePropField(str, Enum):
    STATUS = "status"
    DND_TIMER = "dnd_timer"
    CLEAN_SUMMARY = "clean_summary"
    CONSUMABLE = "consumable"
    LAST_CLEAN_RECORD = "last_clean_record"

class RoborockCommand(str, Enum):
    GET_MAP_V1 = "get_map_v1",
    GET_STATUS = "get_status"
    GET_DND_TIMER = "get_dnd_timer"
    GET_CLEAN_SUMMARY = "get_clean_summary"
    GET_CLEAN_RECORD = "get_clean_record"
    GET_CONSUMABLE = "get_consumable"
    GET_MULTI_MAPS_LIST = "get_multi_maps_list",
    APP_START = "app_start",
    APP_PAUSE = "app_pause",
    APP_STOP = "app_stop",
    APP_CHARGE = "app_charge",
    APP_SPOT = "app_spot",
    FIND_ME = "find_me",
    SET_CUSTOM_MODE = "set_custom_mode",
    SET_MOP_MODE = "set_mop_mode",
    SET_WATER_BOX_CUSTOM_MODE = "set_water_box_custom_mode",
    RESET_CONSUMABLE = "reset_consumable",
    LOAD_MULTI_MAP = "load_multi_map",
    APP_RC_START = "app_rc_start",
    APP_RC_END = "app_rc_end",
    APP_RC_MOVE = "app_rc_move",
    APP_GOTO_TARGET = "app_goto_target",
    APP_SEGMENT_CLEAN = "app_segment_clean",
    APP_ZONED_CLEAN = "app_zoned_clean",


class RoborockDeviceInfo:
    def __init__(self, device: HomeDataDevice, product: HomeDataProduct):
        self.device = device
        self.product = product


class RoborockDeviceProp:
    def __init__(self, status: Status, dnd_timer: DNDTimer, clean_summary: CleanSummary, consumable: Consumable,
                 last_clean_record: CleanRecord):
        self.status = status
        self.dnd_timer = dnd_timer
        self.clean_summary = clean_summary
        self.consumable = consumable
        self.last_clean_record = last_clean_record

    def update(self, device_prop: 'RoborockDeviceProp'):
        if device_prop.status:
            self.status = device_prop.status
        if device_prop.dnd_timer:
            self.dnd_timer = device_prop.dnd_timer
        if device_prop.clean_summary:
            self.clean_summary = device_prop.clean_summary
        if device_prop.consumable:
            self.consumable = device_prop.consumable
        if device_prop.last_clean_record:
            self.last_clean_record = device_prop.last_clean_record
