from enum import Enum


class UserDataRRiotReferenceField(str, Enum):
    REGION = "r"
    API = "a"
    MQTT = "m"
    L_UNKNOWN = "l"


class UserDataRRiotField(str, Enum):
    USER = "u"
    PASSWORD = "s"
    H_UNKNOWN = "h"
    DOMAIN = "k"
    REFERENCE = "r"


class UserDataField(str, Enum):
    UID = "uid"
    TOKEN_TYPE = "tokentype"
    TOKEN = "token"
    RR_UID = "rruid"
    REGION = "region"
    COUNTRY_CODE = "countrycode"
    COUNTRY = "country"
    NICKNAME = "nickname"
    RRIOT = "rriot"
    TUYA_DEVICE_STATE = "tuyaDeviceState"
    AVATAR_URL = "avatarurl"


class HomeDataProductSchemaField(str, Enum):
    ID = "id"
    NAME = "name"
    CODE = "code"
    MODE = "mode"
    TYPE = "type"
    PROPERTY = "property"
    DESC = "desc"


class HomeDataProductField(str, Enum):
    ID = "id"
    NAME = "name"
    CODE = "code"
    MODEL = "model"
    ICONURL = "iconUrl"
    ATTRIBUTE = "attribute"
    CAPABILITY = "capability"
    CATEGORY = "category"
    SCHEMA = "schema"


class HomeDataDeviceStatusField(str, Enum):
    ID = "id"
    NAME = "name"
    CODE = "code"
    MODEL = "model"
    ICON_URL = "iconUrl"
    ATTRIBUTE = "attribute"
    CAPABILITY = "capability"
    CATEGORY = "category"
    SCHEMA = "schema"


class HomeDataDeviceField(str, Enum):
    DUID = "duid"
    NAME = "name"
    ATTRIBUTE = "attribute"
    ACTIVETIME = "activeTime"
    LOCAL_KEY = "localKey"
    RUNTIME_ENV = "runtimeEnv"
    TIME_ZONE_ID = "timeZoneId"
    ICON_URL = "iconUrl"
    PRODUCT_ID = "productId"
    LON = "lon"
    LAT = "lat"
    SHARE = "share"
    SHARE_TIME = "shareTime"
    ONLINE = "online"
    FV = "fv"
    PV = "pv"
    ROOM_ID = "roomId"
    TUYA_UUID = "tuyaUuid"
    TUYA_MIGRATED = "tuyaMigrated"
    EXTRA = "extra"
    SN = "sn"
    FEATURE_SET = "featureSet"
    NEW_FEATURE_SET = "newFeatureSet"
    DEVICE_STATUS = "deviceStatus"
    SILENT_OTA_SWITCH = "silentOtaSwitch"


class HomeDataRoomField(str, Enum):
    ID = "id"
    NAME = "name"


class HomeDataField(str, Enum):
    ID = "id"
    NAME = "name"
    LON = "lon"
    LAT = "lat"
    GEO_NAME = "geoName"
    PRODUCTS = "products"
    DEVICES = "devices"
    RECEIVED_DEVICES = "receivedDevices"
    ROOMS = "rooms"


class StatusField(str, Enum):
    MSG_VER = "msg_ver"
    MSG_SEQ = "msg_seq"
    STATE = "state"
    BATTERY = "battery"
    CLEAN_TIME = "clean_time"
    CLEAN_AREA = "clean_area"
    ERROR_CODE = "error_code"
    MAP_PRESENT = "map_present"
    IN_CLEANING = "in_cleaning"
    IN_RETURNING = "in_returning"
    IN_FRESH_STATE = "in_fresh_state"
    LAB_STATUS = "lab_status"
    WATER_BOX_STATUS = "water_box_status"
    BACK_TYPE = "back_type"
    WASH_PHASE = "wash_phase"
    WASH_READY = "wash_ready"
    FAN_POWER = "fan_power"
    DND_ENABLED = "dnd_enabled"
    MAP_STATUS = "map_status"
    IS_LOCATING = "is_locating"
    LOCK_STATUS = "lock_status"
    WATER_BOX_MODE = "water_box_mode"
    WATER_BOX_CARRIAGE_STATUS = "water_box_carriage_status"
    MOP_FORBIDDEN_ENABLE = "mop_forbidden_enable"
    CAMERA_STATUS = "camera_status"
    IS_EXPLORING = "is_exploring"
    HOME_SEC_STATUS = "home_sec_status"
    HOME_SEC_ENABLE_PASSWORD = "home_sec_enable_password"
    ADBUMPER_STATUS = "adbumper_status"
    WATER_SHORTAGE_STATUS = "water_shortage_status"
    DOCK_TYPE = "dock_type"
    DUST_COLLECTION_STATUS = "dust_collection_status"
    AUTO_DUST_COLLECTION = "auto_dust_collection"
    AVOID_COUNT = "avoid_count"
    MOP_MODE = "mop_mode"
    DEBUG_MODE = "debug_mode"
    COLLISION_AVOID_STATUS = "collision_avoid_status"
    SWITCH_MAP_MODE = "switch_map_mode"
    DOCK_ERROR_STATUS = "dock_error_status"
    CHARGE_STATUS = "charge_status"
    UNSAVE_MAP_REASON = "unsave_map_reason"
    UNSAVE_MAP_FLAG = "unsave_map_flag"


class DNDTimerField(str, Enum):
    START_HOUR = "start_hour"
    START_MINUTE = "start_minute"
    END_HOUR = "end_hour"
    END_MINUTE = "end_minute"
    ENABLED = "enabled"


class CleanSummaryField(str, Enum):
    CLEAN_TIME = "clean_time"
    CLEAN_AREA = "clean_area"
    CLEAN_COUNT = "clean_count"
    DUST_COLLECTION_COUNT = "dust_collection_count"
    RECORDS = "records"


class CleanRecordField(str, Enum):
    BEGIN = "begin"
    END = "end"
    DURATION = "duration"
    AREA = "area"
    ERROR = "error"
    COMPLETE = "complete"
    START_TYPE = "start_type"
    CLEAN_TYPE = "clean_type"
    FINISH_REASON = "finish_reason"
    DUST_COLLECTION_STATUS = "dust_collection_status"
    AVOID_COUNT = "avoid_count"
    WASH_COUNT = "wash_count"
    MAP_FLAG = "map_flag"


class ConsumableField(str, Enum):
    MAIN_BRUSH_WORK_TIME = "main_brush_work_time"
    SIDE_BRUSH_WORK_TIME = "side_brush_work_time"
    FILTER_WORK_TIME = "filter_work_time"
    FILTER_ELEMENT_WORK_TIME = "filter_element_work_time"
    SENSOR_DIRTY_TIME = "sensor_dirty_time"
    STRAINER_WORK_TIMES = "strainer_work_times"
    DUST_COLLECTION_WORK_TIMES = "dust_collection_work_times"
    CLEANING_BRUSH_WORK_TIMES = "cleaning_brush_work_times"


class MultiMapListMapInfoBakMapsField(str, Enum):
    MAPFLAG = "mapFlag"
    ADD_TIME = "add_time"


class MultiMapListMapInfoField(str, Enum):
    MAPFLAG = "mapFlag"
    ADD_TIME = "add_time"
    LENGTH = "length"
    NAME = "name"
    BAK_MAPS = "bak_maps"


class MultiMapListField(str, Enum):
    MAX_MULTI_MAP = "max_multi_map"
    MAX_BAK_MAP = "max_bak_map"
    MULTI_MAP_COUNT = "multi_map_count"
    MAP_INFO = "map_info"


class Reference:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def region(self):
        return self.data.get(UserDataRRiotReferenceField.REGION)

    @property
    def api(self):
        return self.data.get(UserDataRRiotReferenceField.API)

    @property
    def mqtt(self):
        return self.data.get(UserDataRRiotReferenceField.MQTT)

    @property
    def l_unknown(self):
        return self.data.get(UserDataRRiotReferenceField.L_UNKNOWN)


class RRiot:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def user(self):
        return self.data.get(UserDataRRiotField.USER)

    @property
    def password(self):
        return self.data.get(UserDataRRiotField.PASSWORD)

    @property
    def h_unknown(self):
        return self.data.get(UserDataRRiotField.H_UNKNOWN)

    @property
    def domain(self):
        return self.data.get(UserDataRRiotField.DOMAIN)

    @property
    def reference(self) -> Reference:
        return Reference(self.data.get(UserDataRRiotField.REFERENCE))


class UserData:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def uid(self):
        return self.data.get(UserDataField.UID)

    @property
    def token_type(self):
        return self.data.get(UserDataField.TOKEN_TYPE)

    @property
    def token(self):
        return self.data.get(UserDataField.TOKEN)

    @property
    def rr_uid(self):
        return self.data.get(UserDataField.RR_UID)

    @property
    def region(self):
        return self.data.get(UserDataField.REGION)

    @property
    def country_code(self):
        return self.data.get(UserDataField.COUNTRY_CODE)

    @property
    def country(self):
        return self.data.get(UserDataField.COUNTRY)

    @property
    def nickname(self):
        return self.data.get(UserDataField.NICKNAME)

    @property
    def rriot(self) -> RRiot:
        return RRiot(self.data.get(UserDataField.RRIOT))

    @property
    def tuya_device_state(self):
        return self.data.get(UserDataField.TUYA_DEVICE_STATE)

    @property
    def avatar_url(self):
        return self.data.get(UserDataField.AVATAR_URL)


class HomeDataProductSchema:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def id(self):
        return self.data.get(HomeDataProductSchemaField.ID)

    @property
    def name(self):
        return self.data.get(HomeDataProductSchemaField.NAME)

    @property
    def code(self):
        return self.data.get(HomeDataProductSchemaField.CODE)

    @property
    def mode(self):
        return self.data.get(HomeDataProductSchemaField.MODE)

    @property
    def type(self):
        return self.data.get(HomeDataProductSchemaField.TYPE)

    @property
    def product_property(self):
        return self.data.get(HomeDataProductSchemaField.PROPERTY)

    @property
    def desc(self):
        return self.data.get(HomeDataProductSchemaField.DESC)


class HomeDataProduct:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def id(self):
        return self.data.get(HomeDataProductField.ID)

    @property
    def name(self):
        return self.data.get(HomeDataProductField.NAME)

    @property
    def code(self):
        return self.data.get(HomeDataProductField.CODE)

    @property
    def model(self):
        return self.data.get(HomeDataProductField.MODEL)

    @property
    def iconurl(self):
        return self.data.get(HomeDataProductField.ICONURL)

    @property
    def attribute(self):
        return self.data.get(HomeDataProductField.ATTRIBUTE)

    @property
    def capability(self):
        return self.data.get(HomeDataProductField.CAPABILITY)

    @property
    def category(self):
        return self.data.get(HomeDataProductField.CATEGORY)

    @property
    def schema(self) -> list[HomeDataProductSchema]:
        return [HomeDataProductSchema(schema) for schema in self.data.get(HomeDataProductField.SCHEMA)]


class HomeDataDeviceStatus:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def id(self):
        return self.data.get(HomeDataDeviceStatusField.ID)

    @property
    def name(self):
        return self.data.get(HomeDataDeviceStatusField.NAME)

    @property
    def code(self):
        return self.data.get(HomeDataDeviceStatusField.CODE)

    @property
    def model(self):
        return self.data.get(HomeDataDeviceStatusField.MODEL)

    @property
    def icon_url(self):
        return self.data.get(HomeDataDeviceStatusField.ICON_URL)

    @property
    def attribute(self):
        return self.data.get(HomeDataDeviceStatusField.ATTRIBUTE)

    @property
    def capability(self):
        return self.data.get(HomeDataDeviceStatusField.CAPABILITY)

    @property
    def category(self):
        return self.data.get(HomeDataDeviceStatusField.CATEGORY)

    @property
    def schema(self):
        return self.data.get(HomeDataDeviceStatusField.SCHEMA)


class HomeDataDevice:

    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def duid(self) -> str:
        return self.data.get(HomeDataDeviceField.DUID)

    @property
    def name(self):
        return self.data.get(HomeDataDeviceField.NAME)

    @property
    def attribute(self):
        return self.data.get(HomeDataDeviceField.ATTRIBUTE)

    @property
    def activetime(self):
        return self.data.get(HomeDataDeviceField.ACTIVETIME)

    @property
    def local_key(self) -> str:
        return self.data.get(HomeDataDeviceField.LOCAL_KEY)

    @property
    def runtime_env(self):
        return self.data.get(HomeDataDeviceField.RUNTIME_ENV)

    @property
    def time_zone_id(self):
        return self.data.get(HomeDataDeviceField.TIME_ZONE_ID)

    @property
    def icon_url(self):
        return self.data.get(HomeDataDeviceField.ICON_URL)

    @property
    def product_id(self):
        return self.data.get(HomeDataDeviceField.PRODUCT_ID)

    @property
    def lon(self):
        return self.data.get(HomeDataDeviceField.LON)

    @property
    def lat(self):
        return self.data.get(HomeDataDeviceField.LAT)

    @property
    def share(self):
        return self.data.get(HomeDataDeviceField.SHARE)

    @property
    def share_time(self):
        return self.data.get(HomeDataDeviceField.SHARE_TIME)

    @property
    def online(self):
        return self.data.get(HomeDataDeviceField.ONLINE)

    @property
    def fv(self):
        return self.data.get(HomeDataDeviceField.FV)

    @property
    def pv(self):
        return self.data.get(HomeDataDeviceField.PV)

    @property
    def room_id(self):
        return self.data.get(HomeDataDeviceField.ROOM_ID)

    @property
    def tuya_uuid(self):
        return self.data.get(HomeDataDeviceField.TUYA_UUID)

    @property
    def tuya_migrated(self):
        return self.data.get(HomeDataDeviceField.TUYA_MIGRATED)

    @property
    def extra(self):
        return self.data.get(HomeDataDeviceField.EXTRA)

    @property
    def sn(self):
        return self.data.get(HomeDataDeviceField.SN)

    @property
    def feature_set(self):
        return self.data.get(HomeDataDeviceField.FEATURE_SET)

    @property
    def new_feature_set(self):
        return self.data.get(HomeDataDeviceField.NEW_FEATURE_SET)

    @property
    def device_status(self) -> HomeDataDeviceStatus:
        return HomeDataDeviceStatus(self.data.get(HomeDataDeviceField.DEVICE_STATUS))

    @property
    def silent_ota_switch(self):
        return self.data.get(HomeDataDeviceField.SILENT_OTA_SWITCH)


class HomeDataRoom:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def id(self):
        return self.data.get(HomeDataRoomField.ID)

    @property
    def name(self):
        return self.data.get(HomeDataRoomField.NAME)


class HomeData:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def id(self):
        return self.data.get(HomeDataField.ID)

    @property
    def name(self):
        return self.data.get(HomeDataField.NAME)

    @property
    def lon(self):
        return self.data.get(HomeDataField.LON)

    @property
    def lat(self):
        return self.data.get(HomeDataField.LAT)

    @property
    def geo_name(self):
        return self.data.get(HomeDataField.GEO_NAME)

    @property
    def products(self) -> list[HomeDataProduct]:
        return [HomeDataProduct(product) for product in self.data.get(HomeDataField.PRODUCTS)]

    @property
    def devices(self) -> list[HomeDataDevice]:
        return [HomeDataDevice(device) for device in self.data.get(HomeDataField.DEVICES)]

    @property
    def received_devices(self) -> list[HomeDataDevice]:
        return [HomeDataDevice(device) for device in self.data.get(HomeDataField.RECEIVED_DEVICES)]

    @property
    def rooms(self) -> list[HomeDataRoom]:
        return [HomeDataRoom(room) for room in self.data.get(HomeDataField.ROOMS)]


class Status:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def msg_ver(self):
        return self.data.get(StatusField.MSG_VER)

    @property
    def msg_seq(self):
        return self.data.get(StatusField.MSG_SEQ)

    @property
    def state(self):
        return self.data.get(StatusField.STATE)

    @property
    def battery(self):
        return self.data.get(StatusField.BATTERY)

    @property
    def clean_time(self):
        return self.data.get(StatusField.CLEAN_TIME)

    @property
    def clean_area(self):
        return self.data.get(StatusField.CLEAN_AREA)

    @property
    def error_code(self) -> int:
        return self.data.get(StatusField.ERROR_CODE)

    @property
    def map_present(self):
        return self.data.get(StatusField.MAP_PRESENT)

    @property
    def in_cleaning(self):
        return self.data.get(StatusField.IN_CLEANING)

    @property
    def in_returning(self):
        return self.data.get(StatusField.IN_RETURNING)

    @property
    def in_fresh_state(self):
        return self.data.get(StatusField.IN_FRESH_STATE)

    @property
    def lab_status(self):
        return self.data.get(StatusField.LAB_STATUS)

    @property
    def water_box_status(self):
        return self.data.get(StatusField.WATER_BOX_STATUS)

    @property
    def back_type(self):
        return self.data.get(StatusField.BACK_TYPE)

    @property
    def wash_phase(self):
        return self.data.get(StatusField.WASH_PHASE)

    @property
    def wash_ready(self):
        return self.data.get(StatusField.WASH_READY)

    @property
    def fan_power(self):
        return self.data.get(StatusField.FAN_POWER)

    @property
    def dnd_enabled(self):
        return self.data.get(StatusField.DND_ENABLED)

    @property
    def map_status(self):
        return self.data.get(StatusField.MAP_STATUS)

    @property
    def is_locating(self):
        return self.data.get(StatusField.IS_LOCATING)

    @property
    def lock_status(self):
        return self.data.get(StatusField.LOCK_STATUS)

    @property
    def water_box_mode(self):
        return self.data.get(StatusField.WATER_BOX_MODE)

    @property
    def water_box_carriage_status(self):
        return self.data.get(StatusField.WATER_BOX_CARRIAGE_STATUS)

    @property
    def mop_forbidden_enable(self):
        return self.data.get(StatusField.MOP_FORBIDDEN_ENABLE)

    @property
    def camera_status(self):
        return self.data.get(StatusField.CAMERA_STATUS)

    @property
    def is_exploring(self):
        return self.data.get(StatusField.IS_EXPLORING)

    @property
    def home_sec_status(self):
        return self.data.get(StatusField.HOME_SEC_STATUS)

    @property
    def home_sec_enable_password(self):
        return self.data.get(StatusField.HOME_SEC_ENABLE_PASSWORD)

    @property
    def adbumper_status(self):
        return self.data.get(StatusField.ADBUMPER_STATUS)

    @property
    def water_shortage_status(self):
        return self.data.get(StatusField.WATER_SHORTAGE_STATUS)

    @property
    def dock_type(self):
        return self.data.get(StatusField.DOCK_TYPE)

    @property
    def dust_collection_status(self):
        return self.data.get(StatusField.DUST_COLLECTION_STATUS)

    @property
    def auto_dust_collection(self):
        return self.data.get(StatusField.AUTO_DUST_COLLECTION)

    @property
    def avoid_count(self):
        return self.data.get(StatusField.AVOID_COUNT)

    @property
    def mop_mode(self):
        return self.data.get(StatusField.MOP_MODE)

    @property
    def debug_mode(self):
        return self.data.get(StatusField.DEBUG_MODE)

    @property
    def collision_avoid_status(self):
        return self.data.get(StatusField.COLLISION_AVOID_STATUS)

    @property
    def switch_map_mode(self):
        return self.data.get(StatusField.SWITCH_MAP_MODE)

    @property
    def dock_error_status(self):
        return self.data.get(StatusField.DOCK_ERROR_STATUS)

    @property
    def charge_status(self):
        return self.data.get(StatusField.CHARGE_STATUS)

    @property
    def unsave_map_reason(self):
        return self.data.get(StatusField.UNSAVE_MAP_REASON)

    @property
    def unsave_map_flag(self):
        return self.data.get(StatusField.UNSAVE_MAP_FLAG)


class DNDTimer:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def start_hour(self):
        return self.data.get(DNDTimerField.START_HOUR)

    @property
    def start_minute(self):
        return self.data.get(DNDTimerField.START_MINUTE)

    @property
    def end_hour(self):
        return self.data.get(DNDTimerField.END_HOUR)

    @property
    def end_minute(self):
        return self.data.get(DNDTimerField.END_MINUTE)

    @property
    def enabled(self):
        return self.data.get(DNDTimerField.ENABLED)


class CleanSummary:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def clean_time(self):
        return self.data.get(CleanSummaryField.CLEAN_TIME)

    @property
    def clean_area(self):
        return self.data.get(CleanSummaryField.CLEAN_AREA)

    @property
    def clean_count(self):
        return self.data.get(CleanSummaryField.CLEAN_COUNT)

    @property
    def dust_collection_count(self):
        return self.data.get(CleanSummaryField.DUST_COLLECTION_COUNT)

    @property
    def records(self) -> list[int]:
        return self.data.get(CleanSummaryField.RECORDS)


class CleanRecord:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def begin(self):
        return self.data.get(CleanRecordField.BEGIN)

    @property
    def end(self):
        return self.data.get(CleanRecordField.END)

    @property
    def duration(self):
        return self.data.get(CleanRecordField.DURATION)

    @property
    def area(self):
        return self.data.get(CleanRecordField.AREA)

    @property
    def error(self):
        return self.data.get(CleanRecordField.ERROR)

    @property
    def complete(self):
        return self.data.get(CleanRecordField.COMPLETE)

    @property
    def start_type(self):
        return self.data.get(CleanRecordField.START_TYPE)

    @property
    def clean_type(self):
        return self.data.get(CleanRecordField.CLEAN_TYPE)

    @property
    def finish_reason(self):
        return self.data.get(CleanRecordField.FINISH_REASON)

    @property
    def dust_collection_status(self):
        return self.data.get(CleanRecordField.DUST_COLLECTION_STATUS)

    @property
    def avoid_count(self):
        return self.data.get(CleanRecordField.AVOID_COUNT)

    @property
    def wash_count(self):
        return self.data.get(CleanRecordField.WASH_COUNT)

    @property
    def map_flag(self):
        return self.data.get(CleanRecordField.MAP_FLAG)


class Consumable:
    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def main_brush_work_time(self):
        return self.data.get(ConsumableField.MAIN_BRUSH_WORK_TIME)

    @property
    def side_brush_work_time(self):
        return self.data.get(ConsumableField.SIDE_BRUSH_WORK_TIME)

    @property
    def filter_work_time(self):
        return self.data.get(ConsumableField.FILTER_WORK_TIME)

    @property
    def filter_element_work_time(self):
        return self.data.get(ConsumableField.FILTER_ELEMENT_WORK_TIME)

    @property
    def sensor_dirty_time(self):
        return self.data.get(ConsumableField.SENSOR_DIRTY_TIME)

    @property
    def strainer_work_times(self):
        return self.data.get(ConsumableField.STRAINER_WORK_TIMES)

    @property
    def dust_collection_work_times(self):
        return self.data.get(ConsumableField.DUST_COLLECTION_WORK_TIMES)

    @property
    def cleaning_brush_work_times(self):
        return self.data.get(ConsumableField.CLEANING_BRUSH_WORK_TIMES)


class MultiMapsListMapInfoBakMaps:

    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def mapflag(self):
        return self.data.get(MultiMapListMapInfoBakMapsField.MAPFLAG)

    @property
    def add_time(self):
        return self.data.get(MultiMapListMapInfoBakMapsField.ADD_TIME)


class MultiMapsListMapInfo:

    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def mapflag(self):
        return self.data.get(MultiMapListMapInfoField.MAPFLAG)

    @property
    def add_time(self):
        return self.data.get(MultiMapListMapInfoField.ADD_TIME)

    @property
    def length(self):
        return self.data.get(MultiMapListMapInfoField.LENGTH)

    @property
    def name(self):
        return self.data.get(MultiMapListMapInfoField.NAME)

    @property
    def bak_maps(self):
        return [MultiMapsListMapInfoBakMaps(bak_maps) for bak_maps in self.data.get(MultiMapListMapInfoField.BAK_MAPS)]


class MultiMapsList:

    def __init__(self, data: dict[str, any]) -> None:
        self.data = data if isinstance(data, dict) else {}

    @property
    def max_multi_map(self):
        return self.data.get(MultiMapListField.MAX_MULTI_MAP)

    @property
    def max_bak_map(self):
        return self.data.get(MultiMapListField.MAX_BAK_MAP)

    @property
    def multi_map_count(self):
        return self.data.get(MultiMapListField.MULTI_MAP_COUNT)

    @property
    def map_info(self):
        return [MultiMapsListMapInfo(map_info) for map_info in self.data.get(MultiMapListField.MAP_INFO)]
