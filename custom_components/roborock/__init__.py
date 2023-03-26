"""The Roborock component."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from roborock.api import RoborockClient, RoborockMqttClient
from roborock.containers import HomeDataProduct, UserData
from roborock.typing import RoborockDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from homeassistant.helpers.translation import async_get_translations

from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_USERNAME,
    CONF_INCLUDE_SHARED,
    CONF_USER_DATA,
    DOMAIN,
    PLATFORMS,
    SENSOR,
    VACUUM,
)
from .coordinator import RoborockDataUpdateCoordinator
from .utils import get_nested_dict, set_nested_dict

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def get_translation_from_hass(
    hass: HomeAssistant, language: str
) -> dict[str, Any]:
    """Get translation from hass."""
    entity_translations = await async_get_translations(hass, language, "entity", tuple([DOMAIN]))
    if not entity_translations:
        return {}
    data: dict[str, Any] = {}
    for key, value in entity_translations.items():
        set_nested_dict(data, key, value)
    states_translation = get_nested_dict(
        data, f"component.{DOMAIN}.entity.{SENSOR}", {}
    )
    return states_translation


async def get_translation(hass: HomeAssistant) -> dict[str, Any]:
    """Get translation."""
    if hasattr(hass.config, "language"):
        language = hass.config.language
        translation = await get_translation_from_hass(hass, language)
        if translation:
            return translation
        wide_language = language.split("-")[0]
        wide_translation = await get_translation_from_hass(hass, wide_language)
        if wide_translation:
            return wide_translation
    return await get_translation_from_hass(hass, "en")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())
    await async_process_integration_platform_for_component(hass, DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    user_data = UserData(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_ENTRY_USERNAME)
    vacuum_options = entry.options.get(VACUUM)
    include_shared = (
        vacuum_options.get(CONF_INCLUDE_SHARED) if vacuum_options else False
    )
    api_client = RoborockClient(username, base_url)
    _LOGGER.debug("Getting home data")
    home_data = await api_client.get_home_data(user_data)
    _LOGGER.debug("Got home data %s", home_data)

    device_map: dict[str, RoborockDeviceInfo] = {}
    devices = (
        home_data.devices + home_data.received_devices
        if include_shared
        else home_data.devices
    )
    for device in devices:
        product: HomeDataProduct = next(
            (
                HomeDataProduct(product)
                for product in home_data.products
                if product.id == device.product_id
            ),
            {},
        )
        device_map[device.duid] = RoborockDeviceInfo(device, product)

    translation = await get_translation(hass)
    _LOGGER.debug("Using translation %s", translation)

    client = RoborockMqttClient(user_data, device_map)
    coordinator = RoborockDataUpdateCoordinator(hass, client, translation)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


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
        await coordinator.release()

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
