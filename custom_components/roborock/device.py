"""Code to handle a Roborock Device."""
import datetime
import logging
from enum import Enum

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from . import RoborockDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RoborockCoordinatedEntity(CoordinatorEntity[RoborockDataUpdateCoordinator]):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            device: dict,
            coordinator: RoborockDataUpdateCoordinator,
            unique_id: str = None
    ):
        """Initialize the coordinated Roborock Device."""
        super().__init__(coordinator)
        self._device_name = device.get("name")
        self._attr_unique_id = unique_id
        self._device_id = device.get("duid")
        self._device = device

    @property
    def _device_status(self):
        return self.coordinator.data.get(self._device_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._device_name,
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Roborock",
            model=self._device.get("model"),
        )

    async def send(self, command: str, params=None):
        """Send a command to a vacuum cleaner."""
        return await self.coordinator.api.send_request(self._device_id, command, params, True)

    def _extract_value_from_attribute(self, attribute):
        device_status = self._device_status
        if device_status:
            value = device_status.get(attribute)
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, datetime.timedelta):
                return self._parse_time_delta(value)
            if isinstance(value, datetime.time):
                return self._parse_datetime_time(value)
            if isinstance(value, datetime.datetime):
                return self._parse_datetime_datetime(value)

            if value is None:
                _LOGGER.debug("Attribute %s is None, this is unexpected", attribute)

            return value

    @staticmethod
    def _parse_time_delta(timedelta: datetime.timedelta) -> int:
        return int(timedelta.total_seconds())

    @staticmethod
    def _parse_datetime_time(initial_time: datetime.time) -> str:
        time = datetime.datetime.now().replace(
            hour=initial_time.hour, minute=initial_time.minute, second=0, microsecond=0
        )

        if time < datetime.datetime.now():
            time += datetime.timedelta(days=1)

        return time.isoformat()

    @staticmethod
    def _parse_datetime_datetime(time: datetime.datetime) -> str:
        return time.isoformat()
