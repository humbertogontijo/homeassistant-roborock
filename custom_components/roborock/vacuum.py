import logging
from typing import Any

from homeassistant.components.vacuum import VacuumEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .api import RoborockClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
):
    """Set up the Roborock sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_devices(
        [RoborockVacuum(device, coordinator.api) for device in coordinator.api.devices]
    )


class RoborockVacuum(VacuumEntity):
    """General Representation of a Roborock sensor."""

    def __init__(self, device: dict, client: RoborockClient):
        """Initialize a sensor."""
        self._attr_is_on = False
        self._name = device.get("name")
        self._device = device
        self._client = client
        _LOGGER.debug("Added sensor entity {}".format(self._name))

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._name,
            identifiers={(DOMAIN, self._device.get("duid"))},
            manufacturer="Roborock",
            model="Vacuum",
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        return "mdi:robot-vacuum"

    @property
    def unique_id(self):
        return format_mac(self._device.get("duid"))

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._attr_is_on

    # @property
    # def state_attributes(self):
    #     """Return the state attributes.
    #
    #     Implemented by component base class, should not be extended by integrations.
    #     Convention for attribute names is lowercase snake_case.
    #     """
    #     return self._device.get('deviceStatus')

    def turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self._client.send_request(self._device.get('duid'), "app_start", [], True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        self._client.send_request(self._device.get('duid'), "app_stop", [], True)

    def stop(self, **kwargs: Any) -> None:
        return self.turn_off()

    def return_to_base(self, **kwargs: Any) -> None:
        self._client.send_request(self._device.get('duid'), "app_charge", [], True)

    def clean_spot(self, **kwargs: Any) -> None:
        self._client.send_request(self._device.get('duid'), "app_spot", [], True)

    def locate(self, **kwargs: Any) -> None:
        self._client.send_request(self._device.get('duid'), "find_me", [], True)

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        # speed = [38, 60 or 77]
        self._client.send_request(self._device.get('duid'), "set_custom_mode", [77], True)

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any
    ) -> None:
        self._client.send_request(self._device.get('duid'), command, params, True)

    def start_pause(self, **kwargs: Any) -> None:
        self._client.send_request(self._device.get('duid'), "app_pause", [], True)
