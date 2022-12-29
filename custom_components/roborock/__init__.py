"""The Roborock component."""
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.roborock.api.api import RoborockClient, RoborockMqttClient
from .api.containers import Status, UserData, HomeData, CleanSummary
from .api.typing import RoborockDeviceInfo, RoborockDeviceProp
from .const import CONF_ENTRY_USERNAME, CONF_USER_DATA, CONF_BASE_URL
from .const import DOMAIN, PLATFORMS

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up roborock from a config entry."""
    _LOGGER.debug(f"integration async setup entry: {entry.as_dict()}")
    hass.data.setdefault(DOMAIN, {})

    user_data = UserData(entry.data.get(CONF_USER_DATA))
    base_url = entry.data.get(CONF_BASE_URL)
    username = entry.data.get(CONF_ENTRY_USERNAME)
    api_client = RoborockClient(username, base_url)
    _LOGGER.debug("Getting home data")
    home_data = HomeData(await api_client.get_home_data(user_data))

    device_map: dict[str, RoborockDeviceInfo] = {}
    for device in home_data.devices + home_data.received_devices:
        product = next((product for product in home_data.products if product.id == device.product_id), {})
        device_map[device.duid] = RoborockDeviceInfo(device, product)

    client = RoborockMqttClient(user_data, device_map)
    coordinator = RoborockDataUpdateCoordinator(hass, client)

    _LOGGER.debug("Searching for Roborock sensors...")
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


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[dict[str, RoborockDeviceProp]]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: RoborockMqttClient) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.platforms = []

    async def _async_update_data(self):
        """Update data via library."""
        try:
            if not self.api.is_connected():
                try:
                    _LOGGER.debug("Connecting to roborock mqtt")
                    await self.api.connect()
                except Exception as exception:
                    raise UpdateFailed(exception) from exception
            devices_prop = {}
            for device_id, _ in self.api.device_map.items():
                device_prop = await self.api.get_prop(device_id)
                devices_prop[device_id] = device_prop
            return devices_prop
        except Exception as e:
            _LOGGER.exception(e)
            raise e


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
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

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
