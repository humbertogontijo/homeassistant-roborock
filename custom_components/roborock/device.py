"""Support for Roborock device base class."""
from __future__ import annotations

import datetime
import logging

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from roborock.containers import Status
from roborock.typing import RoborockCommand

from .typing import RoborockHassDeviceInfo
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def parse_datetime_time(initial_time: datetime.time) -> float:
    """Help to handle time data."""
    time = datetime.datetime.now().replace(
        hour=initial_time.hour, minute=initial_time.minute, second=0, microsecond=0
    )

    if time < datetime.datetime.now():
        time += datetime.timedelta(days=1)

    return time.timestamp()


class RoborockEntityBase(Entity):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            device_info: RoborockHassDeviceInfo,
            unique_id: str | None = None,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        self._device_name = device_info.device.name
        self._attr_unique_id = unique_id
        self._device_id = str(device_info.device.duid)
        self._device_model = device_info.product.model
        self._fw_version = device_info.device.fv
        self._device_info = device_info

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._device_name,
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Roborock",
            model=self._device_model,
            sw_version=self._fw_version,
        )

    @property
    def _device_status(self) -> Status:
        props = self._device_info.props
        if props is None:
            return Status()
        status = props.status
        if status is None:
            return Status()
        return status

    def is_valid_map(self) -> bool:
        return self._device_info.is_map_valid

    def set_valid_map(self) -> None:
        self._device_info.is_map_valid = True

    def set_invalid_map(self) -> None:
        self._device_info.is_map_valid = False


class RoborockCoordinatedEntity(RoborockEntityBase, CoordinatorEntity[RoborockDataUpdateCoordinator]):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            device_info: RoborockHassDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
            unique_id: str | None = None,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntityBase.__init__(self, device_info, unique_id)
        CoordinatorEntity.__init__(self, coordinator)
        self._device_name = device_info.device.name
        self._attr_unique_id = unique_id
        self._device_id = str(device_info.device.duid)
        self._device_model = device_info.product.model
        self._fw_version = device_info.device.fv

    def translate(self, attr: str, value) -> str:
        """Translate value into new language."""
        translation = self.coordinator.translation
        if not translation:
            return value
        key = translation.get(self.translation_key)
        if not key:
            return value
        attr_value = key.get(attr)
        if not attr_value:
            return value
        translated_value = attr_value.get(str(value))
        if not translated_value:
            return value
        return translated_value

    async def send(self, command: RoborockCommand, params=None):
        """Send a command to a vacuum cleaner."""
        return await self.coordinator.api.send_command(self._device_id, command, params)
