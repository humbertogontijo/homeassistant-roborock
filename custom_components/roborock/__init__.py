"""The Roborock component."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.api import RoborockClient, RoborockMqttClient
from .api.containers import UserData, MultiMapsList
from .api.exceptions import RoborockException, RoborockTimeout
from .api.typing import RoborockDeviceInfo, RoborockDeviceProp
from .const import CONF_BASE_URL, CONF_ENTRY_USERNAME, CONF_INCLUDE_SHARED, CONF_USER_DATA
from .const import DOMAIN, PLATFORMS

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


def get_translation_file(file_url):
    """Get translation file."""
    file_path = Path(file_url) if isinstance(file_url, str) else file_url
    if file_path.is_file():
        f = open(file_path)
        translation = json.load(f)
        entity = translation.get("entity")
        if not entity:
            return
        domain = entity.get("sensor")
        if not domain:
            return
        data = {}
        for translation_key, value in domain.items():
            data.update({translation_key: value})
        return data


def get_translation(hass: HomeAssistant):
    """Get translation."""
    path = Path
    if hasattr(hass.config, 'path'):
        path = hass.config.path
    if hasattr(hass.config, 'language'):
        language = hass.config.language
        translation = get_translation_file(
            path(f"custom_components/roborock/translations/{language}.json")
        )
        if translation:
            return translation
        wide_language = language.split("-")[0]
        wide_translation = get_translation_file(
            path(f"custom_components/roborock/translations/{wide_language}.json")
        )
        if wide_translation:
            return wide_translation
    return get_translation_file(
        path("custom_components/roborock/translations/en.json")
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())
    hass.data.setdefault(DOMAIN, {})

    user_data = UserData(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_ENTRY_USERNAME)
    include_shared = entry.options.get(CONF_INCLUDE_SHARED)
    api_client = RoborockClient(username, base_url)

    _LOGGER.debug("Getting home data")
    home_data = await api_client.get_home_data(user_data)
    _LOGGER.debug("Got home data %s", home_data.data)

    device_map: dict[str, RoborockDeviceInfo] = {}

    devices = (
        home_data.devices + home_data.received_devices
        if include_shared
        else home_data.devices
    )

    for device in devices:
        product = next(
            (
                product
                for product in home_data.products
                if product.id == device.product_id
            ),
            {},
        )
        device_map[device.duid] = RoborockDeviceInfo(device, product)

    translation = get_translation(hass)
    _LOGGER.debug("Using translation %s", translation)

    client = RoborockMqttClient(user_data, device_map)
    coordinator = RoborockDataUpdateCoordinator(hass, client, translation)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


class RoborockDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, RoborockDeviceProp]]
):
    """Class to manage fetching data from the API."""

    ACCEPTABLE_NUMBER_OF_TIMEOUTS = 3

    def __init__(
            self, hass: HomeAssistant, client: RoborockMqttClient, translation: dict
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.platforms = []
        self._devices_prop: dict[str, RoborockDeviceProp] = {}
        self.translation = translation
        self.devices_maps: dict[str, MultiMapsList] = {}
        self.retries = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)
        self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)

    def release(self):
        """Disconnect from API."""
        self.api.release()

    async def _get_device_multi_maps_list(self, device_id: str):
        """Get multi maps list."""
        multi_maps_list = await self.api.get_multi_maps_list(device_id)
        if multi_maps_list:
            self.devices_maps[device_id] = multi_maps_list

    async def _get_device_prop(self, device_id: str):
        """Get device properties."""
        device_prop = await self.api.get_prop(device_id)
        if device_id in self._devices_prop:
            self._devices_prop[device_id].update(device_prop)
        else:
            self._devices_prop[device_id] = device_prop

    async def _async_update_data(self):
        """Update data via library."""
        try:
            funcs = []
            for device_id, _ in self.api.device_map.items():
                if not self.devices_maps.get(device_id):
                    funcs.append(self._get_device_multi_maps_list(device_id))
                funcs.append(self._get_device_prop(device_id))
            await asyncio.gather(*funcs)
            self._timeout_countdown = int(self.ACCEPTABLE_NUMBER_OF_TIMEOUTS)
        except (RoborockTimeout, RoborockException) as ex:
            if self._timeout_countdown > 0:
                _LOGGER.debug("Timeout updating coordinator. Acceptable timeouts countdown = %s", self._timeout_countdown)
                self._timeout_countdown -= 1
            else:
                raise UpdateFailed(ex) from ex
        if self._devices_prop:
            return self._devices_prop
        # Only for the first attempt
        if self.retries > 0:
            self.retries -= 1
            return self._async_update_data()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.release()

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
