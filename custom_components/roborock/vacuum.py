"""Support for Roborock vacuum class."""
from __future__ import annotations

import logging
import math
import time
from abc import ABC
from typing import Any

import voluptuous as vol
from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_STATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock import RoborockMopModeCode, RoborockMopIntensityCode, RoborockFanPowerCode, RoborockStateCode
from roborock.typing import RoborockCommand

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .typing import RoborockHassDeviceInfo

_LOGGER = logging.getLogger(__name__)

STATE_CODE_TO_STATE = {
    RoborockStateCode['1']: STATE_IDLE,  # "Starting"
    RoborockStateCode['2']: STATE_IDLE,  # "Charger disconnected"
    RoborockStateCode['3']: STATE_IDLE,  # "Idle"
    RoborockStateCode['4']: STATE_CLEANING,  # "Remote control active"
    RoborockStateCode['5']: STATE_CLEANING,  # "Cleaning"
    RoborockStateCode['6']: STATE_RETURNING,  # "Returning home"
    RoborockStateCode['7']: STATE_CLEANING,  # "Manual mode"
    RoborockStateCode['8']: STATE_DOCKED,  # "Charging"
    RoborockStateCode['9']: STATE_ERROR,  # "Charging problem"
    RoborockStateCode['10']: STATE_PAUSED,  # "Paused"
    RoborockStateCode['11']: STATE_CLEANING,  # "Spot cleaning"
    RoborockStateCode['12']: STATE_ERROR,  # "Error"
    RoborockStateCode['13']: STATE_IDLE,  # "Shutting down"
    RoborockStateCode['14']: STATE_DOCKED,  # "Updating"
    RoborockStateCode['15']: STATE_RETURNING,  # "Docking"
    RoborockStateCode['16']: STATE_CLEANING,  # "Going to target"
    RoborockStateCode['17']: STATE_CLEANING,  # "Zoned cleaning"
    RoborockStateCode['18']: STATE_CLEANING,  # "Segment cleaning"
    RoborockStateCode['22']: STATE_DOCKED,  # "Emptying the bin" on s7+
    RoborockStateCode['23']: STATE_DOCKED,  # "Washing the mop" on s7maxV
    RoborockStateCode['26']: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    RoborockStateCode['100']: STATE_DOCKED,  # "Charging complete"
    RoborockStateCode['101']: STATE_ERROR,  # "Device offline"
}

ATTR_STATUS = "status"
ATTR_MOP_MODE = "mop_mode"
ATTR_MOP_INTENSITY = "mop_intensity"
ATTR_MOP_MODE_LIST = f"{ATTR_MOP_MODE}_list"
ATTR_MOP_INTENSITY_LIST = f"{ATTR_MOP_INTENSITY}_list"
ATTR_ERROR = "error"


def add_services() -> None:
    """Add the vacuum services to hass."""
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
        cv.make_entity_service_schema(
            {
                vol.Optional("velocity"): vol.All(
                    vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
                ),
                vol.Optional("rotation"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=-179, max=179)
                ),
                vol.Optional("duration"): cv.positive_int,
            }
        ),
        RoborockVacuum.async_remote_control_move.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_move_step",
        cv.make_entity_service_schema(
            {
                vol.Optional("velocity"): vol.All(
                    vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
                ),
                vol.Optional("rotation"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=-179, max=179)
                ),
                vol.Optional("duration"): cv.positive_int,
            }
        ),
        RoborockVacuum.async_remote_control_move_step.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_clean_zone",
        cv.make_entity_service_schema(
            {
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
            }
        ),
        RoborockVacuum.async_clean_zone.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_goto",
        cv.make_entity_service_schema(
            {
                vol.Required("x_coord"): vol.Coerce(int),
                vol.Required("y_coord"): vol.Coerce(int),
            }
        ),
        RoborockVacuum.async_goto.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_clean_segment",
        cv.make_entity_service_schema(
            {
                vol.Required("segments"): vol.Any(vol.Coerce(int), [vol.Coerce(int)]),
                vol.Optional("repeats"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=1, max=3)
                ),
            }
        ),
        RoborockVacuum.async_clean_segment.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_mop_mode",
        cv.make_entity_service_schema(
            {vol.Required("mop_mode"): vol.In(list(RoborockMopModeCode.values()))}
        ),
        RoborockVacuum.async_set_mop_mode.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_mop_intensity",
        cv.make_entity_service_schema(
            {vol.Required("mop_intensity"): vol.In(list(RoborockMopIntensityCode.values()))}
        ),
        RoborockVacuum.async_set_mop_intensity.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_fan_speed",
        cv.make_entity_service_schema(
            {vol.Required("fan_speed"): vol.In(list(RoborockFanPowerCode.values()))}
        ),
        RoborockVacuum.async_set_fan_speed.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_reset_consumables",
        cv.make_entity_service_schema({}),
        RoborockVacuum.async_reset_consumable.__name__,
    )
    platform.async_register_entity_service(
        "camera_load_multi_map",
        cv.make_entity_service_schema(
            {
                vol.Required("map_flag"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=0, max=4)
                ),
            }
        ),
        RoborockVacuum.async_load_multi_map.__name__,
    )


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock sensor."""
    add_services()

    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities = []
    for device_id, device_info in coordinator.devices_info.items():
        unique_id = slugify(device_id)
        entities.append(RoborockVacuum(unique_id, device_info, coordinator))
    async_add_entities(entities)


class RoborockVacuum(RoborockCoordinatedEntity, StateVacuumEntity, ABC):
    """General Representation of a Roborock vacuum."""

    def __init__(
            self,
            unique_id: str,
            device: RoborockHassDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device, coordinator, unique_id)
        self.manual_seqnum = 0
        self._device = device
        self._coordinator = coordinator

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner features that are supported."""
        features = (
                VacuumEntityFeature.TURN_ON
                | VacuumEntityFeature.TURN_OFF
                | VacuumEntityFeature.PAUSE
                | VacuumEntityFeature.STOP
                | VacuumEntityFeature.RETURN_HOME
                | VacuumEntityFeature.FAN_SPEED
                | VacuumEntityFeature.BATTERY
                | VacuumEntityFeature.STATUS
                | VacuumEntityFeature.SEND_COMMAND
                | VacuumEntityFeature.LOCATE
                | VacuumEntityFeature.CLEAN_SPOT
                | VacuumEntityFeature.STATE
                | VacuumEntityFeature.START
                | VacuumEntityFeature.MAP
        )
        return features

    @property
    def icon(self) -> str:
        """Return the icon of the vacuum cleaner."""
        return "mdi:robot-vacuum"

    @property
    def translation_key(self) -> str:
        """Returns the translation key for vacuum."""
        return "roborock_vacuum"

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        if self._device_status is None:
            return None
        state = self._device_status.state
        return STATE_CODE_TO_STATE.get(state)

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        if self._device_status is None:
            return {}
        data: dict[str, Any] = dict(self._device_status.as_dict())

        if self.supported_features & VacuumEntityFeature.BATTERY:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.supported_features & VacuumEntityFeature.FAN_SPEED:
            data[ATTR_FAN_SPEED] = self.fan_speed

        data[ATTR_STATE] = self.state
        data[ATTR_STATUS] = self.status
        data[ATTR_MOP_MODE] = self.mop_mode
        data[ATTR_MOP_INTENSITY] = self.mop_intensity
        data[ATTR_ERROR] = self.error
        data.update(self.capability_attributes)

        return data

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.battery

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.fan_power

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(RoborockFanPowerCode.values())

    @property
    def mop_mode(self) -> str | None:
        """Return the mop mode of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.mop_mode

    @property
    def mop_mode_list(self) -> list[str]:
        """Get the list of available mop mode steps of the vacuum cleaner."""
        return list(RoborockMopModeCode.values())

    @property
    def mop_intensity(self) -> str | None:
        """Return the mop intensity of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.water_box_mode

    @property
    def mop_intensity_list(self) -> list[str]:
        """Get the list of available mop intensity steps of the vacuum cleaner."""
        return list(RoborockMopIntensityCode.values())

    @property
    def error(self) -> str | None:
        """Get the error translated if one exist."""
        if self._device_status is None:
            return None
        return self._device_status.error_code

    @property
    def capability_attributes(self) -> dict[str, list[str]]:
        """Return capability attributes."""
        capability_attributes = {}
        if self.supported_features & VacuumEntityFeature.FAN_SPEED:
            capability_attributes[ATTR_FAN_SPEED_LIST] = self.fan_speed_list
        capability_attributes[ATTR_MOP_MODE_LIST] = self.mop_mode_list
        capability_attributes[ATTR_MOP_INTENSITY_LIST] = self.mop_intensity_list
        return capability_attributes

    def is_paused(self) -> bool:
        """Returns if the vacuum is paused."""
        return self.state == STATE_PAUSED or self.state == STATE_ERROR

    async def async_start(self) -> None:
        """Start the vacuum."""
        if self.is_paused() and self._device_status.in_cleaning == 2:
            await self.send(RoborockCommand.RESUME_ZONED_CLEAN)
        elif self.is_paused and self._device_status.in_cleaning == 3:
            await self.send(RoborockCommand.RESUME_SEGMENT_CLEAN)
        else:
            await self.send(RoborockCommand.APP_START)
        await self.coordinator.async_refresh()

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        await self.send(RoborockCommand.APP_PAUSE)
        await self.coordinator.async_refresh()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        await self.send(RoborockCommand.APP_STOP)
        await self.coordinator.async_refresh()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send vacuum back to base."""
        await self.send(RoborockCommand.APP_CHARGE)
        await self.coordinator.async_refresh()

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Spot clean."""
        await self.send(RoborockCommand.APP_SPOT)
        await self.coordinator.async_refresh()

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum."""
        await self.send(RoborockCommand.FIND_ME)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        await self.send(
            RoborockCommand.SET_CUSTOM_MODE,
            [k for k, v in RoborockFanPowerCode.items() if v == fan_speed],
        )
        await self.coordinator.async_refresh()

    async def async_set_mop_mode(self, mop_mode: str, _=None) -> None:
        """Change vacuum mop mode."""
        await self.send(
            RoborockCommand.SET_MOP_MODE,
            [k for k, v in RoborockMopModeCode.items() if v == mop_mode],
        )
        await self.coordinator.async_refresh()

    async def async_set_mop_intensity(self, mop_intensity: str, _=None):
        """Set vacuum mop intensity."""
        await self.send(
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
            [k for k, v in RoborockMopIntensityCode.items() if v == mop_intensity],
        )
        await self.coordinator.async_refresh()

    async def async_manual_start(self):
        """Start manual control mode."""
        self.manual_seqnum = 0
        await self.send(RoborockCommand.APP_RC_START)
        await self.coordinator.async_refresh()

    async def async_manual_stop(self):
        """Stop manual control mode."""
        self.manual_seqnum = 0
        await self.send(RoborockCommand.APP_RC_END)
        await self.coordinator.async_refresh()

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

        await self.send(RoborockCommand.APP_RC_MOVE, [params])

    async def async_manual_control_once(
            self, rotation: int, velocity: float, duration: int = MANUAL_DURATION_DEFAULT
    ):
        """Start the remote control mode and executes the action once before deactivating the mode."""
        number_of_tries = 3
        await self.async_manual_start()
        while number_of_tries > 0:
            if self.state == STATE_CODE_TO_STATE[7]:
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
            self,
            rotation: int = 0,
            velocity: float = 0.2,
            duration: int = MANUAL_DURATION_DEFAULT,
    ):
        """Move vacuum one step with remote control mode."""
        await self.async_manual_control_once(rotation, velocity, duration)

    async def async_goto(self, x_coord: int, y_coord: int):
        """Send vacuum to x,y location."""
        await self.send(RoborockCommand.APP_GOTO_TARGET, [x_coord, y_coord])

    async def async_clean_segment(self, segments, repeats: int | None = None):
        """Clean the specified segments(s)."""
        if isinstance(segments, int):
            segments = [segments]

        params = segments
        if repeats is not None:
            params = [{"segments": segments, "repeat": repeats}]

        await self.send(
            RoborockCommand.APP_SEGMENT_CLEAN,
            params,
        )
        await self.coordinator.async_refresh()

    async def async_clean_zone(self, zone: list, repeats: int = 1):
        """Clean selected area for the number of repeats indicated."""
        for _zone in zone:
            _zone.append(repeats)
        _LOGGER.debug("Zone with repeats: %s", zone)
        await self.send(RoborockCommand.APP_ZONED_CLEAN, zone)
        await self.coordinator.async_refresh()

    async def async_start_pause(self):
        """Start or pause cleaning if running."""
        if self.state == STATE_CLEANING:
            await self.async_pause()
        else:
            await self.async_start()

    async def async_reset_consumable(self):
        """Reset the consumable data(ex. brush work time)."""
        await self.send(RoborockCommand.RESET_CONSUMABLE)
        await self.coordinator.async_refresh()

    async def async_load_multi_map(self, map_flag: int):
        """Load another map."""
        maps = self.coordinator.devices_maps.get(self._device_id)
        map_flags = {
            map_info.name or str(map_info.mapflag): map_info.mapflag
            for map_info in maps.map_info
        }
        if any(mapflag == map_flag for name, mapflag in map_flags.items()):
            await self.send(RoborockCommand.LOAD_MULTI_MAP, [map_flag])
            self.set_invalid_map()
        else:
            raise HomeAssistantError(
                f"Map flag {map_flag} is invalid. Available map flags for device are {map_flags}"
            )

    async def async_send_command(
            self,
            command: RoborockCommand,
            params: dict[str, Any] | list[Any] | None = None,
            **kwargs: Any,
    ):
        """Send a command to a vacuum cleaner."""
        return await self.send(command, params)
