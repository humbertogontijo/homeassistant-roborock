"""The Roborock component."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from homeassistant.helpers.update_coordinator import UpdateFailed
from roborock import (
    RoborockMqttClient,
    RoborockLocalClient,
    RoborockCommand,
    RoborockLocalDeviceInfo,
    RoborockConnectionException,
)
from roborock.api import RoborockApiClient
from roborock.containers import UserData, HomeDataProduct, NetworkInfo

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
from .typing import RoborockHassDeviceInfo
from .utils import get_nested_dict, set_nested_dict

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())
    await async_process_integration_platform_for_component(hass, DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    user_data = UserData.from_dict(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_ENTRY_USERNAME)
    vacuum_options = entry.options.get(VACUUM)
    include_shared = (
        vacuum_options.get(CONF_INCLUDE_SHARED) if vacuum_options else False
    )

    local_backup = entry.data.get(CONF_LOCAL_BACKUP)
    localdevices_info: dict[str, RoborockLocalDeviceInfo] = {
        device_id: RoborockLocalDeviceInfo.from_dict(device_info)
        for device_id, device_info in local_backup.items()
    } if local_backup else None
    integration_options = entry.options.get(DOMAIN)
    local_integration = (
        integration_options.get(CONF_LOCAL_INTEGRATION)
        if integration_options
        else False
    )

    devices_info: dict[str, RoborockHassDeviceInfo] = {}
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
                    product
                    for product in home_data.products
                    if product.id == _device.product_id
                ),
                {},
            )
            devices_info[_device.duid] = RoborockHassDeviceInfo(
                device=_device,
                product=product,
                is_map_valid=False
            )

    except Exception as e:
        if localdevices_info is None and local_integration is None:
            raise e

    map_client = RoborockMqttClient(user_data, devices_info)
    if local_integration:
        if localdevices_info is None:
            localdevices_info = await get_local_devices_info(map_client, devices_info)
            hass.config_entries.async_update_entry(
                entry, data={CONF_LOCAL_BACKUP: localdevices_info, **entry.data}
            )
        main_client = RoborockLocalClient(localdevices_info)
    else:
        main_client = map_client
    local_coordinator = RoborockDataUpdateCoordinator(
        hass, main_client, map_client, devices_info
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = local_coordinator

    try:
        await local_coordinator.async_config_entry_first_refresh()
    except RoborockConnectionException as e:
        await remove_entry_key(entry, hass, CONF_LOCAL_BACKUP)
        raise UpdateFailed from e

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            local_coordinator.platforms.append(platform)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def remove_entry_key(entry, hass, key):
    entry_data = dict(entry.data)
    entry_data.pop(key, None)
    hass.config_entries.async_update_entry(
        entry, data=entry_data
    )


async def get_local_devices_info(
    cloud_client: RoborockMqttClient, devices_info: dict[str, RoborockHassDeviceInfo]
):
    """Get local device info."""
    localdevices_info: dict[str, RoborockLocalDeviceInfo] = {}
    for device_id, device_info in devices_info.items():
        network_info = await cloud_client.get_networking(device_id)
        localdevices_info[device_id] = RoborockLocalDeviceInfo(
            device=device_info.device,
            network_info=network_info
        )
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
