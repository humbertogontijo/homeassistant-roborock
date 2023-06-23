"""Support for Roborock device base class."""
from __future__ import annotations

import logging
from typing import Optional

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from roborock.api import RT, RoborockClient
from roborock.containers import Status
from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .roborock_typing import RoborockHassDeviceInfo

_LOGGER = logging.getLogger(__name__)


class RoborockEntity(Entity):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            device_info: RoborockHassDeviceInfo,
            unique_id: str,
            api: RoborockClient,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        self._device_name = device_info.device.name
        self._attr_unique_id = unique_id
        self._device_id = str(device_info.device.duid)
        self._device_model = device_info.model
        self._fw_version = device_info.device.fv
        self._device_info = device_info
        self.api = api

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
        """Check if map is valid."""
        return self._device_info.is_map_valid

    def set_valid_map(self) -> None:
        """Set map as valid to avoid unnecessary updates."""
        self._device_info.is_map_valid = True

    def set_invalid_map(self) -> None:
        """Set map as invalid so it can be updated."""
        self._device_info.is_map_valid = False

    async def send(
            self,
            method: RoborockCommand,
            params: Optional[list | dict] = None,
            return_type: Optional[type[RT]] = None,
    ) -> RT:
        """Send a command to a vacuum cleaner."""
        try:
            response = await self.api.send_command(method, params, return_type)
        except RoborockException as err:
            raise HomeAssistantError(
                f"Error while calling {method.name} with {params}"
            ) from err
        return response


class RoborockCoordinatedEntity(RoborockEntity, CoordinatorEntity[RoborockDataUpdateCoordinator]):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
            self,
            device_info: RoborockHassDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
            unique_id: str | None = None,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntity.__init__(self, device_info, unique_id, coordinator.api)
        CoordinatorEntity.__init__(self, coordinator)
        self._device_name = device_info.device.name
        self._attr_unique_id = unique_id
        self._device_id = str(device_info.device.duid)
        self._device_model = device_info.model
        self._fw_version = device_info.device.fv

    async def send(
            self,
            method: RoborockCommand,
            params: Optional[list | dict] = None,
            return_type: Optional[type[RT]] = None,
    ) -> RT:
        """Send a command to a vacuum cleaner."""
        response = await super().send(method, params, return_type)
        self.coordinator.schedule_refresh()
        return response
