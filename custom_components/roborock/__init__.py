"""The Roborock component."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from homeassistant.helpers.translation import async_get_translations
from roborock import (
    RoborockMqttClient,
    RoborockLocalClient,
    RoborockCommand,
    RoborockDeviceInfo,
    RoborockLocalDeviceInfo,
)
from roborock.api import RoborockApiClient
from roborock.containers import UserData, HomeDataProduct, NetworkInfo, RoborockLocalDeviceInfoField, \
    RoborockDeviceInfoField

from .const import (
    CONF_BASE_URL,
    CONF_ENTRY_USERNAME,
    CONF_INCLUDE_SHARED,
    CONF_USER_DATA,
    DOMAIN,
    PLATFORMS,
    SENSOR,
    VACUUM,
    CONF_LOCAL_INTEGRATION,
    CONF_LOCAL_BACKUP,
    CONF_CLOUD_BACKUP,
)
from .coordinator import RoborockDataUpdateCoordinator
from .utils import get_nested_dict, set_nested_dict

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def get_translation_from_hass(
    hass: HomeAssistant, language: str
) -> dict[str, Any]:
    """Get translation from hass."""
    entity_translations = await async_get_translations(
        hass, language, "entity", tuple([DOMAIN])
    )
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

    local_backup = entry.data.get(CONF_LOCAL_BACKUP)
    localdevices_info = RoborockLocalDeviceInfo(local_backup) if local_backup else None
    integration_options = entry.options.get(DOMAIN)
    local_integration = integration_options.get(CONF_LOCAL_INTEGRATION)

    translation = await get_translation(hass)
    _LOGGER.debug("Using translation %s", translation)

    devices_info: dict[str, RoborockDeviceInfo] = {}
    try:
        api_client = RoborockApiClient(username, base_url)
        _LOGGER.debug("Getting home data")
        home_data = await api_client.get_home_data(user_data)
        _LOGGER.debug("Got home data %s", home_data)

        devices = (
            home_data.devices + home_data.received_devices
            if include_shared
            else home_data.devices
        )
        for _device in devices:
            product: HomeDataProduct = next(
                (
                    HomeDataProduct(product)
                    for product in home_data.products
                    if product.id == _device.product_id
                ),
                {},
            )
            devices_info[_device.duid] = RoborockDeviceInfo({
                RoborockDeviceInfoField.DEVICE: _device,
                RoborockDeviceInfoField.PRODUCT: product
            })

    except Exception as e:
        if not localdevices_info and not local_integration:
            raise e

    if local_integration:
        if not localdevices_info:
            localdevices_info = await get_local_devices_info(devices_info, user_data)
            hass.config_entries.async_update_entry(
                entry, data={CONF_LOCAL_BACKUP: localdevices_info, **entry.data}
            )
        client = RoborockLocalClient(localdevices_info)
    else:
        client = RoborockMqttClient(user_data, devices_info)

    data_coordinator = RoborockDataUpdateCoordinator(
        hass, client, devices_info, translation
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data_coordinator

    await data_coordinator.async_config_entry_first_refresh()

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            data_coordinator.platforms.append(platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def get_local_devices_info(devices_info, user_data):
    cloud_client = RoborockMqttClient(user_data, devices_info)
    localdevices_info: dict[str, RoborockLocalDeviceInfo] = {}
    for device_id, device_info in devices_info.items():
        network_info = NetworkInfo(
            await cloud_client.send_command(
                device_id, RoborockCommand.GET_NETWORK_INFO
            )
        )
        localdevices_info[device_id] = RoborockLocalDeviceInfo({
            RoborockDeviceInfoField.DEVICE: device_info.device,
            RoborockDeviceInfoField.PRODUCT: device_info.product,
            RoborockLocalDeviceInfoField.NETWORK_INFO: network_info
        })
    await cloud_client.async_disconnect()
    return localdevices_info


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    data_coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN].get(
        entry.entry_id
    )
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in data_coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        await data_coordinator.release()

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
