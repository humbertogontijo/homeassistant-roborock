import logging

import voluptuous as vol

from homeassistant.components.vacuum import VacuumEntityFeature, StateVacuumEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import STATE_CODES, FAN_SPEED_CODES, ATTR_ERROR_CODE, ERROR_CODES, ATTR_FAN_SPEED, ATTR_STATE, \
    ATTR_MOP_MODE, MOP_MODE_CODES, ATTR_MOP_INTENSITY, MOP_INTENSITY_CODES, RoborockMqttClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_devices: AddEntitiesCallback,
):
    """Set up the Roborock sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "vacuum_goto",
        {
            vol.Required("x_coord"): vol.Coerce(int),
            vol.Required("y_coord"): vol.Coerce(int),
        },
        RoborockVacuum.async_app_goto_target.__name__
    )

    async_add_devices([
        RoborockVacuum(device, coordinator.api) for device in coordinator.api.devices
    ])


class RoborockVacuum(StateVacuumEntity):
    """General Representation of a Roborock sensor."""

    def __init__(self, device: dict, client: RoborockMqttClient):
        """Initialize a sensor."""
        super().__init__()
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
        updated_status = self.send("get_status")
        if updated_status is not None and isinstance(updated_status, dict):
            self._status = updated_status

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
                + VacuumEntityFeature.MAP
        )
        return features

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._name,
            identifiers={(DOMAIN, self._device.get("duid"))},
            manufacturer="Roborock",
            model=self._device.get("model"),
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon of the vacuum cleaner."""
        return "mdi:robot-vacuum"

    @property
    def unique_id(self):
        """Return the unique id of the vacuum cleaner."""
        return "vacuum." + self._device.get("duid")

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self.status

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        state = self._status.get(ATTR_STATE)
        return STATE_CODES.get(state)

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        state_attributes = super().state_attributes
        status = self._status
        status.update(state_attributes)

        # Adding human readable attributes
        attr_codes = [
            [ATTR_STATE, "state_text", STATE_CODES],
            [ATTR_FAN_SPEED, "fan_speed_text", FAN_SPEED_CODES],
            [ATTR_MOP_MODE, "mop_mode_text", MOP_MODE_CODES],
            [ATTR_MOP_INTENSITY, "mop_intensity_text", MOP_INTENSITY_CODES],
            [ATTR_ERROR_CODE, "error_text", ERROR_CODES]
        ]
        for attr, name, codes in attr_codes:
            value = status.get(attr)
            status.update({name: codes.get(value)})

        return status

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._status.get("battery")

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        fan_speed = self._status.get(ATTR_FAN_SPEED)
        return FAN_SPEED_CODES.get(fan_speed)

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEED_CODES.values())

    @property
    def mop_mode(self):
        """Return the mop mode of the vacuum cleaner."""
        mop_mode = self._status.get(ATTR_MOP_MODE)
        return MOP_MODE_CODES.get(mop_mode)

    @property
    def mop_mode_list(self) -> list[str]:
        """Get the list of available mop mode steps of the vacuum cleaner."""
        return list(MOP_MODE_CODES.values())

    @property
    def mop_intensity(self):
        """Return the mop intensity of the vacuum cleaner."""
        mop_intensity = self._status.get(ATTR_MOP_INTENSITY)
        return MOP_INTENSITY_CODES.get(mop_intensity)

    @property
    def mop_intensity_list(self) -> list[str]:
        """Get the list of available mop intensity steps of the vacuum cleaner."""
        return list(MOP_INTENSITY_CODES.values())

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
            "set_custom_mode", [k for k, v in FAN_SPEED_CODES.items() if v == fan_speed]
        )

    def set_mop_mode(self, mop_mode: str, **kwargs: any) -> None:
        self.send(
            "set_mop_mode", [k for k, v in MOP_MODE_CODES.items() if v == mop_mode]
        )

    def set_mop_intensity(self, mop_intensity: str, **kwargs: any) -> None:
        self.send(
            "set_water_box_custom_mode", [k for k, v in MOP_INTENSITY_CODES.items() if v == mop_intensity]
        )

    async def async_app_goto_target(self, x_coord: int, y_coord: int) -> None:
        self.send("app_goto_target", [x_coord, y_coord])

    def send_command(
            self,
            command,
            params=None,
            **kwargs: any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        return self.send(command, params)

    def start_pause(self, **kwargs: any) -> None:
        self.send("app_pause")
