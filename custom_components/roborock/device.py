"""Support for Roborock device base class."""

from typing import Any

from roborock.containers import Status
from roborock.exceptions import RoborockException
from roborock.api import RoborockClient
from roborock.roborock_typing import RoborockCommand

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RoborockDataUpdateCoordinator
from .roborock_typing import RoborockHassDeviceInfo


class RoborockEntity(Entity):
    """Representation of a base Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        device_info: DeviceInfo,
        api: RoborockClient,
        roborock_device_info: RoborockHassDeviceInfo,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info
        self._api = api
        self._roborock_device_info = roborock_device_info

    @property
    def api(self) -> RoborockClient:
        """Returns the api."""
        return self._api

    @property
    def _device_status(self) -> Status:
        props = self._roborock_device_info.props
        if props is None:
            return Status()
        status = props.status
        if status is None:
            return Status()
        return status

    async def send(
        self, command: RoborockCommand, params: dict[str, Any] | list[Any] | None = None
    ) -> dict:
        """Send a command to a vacuum cleaner."""
        try:
            response = await self._api.send_command(command, params)
        except RoborockException as err:
            raise HomeAssistantError(
                f"Error while calling {command.name} with {params}"
            ) from err

        return response

    def is_valid_map(self) -> bool:
        """Check if map is valid."""
        return self._roborock_device_info.is_map_valid

    def set_valid_map(self) -> None:
        """Set map as valid to avoid unnecessary updates."""
        self._roborock_device_info.is_map_valid = True

    def set_invalid_map(self) -> None:
        """Set map as invalid so it can be updated."""
        self._roborock_device_info.is_map_valid = False


class RoborockCoordinatedEntity(
    RoborockEntity, CoordinatorEntity[RoborockDataUpdateCoordinator]
):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        unique_id: str,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        RoborockEntity.__init__(
            self,
            unique_id=unique_id,
            device_info=coordinator.device_info,
            api=coordinator.api,
            roborock_device_info=coordinator.roborock_device_info,
        )
        CoordinatorEntity.__init__(self, coordinator=coordinator)
        self._attr_unique_id = unique_id

    async def send(
        self,
        command: RoborockCommand,
        params: dict[str, Any] | list[Any] | None = None,
    ) -> dict:
        """Overloads normal send command but refreshes coordinator."""
        res = await super().send(command, params)
        await self.coordinator.async_refresh()
        return res
