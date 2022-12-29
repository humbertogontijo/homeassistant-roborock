"""Code to handle a Roborock Device."""
import datetime
import logging

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from . import RoborockDataUpdateCoordinator
from .api.containers import Status
from .api.typing import RoborockDeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def parse_datetime_time(initial_time: datetime.time):
    time = datetime.datetime.now().replace(
        hour=initial_time.hour, minute=initial_time.minute, second=0, microsecond=0
    )

    if time < datetime.datetime.now():
        time += datetime.timedelta(days=1)

    return time.timestamp()


class RoborockCoordinatedEntity(CoordinatorEntity[RoborockDataUpdateCoordinator]):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            device_info: RoborockDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
            unique_id: str = None
    ):
        """Initialize the coordinated Roborock Device."""
        super().__init__(coordinator)
        self._device_name = device_info.device.name
        self._attr_unique_id = unique_id
        self._device_id = str(device_info.device.duid)
        self._device_model = device_info.product.model

    @property
    def _device_status(self) -> Status:
        return self.coordinator.data.get(self._device_id).status

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._device_name,
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Roborock",
            model=self._device_model,
        )

    async def send(self, command: str, params=None):
        """Send a command to a vacuum cleaner."""
        return await self.coordinator.api.send_command(self._device_id, command, params, True)
