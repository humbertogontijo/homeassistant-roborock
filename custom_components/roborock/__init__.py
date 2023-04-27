"""The Roborock component."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from homeassistant.helpers.update_coordinator import UpdateFailed
from roborock import RoborockConnectionException
from roborock.api import RoborockApiClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import UserData, HomeDataProduct, HomeData
from roborock.local_api import RoborockLocalClient

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
    CONF_HOME_DATA,
)
from .coordinator import RoborockDataUpdateCoordinator
from .roborock_typing import RoborockHassDeviceInfo, RoborockHassLocalDeviceInfo
from .utils import get_nested_dict, set_nested_dict

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class DomainData(TypedDict):
    coordinators: list[RoborockDataUpdateCoordinator]
    platforms: list[str]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())
    await async_process_integration_platform_for_component(hass, DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    user_data = UserData.from_dict(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_ENTRY_USERNAME)
    vacuum_options = entry.options.get(VACUUM, {})
    include_shared = (
        vacuum_options.get(CONF_INCLUDE_SHARED, False)
    )

    local_backup = entry.data.get(CONF_LOCAL_BACKUP)
    localdevices_info: dict[str, RoborockHassLocalDeviceInfo] = {
        device_id: RoborockHassLocalDeviceInfo.from_dict(device_info)
        for device_id, device_info in local_backup.items()
    } if local_backup else None
    integration_options = entry.options.get(DOMAIN, {})
    local_integration = (
        integration_options.get(CONF_LOCAL_INTEGRATION, False)
    )

    try:
        api_client = RoborockApiClient(username, base_url)
        _LOGGER.debug("Requesting home data")
        home_data = await api_client.get_home_data(user_data)
        hass.config_entries.async_update_entry(
            entry, data={CONF_HOME_DATA: home_data.as_dict(), **entry.data}
        )
        if home_data is None:
            raise ConfigEntryError("Missing home data. Could not found it in cache")
    except Exception as e:
        if localdevices_info is None and local_integration is None:
            raise e
        conf_home_data = entry.data.get(CONF_HOME_DATA)
        home_data = HomeData.from_dict(conf_home_data) if conf_home_data else None
        if home_data is None:
            raise e

    _LOGGER.debug("Got home data %s", home_data)

    platforms = [platform for platform in PLATFORMS if entry.options.get(platform, True)]

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
        device_info = RoborockHassDeviceInfo(
            device=_device,
            product=product
        )
        map_client = RoborockMqttClient(user_data, device_info)
        if local_integration:
            if localdevices_info is None or (
                localdevices_info.get(_device.duid) and localdevices_info.get(_device.duid).is_durty
            ):
                local_device_info = await get_local_devices_info(map_client, device_info)
                local_device_info_map = {_device.duid: local_device_info}
                if localdevices_info:
                    localdevices_info.update(local_device_info_map)
                else:
                    localdevices_info = local_device_info_map
                hass.config_entries.async_update_entry(
                    entry, data={CONF_LOCAL_BACKUP: localdevices_info, **entry.data}
                )
            else:
                local_device_info = localdevices_info.get(_device.duid)
            main_client = RoborockLocalClient(local_device_info)
        else:
            main_client = map_client
        data_coordinator = RoborockDataUpdateCoordinator(
            hass, main_client, map_client, device_info, home_data.rooms
        )

        domain_data: DomainData = hass.data.setdefault(DOMAIN, {}).get(entry.entry_id)
        if not domain_data:
            domain_data = {"coordinators": [data_coordinator], "platforms": platforms}
            hass.data.setdefault(DOMAIN, {})[entry.entry_id] = domain_data
        else:
            domain_data.get("coordinators").append(data_coordinator)

        try:
            await data_coordinator.async_config_entry_first_refresh()
        except RoborockConnectionException as e:
            if localdevices_info:
                for device_info in localdevices_info.values():
                    device_info.is_durty = True
                hass.config_entries.async_update_entry(
                    entry, data={CONF_LOCAL_BACKUP: localdevices_info, **entry.data}
                )
            raise UpdateFailed from e

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def get_local_devices_info(
    cloud_client: RoborockMqttClient, device_info: RoborockHassDeviceInfo
):
    """Get local device info."""
    network_info = await cloud_client.get_networking()
    if network_info is None:
        raise ConfigEntryError("Failed to fetch vacuum networking info")
    local_device_info = RoborockHassLocalDeviceInfo(
        device=device_info.device,
        product=device_info.product,
        network_info=network_info
    )

    await cloud_client.async_disconnect()
    return local_device_info


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    data: DomainData = hass.data[DOMAIN].get(
        entry.entry_id
    )
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in data.get("platforms")
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        await asyncio.gather(
            *[
                data_coordinator.release()
                for data_coordinator in data.get("coordinators")
            ]
        )

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
