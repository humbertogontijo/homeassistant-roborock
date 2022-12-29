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
    def __init__(self, status: Status, dnd_timer: DNDTimer, clean_summary: CleanSummary, consumable: Consumable, last_clean_record: CleanRecord):
        self.status = status
        self.dnd_timer = dnd_timer
        self.clean_summary = clean_summary
        self.consumable = consumable
        self.last_clean_record = last_clean_record
