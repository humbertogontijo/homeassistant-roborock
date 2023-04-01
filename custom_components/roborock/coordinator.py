"""Coordinatory for Roborock devices."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from roborock.api import RoborockClient
from roborock.containers import MultiMapsList
from roborock.exceptions import RoborockException, RoborockTimeout
from roborock.typing import RoborockDeviceProp

from .const import DOMAIN
from .typing import RoborockDeviceInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RoborockDeviceProp]]
):
    """Class to manage fetching data from the API."""

    ACCEPTABLE_NUMBER_OF_TIMEOUTS = 3

    def __init__(
        self,
        hass: HomeAssistant,
        client: RoborockClient,
        devices_info: dict[str, RoborockDeviceInfo],
        translation: dict,
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.platforms: list[str] = []
        self._devices_prop: dict[str, RoborockDeviceProp] = {}
        self.translation = translation
        self.devices_maps: dict[str, MultiMapsList] = {}
        self.devices_info = devices_info
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)
        self.api.add_status_listener(self.refresh)

    def refresh(self, device_id: str, status: str):
        _LOGGER.debug(f"Device {device_id} updated to status {status}")
        asyncio.run_coroutine_threadsafe(self.async_refresh(), self.hass.loop)

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_disconnect()

    async def _get_device_multi_maps_list(self, device_id: str) -> None:
        """Get multi maps list."""
        multi_maps_list = await self.api.get_multi_maps_list(device_id)
        if multi_maps_list:
            self.devices_maps[device_id] = multi_maps_list

    async def _get_device_prop(self, device_id: str) -> None:
        """Get device properties."""
        device_prop = await self.api.get_prop(device_id)
        if device_prop:
            if device_id in self._devices_prop:
                self._devices_prop[device_id].update(device_prop)
            else:
                self._devices_prop[device_id] = device_prop

    async def async_config_entry_first_refresh(self) -> None:
        for device_id, _ in self.devices_info.items():
            if not self.devices_maps.get(device_id):
                await self._get_device_multi_maps_list(device_id)
        return await super().async_config_entry_first_refresh()

    async def _async_update_data(self) -> dict[str, RoborockDeviceProp]:
        """Update data via library."""
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)
        try:
            for device_id, _ in self.devices_info.items():
                await self._get_device_prop(device_id)
        except RoborockTimeout as ex:
            if self._devices_prop and self._timeout_countdown > 0:
                _LOGGER.debug(
                    "Timeout updating coordinator. Acceptable timeouts countdown = %s",
                    self._timeout_countdown,
                )
                self._timeout_countdown -= 1
            else:
                raise UpdateFailed(ex) from ex
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
        if self._devices_prop:
            return self._devices_prop
        raise UpdateFailed("No device props found")
