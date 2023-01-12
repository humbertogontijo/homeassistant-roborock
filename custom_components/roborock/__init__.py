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
from .api.containers import UserData, HomeData
from .api.exceptions import RoborockException
from .api.typing import RoborockDeviceInfo, RoborockDeviceProp
from .const import CONF_ENTRY_USERNAME, CONF_USER_DATA, CONF_BASE_URL
from .const import DOMAIN, PLATFORMS

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


def get_translation_file(file_url):
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
    _LOGGER.debug(f"integration async setup entry: {entry.as_dict()}")
    hass.data.setdefault(DOMAIN, {})

    user_data = UserData(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_ENTRY_USERNAME)
    api_client = RoborockClient(username, base_url)
    _LOGGER.debug("Getting home data")
    home_data = await api_client.get_home_data(user_data)
    _LOGGER.debug(f"Got home data {home_data.data}")

    device_map: dict[str, RoborockDeviceInfo] = {}
    for device in home_data.devices + home_data.received_devices:
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
    _LOGGER.debug(f"Using translation {translation}")

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

    def __init__(
            self, hass: HomeAssistant, client: RoborockMqttClient, translation: dict
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.platforms = []
        self._devices_prop: dict[str, RoborockDeviceProp] = {}
        self.translation = translation

    def release(self):
        self.api.release()

    async def _async_update_data(self):
        """Update data via library."""
        try:
            for device_id, _ in self.api.device_map.items():
                device_prop = None
                device_prop = await self.api.get_prop(device_id)
                if device_prop:
                    if device_id in self._devices_prop:
                        self._devices_prop[device_id].update(device_prop)
                    else:
                        self._devices_prop[device_id] = device_prop
            return self._devices_prop
        except (TimeoutError, RoborockException) as ex:
            _LOGGER.exception(ex)
            raise UpdateFailed(ex) from ex


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
