import logging
import math
import time
from abc import ABC

import voluptuous as vol
from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import RoborockDataUpdateCoordinator
from .api.typing import RoborockDeviceInfo
from .const import DOMAIN
from .device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)

STATE_CODES_TO_STATUS = {
    1: "starting",
    2: "charger_disconnected",
    3: "idle",
    4: "remote_control_active",
    5: "cleaning",
    6: "returning_home",
    7: "manual_mode",
    8: "charging",
    9: "charging_problem",
    10: "paused",
    11: "spot_cleaning",
    12: "error",
    13: "shutting_down",
    14: "updating",
    15: "docking",
    16: "going_to_target",
    17: "zoned_cleaning",
    18: "segment_cleaning",
    22: "emptying_the_bin",  # on s7+, see #1189
    23: "washing_the_mop",  # on a46, #1435
    26: "going_to_wash_the_mop",  # on a46, #1435
    100: "charging_complete",
    101: "device_offline",
}

STATE_CODE_TO_STATE = {
    1: STATE_IDLE,  # "Starting"
    2: STATE_IDLE,  # "Charger disconnected"
    3: STATE_IDLE,  # "Idle"
    4: STATE_CLEANING,  # "Remote control active"
    5: STATE_CLEANING,  # "Cleaning"
    6: STATE_RETURNING,  # "Returning home"
    7: STATE_CLEANING,  # "Manual mode"
    8: STATE_DOCKED,  # "Charging"
    9: STATE_ERROR,  # "Charging problem"
    10: STATE_PAUSED,  # "Paused"
    11: STATE_CLEANING,  # "Spot cleaning"
    12: STATE_ERROR,  # "Error"
    13: STATE_IDLE,  # "Shutting down"
    14: STATE_DOCKED,  # "Updating"
    15: STATE_RETURNING,  # "Docking"
    16: STATE_CLEANING,  # "Going to target"
    17: STATE_CLEANING,  # "Zoned cleaning"
    18: STATE_CLEANING,  # "Segment cleaning"
    22: STATE_DOCKED,  # "Emptying the bin" on s7+
    23: STATE_DOCKED,  # "Washing the mop" on s7maxV
    26: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    100: STATE_DOCKED,  # "Charging complete"
    101: STATE_ERROR,  # "Device offline"
}

FAN_SPEED_CODES = {
    105: "Off",
    101: "Silent",
    102: "Balanced",
    103: "Turbo",
    104: "Max",
    108: "Max+",
    106: "Custom"
}

MOP_MODE_CODES = {
    300: "standard",
    301: "deep",
    303: "deep_plus",
    302: "custom"
}

MOP_INTENSITY_CODES = {
    200: "off",
    201: "mild",
    202: "moderate",
    203: "intense",
    204: "custom"
}

ERROR_CODES = {
    1: "LiDAR turret or laser blocked. Check for obstruction and retry.",
    2: "Bumper stuck. Clean it and lightly tap to release it.",
    3: "Wheels suspended. Move robot and restart.",
    4: "Cliff sensor error. Clean cliff sensors, move robot away from drops and restart.",
    5: "Main brush jammed. Clean main brush and bearings.",
    6: "Side brush jammed. Remove and clean side brush.",
    7: "Wheels iammed. Move the robot and restart.",
    8: "Robot trapped. Clear obstacles surrounding robot.",
    9: "No dustbin. Install dustbin and filter.",
    12: "Low battery. Recharge and retry.",
    13: "Charging error. Clean charging contacts and retry.",
    14: "Battery error.",
    15: "Wall sensor dirty. Clean wall sensor.",
    16: "Robot tilted. Move to level ground and restart.",
    17: "Side brush error. Reset robot.",
    18: "Fan error. Reset robot.",
    21: "Vertical bumper pressed. Move robot and retry.",
    22: "Dock locator error. Clean and retry.",
    23: "Could not return to dock. Clean dock location beacon and retry.",
    27: "VibraRise system jammed. Check for obstructions.",
    28: "Robot on carpet. Move robot to floor and retry.",
    29: "Filter blocked or wet. Clean, dry, and retry.",
    30: "No-go zone or Invisible Wall detected. Move robot from this area.",
    31: "Cannot cross carpet. Move robot across carpet and restart.",
    32: "Internal error. Reset the robot."
}

ATTR_STATUS = "vacuum_status"
ATTR_MOP_MODE = "mop_mode"
ATTR_MOP_INTENSITY = "mop_intensity"
ATTR_MOP_MODE_LIST = f"{ATTR_MOP_MODE}_list"
ATTR_MOP_INTENSITY_LIST = f"{ATTR_MOP_INTENSITY}_list"
ATTR_ERROR = "error"
ATTR_ERROR_CODE = "error_code"


def add_services():
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "vacuum_remote_control_start",
        cv.make_entity_service_schema({}),
        RoborockVacuum.async_remote_control_start.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_stop",
        cv.make_entity_service_schema({}),
        RoborockVacuum.async_remote_control_stop.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_move",
        cv.make_entity_service_schema({
            vol.Optional("velocity"): vol.All(
                vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
            ),
            vol.Optional("rotation"): vol.All(
                vol.Coerce(int), vol.Clamp(min=-179, max=179)
            ),
            vol.Optional("duration"): cv.positive_int,
        }),
        RoborockVacuum.async_remote_control_move.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_move_step",
        cv.make_entity_service_schema({
            vol.Optional("velocity"): vol.All(
                vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
            ),
            vol.Optional("rotation"): vol.All(
                vol.Coerce(int), vol.Clamp(min=-179, max=179)
            ),
            vol.Optional("duration"): cv.positive_int,
        }),
        RoborockVacuum.async_remote_control_move_step.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_clean_zone",
        cv.make_entity_service_schema({
            vol.Required("zone"): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
            vol.Optional("repeats"): vol.All(
                vol.Coerce(int), vol.Clamp(min=1, max=3)
            ),
        }),
        RoborockVacuum.async_clean_zone.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_goto",
        cv.make_entity_service_schema({
            vol.Required("x_coord"): vol.Coerce(int),
            vol.Required("y_coord"): vol.Coerce(int),
        }),
        RoborockVacuum.async_goto.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_clean_segment",
        cv.make_entity_service_schema({vol.Required("segments"): vol.Any(vol.Coerce(int), [vol.Coerce(int)])}),
        RoborockVacuum.async_clean_segment.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_mop_mode",
        cv.make_entity_service_schema({vol.Required("mop_mode"): vol.In(item for item in MOP_MODE_CODES.values())}),
        RoborockVacuum.async_set_mop_mode.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_mop_intensity",
        cv.make_entity_service_schema(
            {vol.Required("mop_intensity"): vol.In(item for item in MOP_INTENSITY_CODES.values())}),
        RoborockVacuum.async_set_mop_intensity.__name__,
    )


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
):
    """Set up the Roborock sensor."""
    add_services()

    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for device_id, device_info in coordinator.api.device_map.items():
        unique_id = slugify(device_id)
        entities.append(RoborockVacuum(unique_id, device_info, coordinator))
    async_add_entities(entities)


class RoborockVacuum(RoborockCoordinatedEntity, StateVacuumEntity, ABC):
    """General Representation of a Roborock sensor."""

    def __init__(self, unique_id: str, device: RoborockDeviceInfo, coordinator: RoborockDataUpdateCoordinator):
        """Initialize a sensor."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device, coordinator, unique_id)
        self.manual_seqnum = 0
        self._device = device
        self._coordinator = coordinator

    @property
    def supported_features(self):
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
    def icon(self):
        """Return the icon of the vacuum cleaner."""
        return "mdi:robot-vacuum"

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        state = self._device_status.state
        return STATE_CODE_TO_STATE.get(state)

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        status = self._device_status.state
        return STATE_CODES_TO_STATUS.get(status)

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = dict(self._device_status.__dict__) or {}

        if self.supported_features & VacuumEntityFeature.BATTERY:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.supported_features & VacuumEntityFeature.FAN_SPEED:
            data[ATTR_FAN_SPEED] = self.fan_speed

        data[ATTR_STATE] = self.state
        data[ATTR_STATUS] = self.status
        data[ATTR_MOP_MODE] = self.mop_mode
        data[ATTR_MOP_INTENSITY] = self.mop_intensity
        data.update(self.capability_attributes)
        error_code = data.get(ATTR_ERROR_CODE)
        error = ERROR_CODES.get(error_code)
        data[ATTR_ERROR] = error

        return data

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._device_status.battery

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        fan_speed = self._device_status.fan_power
        return FAN_SPEED_CODES.get(fan_speed)

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEED_CODES.values())

    @property
    def mop_mode(self):
        """Return the mop mode of the vacuum cleaner."""
        mop_mode = self._device_status.mop_mode
        return MOP_MODE_CODES.get(mop_mode)

    @property
    def mop_mode_list(self):
        """Get the list of available mop mode steps of the vacuum cleaner."""
        return list(MOP_MODE_CODES.values())

    @property
    def mop_intensity(self):
        """Return the mop intensity of the vacuum cleaner."""
        mop_intensity = self._device_status.water_box_mode
        return MOP_INTENSITY_CODES.get(mop_intensity)

    @property
    def mop_intensity_list(self):
        """Get the list of available mop intensity steps of the vacuum cleaner."""
        return list(MOP_INTENSITY_CODES.values())

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        capability_attributes = {}
        if self.supported_features & VacuumEntityFeature.FAN_SPEED:
            capability_attributes[ATTR_FAN_SPEED_LIST] = self.fan_speed_list
        capability_attributes[ATTR_MOP_MODE_LIST] = self.mop_mode_list
        capability_attributes[ATTR_MOP_INTENSITY_LIST] = self.mop_intensity_list
        return capability_attributes

    @property
    async def async_map(self):
        """Return map token."""
        return await self.send("get_map_v1")

    async def async_start(self):
        await self.send("app_start")

    async def async_pause(self):
        await self.send("app_stop")

    async def async_stop(self, **kwargs: any):
        await self.send("app_stop")

    async def async_return_to_base(self, **kwargs: any):
        await self.send("app_charge")

    async def async_clean_spot(self, **kwargs: any):
        await self.send("app_spot")

    async def async_locate(self, **kwargs: any):
        await self.send("find_me")

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: any):
        await self.send(
            "set_custom_mode", [k for k, v in FAN_SPEED_CODES.items() if v == fan_speed]
        )

    async def async_set_mop_mode(self, mop_mode: str, _):
        await self.send(
            "set_mop_mode", [k for k, v in MOP_MODE_CODES.items() if v == mop_mode]
        )

    async def async_set_mop_intensity(self, mop_intensity: str, _):
        await self.send(
            "set_water_box_custom_mode", [k for k, v in MOP_INTENSITY_CODES.items() if v == mop_intensity]
        )

    async def async_manual_start(self):
        """Start manual control mode."""
        self.manual_seqnum = 0
        return await self.send("app_rc_start")

    async def async_manual_stop(self):
        """Stop manual control mode."""
        self.manual_seqnum = 0
        return await self.send("app_rc_end")

    MANUAL_ROTATION_MAX = 180
    MANUAL_ROTATION_MIN = -MANUAL_ROTATION_MAX
    MANUAL_VELOCITY_MAX = 0.3
    MANUAL_VELOCITY_MIN = -MANUAL_VELOCITY_MAX
    MANUAL_DURATION_DEFAULT = 1500

    async def async_manual_control(
            self, rotation: int, velocity: float, duration: int = MANUAL_DURATION_DEFAULT
    ):
        """Give a command over manual control interface."""
        if rotation < self.MANUAL_ROTATION_MIN or rotation > self.MANUAL_ROTATION_MAX:
            raise ValueError(
                "Given rotation is invalid, should be ]%s, %s[, was %s"
                % (self.MANUAL_ROTATION_MIN, self.MANUAL_ROTATION_MAX, rotation)
            )
        if velocity < self.MANUAL_VELOCITY_MIN or velocity > self.MANUAL_VELOCITY_MAX:
            raise ValueError(
                "Given velocity is invalid, should be ]%s, %s[, was: %s"
                % (self.MANUAL_VELOCITY_MIN, self.MANUAL_VELOCITY_MAX, velocity)
            )

        self.manual_seqnum += 1
        params = {
            "omega": round(math.radians(rotation), 1),
            "velocity": velocity,
            "duration": duration,
            "seqnum": self.manual_seqnum,
        }

        await self.send("app_rc_move", [params])

    async def async_manual_control_once(
            self, rotation: int, velocity: float, duration: int = MANUAL_DURATION_DEFAULT
    ):
        """Starts the remote control mode and executes the action once before
        deactivating the mode."""
        number_of_tries = 3
        await self.async_manual_start()
        while number_of_tries > 0:
            if self.status().state_code == 7:
                time.sleep(5)
                await self.async_manual_control(rotation, velocity, duration)
                time.sleep(5)
                return await self.async_manual_stop()

            time.sleep(2)
            number_of_tries -= 1

    async def async_remote_control_start(self):
        """Start remote control mode."""
        await self.async_manual_start()

    async def async_remote_control_stop(self):
        """Stop remote control mode."""
        await self.async_manual_stop()

    async def async_remote_control_move(
            self, rotation: int = 0, velocity: float = 0.3, duration: int = 1500
    ):
        """Move vacuum with remote control mode."""
        await self.async_manual_control(rotation, velocity, duration)

    async def async_remote_control_move_step(
            self, rotation: int = 0, velocity: float = 0.2, duration: int = MANUAL_DURATION_DEFAULT
    ):
        """Move vacuum one step with remote control mode."""
        await self.async_manual_control_once(rotation, velocity, duration)

    async def async_goto(self, x_coord: int, y_coord: int):
        await self.send("app_goto_target", [x_coord, y_coord])

    async def async_clean_segment(self, segments):
        """Clean the specified segments(s)."""
        if isinstance(segments, int):
            segments = [segments]

        await self.send(
            "app_segment_clean",
            segments
        )

    async def async_clean_zone(self, zone: list, repeats: int = 1):
        """Clean selected area for the number of repeats indicated."""
        for _zone in zone:
            _zone.append(repeats)
        _LOGGER.debug("Zone with repeats: %s", zone)
        await self.send("app_zoned_clean", zone)

    async def async_send_command(
            self,
            command,
            params=None,
            **kwargs: any,
    ):
        """Send a command to a vacuum cleaner."""
        return await self.send(command, params)

    async def async_start_pause(self, _):
        await self.send("app_pause")
