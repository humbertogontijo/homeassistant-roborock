"""Coordinatory for Roborock devices."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from roborock.api import RoborockClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import MultiMapsList
from roborock.exceptions import RoborockException
from roborock.typing import RoborockDeviceProp

from .const import DOMAIN
from .roborock_typing import RoborockHassDeviceInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RoborockDeviceProp]]
):
    """Class to manage fetching data from the API."""

    def __init__(
            self,
            hass: HomeAssistant,
            client: RoborockClient,
            map_client: RoborockMqttClient,
            devices_info: dict[str, RoborockHassDeviceInfo],
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.map_api = map_client
        self.platforms: list[str] = []
        self.devices_maps: dict[str, MultiMapsList] = {}
        self.devices_info = devices_info

    def schedule_refresh(self) -> None:
        """Schedule coordinator refresh after 1 second."""
        self.hass.loop.call_later(1, lambda: asyncio.create_task(self.async_refresh()))

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_disconnect()

    async def fill_device_multi_maps_list(self, device_id: str) -> None:
        """Get multi maps list."""
        multi_maps_list = await self.api.get_multi_maps_list(device_id)
        if multi_maps_list:
            self.devices_maps[device_id] = multi_maps_list

    async def fill_device_prop(self, device_info: RoborockHassDeviceInfo) -> None:
        """Get device properties."""
        device_prop = await self.api.get_prop(device_info.device.duid)
        if device_prop:
            if device_info.props:
                device_info.props.update(device_prop)
            else:
                device_info.props = device_prop

    async def async_config_entry_first_refresh(self) -> None:
        for device_id, _ in self.devices_info.items():
            if not self.devices_maps.get(device_id):
                await self.fill_device_multi_maps_list(device_id)
        return await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, RoborockDeviceProp]:
        """Update data via library."""
        try:
            for device_info in self.devices_info.values():
                await self.fill_device_prop(device_info)
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
        return {device_id: device_info.props for device_id, device_info in self.devices_info.items()}
