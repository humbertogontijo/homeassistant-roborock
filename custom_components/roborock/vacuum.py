import logging

from homeassistant.components.vacuum import VacuumEntityFeature, StateVacuumEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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

FAN_SPEEDS = {101: "Silent", 102: "Balanced", 103: "Turbo", 104: "Max"}


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
        self._status = {}
        _LOGGER.debug(f"Added sensor entity {self._name}")

    def send(self, command: str, params=None):
        """Send a command to a vacuum cleaner."""
        return self._client.send_request(
            self._device.get("duid"), command, params, True
        )

    def update(self):
        self._status = self.send("get_status")

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
                + VacuumEntityFeature.STATE
                + VacuumEntityFeature.START
            # + VacuumEntityFeature.MAP
        )
        return features

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
        return self._device.get("duid")

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self.status

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return STATE_CODE_TO_STRING.get(self._status.get("state"))

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._status.get("battery")

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return FAN_SPEEDS.get(self._status.get("fan_power"))

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEEDS.values())

    @property
    def map(self):
        """Return map token."""
        return self.send("get_map_v1")

    def start(self) -> None:
        self.send("app_start")

    def pause(self) -> None:
        self.send("app_stop")

    def stop(self, **kwargs: any) -> None:
        self.send("app_stop")

    def return_to_base(self, **kwargs: any) -> None:
        self.send("app_charge")

    def clean_spot(self, **kwargs: any) -> None:
        self.send("app_spot")

    def locate(self, **kwargs: any) -> None:
        self.send("find_me")

    def set_fan_speed(self, fan_speed: str, **kwargs: any) -> None:
        self.send(
            "set_custom_mode", [k for k, v in FAN_SPEEDS.items() if v == fan_speed]
        )

    def send_command(
            self,
            command,
            params = None,
            **kwargs: any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        return self.send(command, params)

    def start_pause(self, **kwargs: any) -> None:
        self.send("app_pause")
