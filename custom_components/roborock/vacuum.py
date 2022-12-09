import logging
import time
from typing import Any

from homeassistant.components.vacuum import VacuumEntityFeature, StateVacuumEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RoborockClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STATE_CODE_TO_STRING = {
    1: "Starting",
    2: "Charger disconnected",
    3: "Idle",
    4: "Remote control active",
    5: "Cleaning",
    6: "Returning home",
    7: "Manual mode",
    8: "Charging",
    9: "Charging problem",
    10: "Paused",
    11: "Spot cleaning",
    12: "Error",
    13: "Shutting down",
    14: "Updating",
    15: "Docking",
    16: "Going to target",
    17: "Zoned cleaning",
    18: "Segment cleaning",
    22: "Emptying the bin",  # on s7+, see #1189
    23: "Washing the mop",  # on a46, #1435
    26: "Going to wash the mop",  # on a46, #1435
    100: "Charging complete",
    101: "Device offline",
}


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


class RoborockVacuum(StateVacuumEntity):
    """General Representation of a Roborock sensor."""

    def __init__(self, device: dict, client: RoborockClient):
        """Initialize a sensor."""
        self._name = device.get("name")
        self._device = device
        self._client = client
        self._status = None
        self._last_update = time.time()
        _LOGGER.debug(f"Added sensor entity {self._name}")

    def send(self, command: str, params: list[Any] | None = None):
        """Send a command to a vacuum cleaner."""
        return self._client.send_request(
            self._device.get("duid"), command, params, True
        )

    def get_status(self):
        now = time.time()
        if self._status is None or now - self._last_update > 10:
            self._status = self.send("get_status")
            self._last_update = time.time()
        return self._status

    @property
    def supported_features(self) -> int:
        """Flag vacuum cleaner features that are supported."""
        features = (
                VacuumEntityFeature.TURN_ON
                + VacuumEntityFeature.TURN_OFF
                + VacuumEntityFeature.PAUSE
                + VacuumEntityFeature.STOP
                + VacuumEntityFeature.RETURN_HOME
                + VacuumEntityFeature.FAN_SPEED
                + VacuumEntityFeature.BATTERY
                + VacuumEntityFeature.STATUS
                + VacuumEntityFeature.SEND_COMMAND
                + VacuumEntityFeature.LOCATE
                + VacuumEntityFeature.CLEAN_SPOT
                + VacuumEntityFeature.MAP
                + VacuumEntityFeature.STATE
                + VacuumEntityFeature.START
        )
        return VacuumEntityFeature(features)

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
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self.status

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return STATE_CODE_TO_STRING.get(self.get_status().get("state"))

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self.get_status().get("battery")

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.get_status().get("fan_power")

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return ["101", "102", "103", "104"]

    def start(self) -> None:
        self.send("app_start")

    def pause(self) -> None:
        self.send("app_stop")

    def stop(self, **kwargs: Any) -> None:
        self.send("app_stop")

    def return_to_base(self, **kwargs: Any) -> None:
        self.send("app_charge")

    def clean_spot(self, **kwargs: Any) -> None:
        self.send("app_spot")

    def locate(self, **kwargs: Any) -> None:
        self.send("find_me")

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        self.send("set_custom_mode", [fan_speed])

    def send_command(
            self,
            command: str,
            params: dict[str, Any] | list[Any] | None = None,
            **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        return self.send(command, params)

    def start_pause(self, **kwargs: Any) -> None:
        self.send("app_pause")
