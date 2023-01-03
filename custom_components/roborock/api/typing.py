from enum import Enum

from custom_components.roborock.api.containers import HomeDataDevice, HomeDataProduct, Status, CleanSummary, Consumable, \
    DNDTimer, CleanRecord


class RoborockDevicePropField(str, Enum):
    STATUS = "status"
    DND_TIMER = "dnd_timer"
    CLEAN_SUMMARY = "clean_summary"
    CONSUMABLE = "consumable"
    LAST_CLEAN_RECORD = "last_clean_record"


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
