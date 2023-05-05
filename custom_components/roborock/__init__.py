"""The Roborock component."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.integration_platform import (
    async_process_integration_platform_for_component,
)
from roborock.api import RoborockApiClient
from roborock.cloud_api import RoborockMqttClient
from roborock.containers import HomeData, HomeDataDevice, HomeDataProduct, UserData
from roborock.local_api import RoborockLocalClient
from roborock.protocol import RoborockProtocol

from .const import (
    CONF_HOME_DATA,
    CONF_INCLUDE_SHARED,
    DOMAIN,
    PLATFORMS,
    VACUUM,
)
from .coordinator import RoborockDataUpdateCoordinator
from .roborock_typing import ConfigEntryData, DeviceNetwork, DomainData, RoborockHassDeviceInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug("Integration async setup entry: %s", entry.as_dict())
    await async_process_integration_platform_for_component(hass, DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    data: ConfigEntryData = entry.data
    user_data = UserData.from_dict(data.get("user_data"))
    base_url = data.get("base_url")
    username = data.get("username")
    vacuum_options = entry.options.get(VACUUM, {})
    include_shared = (
        vacuum_options.get(CONF_INCLUDE_SHARED, False)
    )

    device_network = data.get("device_network")
    if device_network is None:
        device_network = {}

    try:
        api_client = RoborockApiClient(username, base_url)
        _LOGGER.debug("Requesting home data")
        home_data = await api_client.get_home_data(user_data)
        hass.config_entries.async_update_entry(
            entry, data={CONF_HOME_DATA: home_data.as_dict(), **data}
        )
        if home_data is None:
            raise ConfigEntryError("Missing home data. Could not found it in cache")
    except Exception as e:
        conf_home_data = data.get("home_data")
        home_data = HomeData.from_dict(conf_home_data) if conf_home_data else None
        if home_data is None:
            raise e

    _LOGGER.debug("Got home data %s", home_data)

    platforms = [platform for platform in PLATFORMS if entry.options.get(platform, True)]

    domain_data: DomainData = hass.data.setdefault(DOMAIN, {}).setdefault(
        entry.entry_id,
        DomainData(coordinators=[], platforms=platforms)
    )

    devices = (
        home_data.devices + home_data.received_devices
        if include_shared
        else home_data.devices
    )
    for _device in devices:
        device_id = _device.duid
        product: HomeDataProduct = next(
                product
                for product in home_data.products
                if product.id == _device.product_id
        )

        if device_network.get(device_id) is None:
            devices_network = await get_local_devices_info(_device)
            for d_uid, network in devices_network.items():
                device_network[d_uid] = network
            hass.config_entries.async_update_entry(
                entry, data={"device_network": device_network, **data}
            )
        network = device_network.get(device_id)

        device_info = RoborockHassDeviceInfo(
            device=_device,
            model=product.model,
            host=network.get("ip")
        )

        main_client = RoborockLocalClient(device_info)
        map_client = RoborockMqttClient(user_data, device_info)
        data_coordinator = RoborockDataUpdateCoordinator(
            hass, main_client, map_client, device_info, home_data.rooms
        )

        domain_data["coordinators"].append(data_coordinator)

    await asyncio.gather(
        *[
            _coordinator.async_config_entry_first_refresh() for _coordinator in domain_data["coordinators"]
        ]
    )

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def get_local_devices_info(device: HomeDataDevice) -> dict[str, DeviceNetwork]:
    """Get local device info."""
    discovered_devices = await RoborockProtocol(timeout=10).discover()
    if discovered_devices is None:
        raise ConfigEntryError("Failed to fetch vacuum networking info")

    devices_network = {
        discovered_device.duid: DeviceNetwork(ip=discovered_device.ip, mac="")
        for discovered_device in discovered_devices
    }

    if not any(True for device_id, _ in devices_network.items() if device_id == device.duid):
        raise ConfigEntryError(f"Device {device.duid} not found among {devices_network}")

    return devices_network


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
                if isinstance(data_coordinator, RoborockDataUpdateCoordinator)
            ]
        )

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
