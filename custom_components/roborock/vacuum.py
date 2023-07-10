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
from roborock import RoborockStateCode
from roborock.roborock_typing import RoborockCommand

from . import EntryData
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo

_LOGGER = logging.getLogger(__name__)

STATE_CODE_TO_STATE = {
    RoborockStateCode.starting: STATE_IDLE,  # "Starting"
    RoborockStateCode.charger_disconnected: STATE_IDLE,  # "Charger disconnected"
    RoborockStateCode.idle: STATE_IDLE,  # "Idle"
    RoborockStateCode.remote_control_active: STATE_CLEANING,  # "Remote control active"
    RoborockStateCode.cleaning: STATE_CLEANING,  # "Cleaning"
    RoborockStateCode.returning_home: STATE_RETURNING,  # "Returning home"
    RoborockStateCode.manual_mode: STATE_CLEANING,  # "Manual mode"
    RoborockStateCode.charging: STATE_DOCKED,  # "Charging"
    RoborockStateCode.charging_problem: STATE_ERROR,  # "Charging problem"
    RoborockStateCode.paused: STATE_PAUSED,  # "Paused"
    RoborockStateCode.spot_cleaning: STATE_CLEANING,  # "Spot cleaning"
    RoborockStateCode.error: STATE_ERROR,  # "Error"
    RoborockStateCode.shutting_down: STATE_IDLE,  # "Shutting down"
    RoborockStateCode.updating: STATE_DOCKED,  # "Updating"
    RoborockStateCode.docking: STATE_RETURNING,  # "Docking"
    RoborockStateCode.going_to_target: STATE_CLEANING,  # "Going to target"
    RoborockStateCode.zoned_cleaning: STATE_CLEANING,  # "Zoned cleaning"
    RoborockStateCode.segment_cleaning: STATE_CLEANING,  # "Segment cleaning"
    RoborockStateCode.emptying_the_bin: STATE_DOCKED,  # "Emptying the bin" on s7+
    RoborockStateCode.washing_the_mop: STATE_DOCKED,  # "Washing the mop" on s7maxV
    RoborockStateCode.going_to_wash_the_mop: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    RoborockStateCode.charging_complete: STATE_DOCKED,  # "Charging complete"
    RoborockStateCode.device_offline: STATE_ERROR,  # "Device offline"
}

ATTR_STATUS = "status"
ATTR_MOP_MODE = "mop_mode"
ATTR_MOP_INTENSITY = "mop_intensity"
ATTR_MOP_MODE_LIST = f"{ATTR_MOP_MODE}_list"
ATTR_MOP_INTENSITY_LIST = f"{ATTR_MOP_INTENSITY}_list"
ATTR_ERROR = "error"
ATTR_ROOMS = "rooms"


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
        "vacuum_load_multi_map",
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

    domain_data: EntryData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockVacuum] = []
    for _device_id, device_entry_data in domain_data.get("devices").items():
        coordinator = device_entry_data["coordinator"]
        unique_id = slugify(coordinator.data.device.duid)
        entities.append(RoborockVacuum(unique_id, coordinator.data, coordinator))
    async_add_entities(entities)


class RoborockVacuum(RoborockCoordinatedEntity, StateVacuumEntity, ABC):
    """General Representation of a Roborock vacuum."""

    _attr_name = None

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
        return DOMAIN

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
        return self._device_status.state.name if self._device_status.state else None

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
        return self._device_status.fan_power.name if self._device_status.fan_power else None

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return self._device_status.fan_power.keys() if self._device_status.fan_power else None

    @property
    def mop_mode(self) -> str | None:
        """Return the mop mode of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.mop_mode.name if self._device_status.mop_mode else None

    @property
    def mop_mode_list(self) -> list[str]:
        """Get the list of available mop mode steps of the vacuum cleaner."""
        return self._device_status.mop_mode.keys() if self._device_status.mop_mode else None

    @property
    def mop_intensity(self) -> str | None:
        """Return the mop intensity of the vacuum cleaner."""
        if self._device_status is None:
            return None
        return self._device_status.water_box_mode.name if self._device_status.water_box_mode else None

    @property
    def mop_intensity_list(self) -> list[str]:
        """Get the list of available mop intensity steps of the vacuum cleaner."""
        return self._device_status.water_box_mode.keys() if self._device_status.water_box_mode else None

    @property
    def error(self) -> str | None:
        """Get the error translated if one exist."""
        return self._device_status.error_code.name if self._device_status.error_code else None

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
        """Return if the vacuum is paused."""
        return self.state == STATE_PAUSED or self.state == STATE_ERROR

    async def async_start(self) -> None:
        """Start the vacuum."""
        if self.is_paused() and self._device_status.in_cleaning == 2:
            await self.send(RoborockCommand.RESUME_ZONED_CLEAN)
        elif self.is_paused and self._device_status.in_cleaning == 3:
            await self.send(RoborockCommand.RESUME_SEGMENT_CLEAN)
        else:
            await self.send(RoborockCommand.APP_START)

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        await self.send(RoborockCommand.APP_PAUSE)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        await self.send(RoborockCommand.APP_STOP)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send vacuum back to base."""
        await self.send(RoborockCommand.APP_CHARGE)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Spot clean."""
        await self.send(RoborockCommand.APP_SPOT)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum."""
        await self.send(RoborockCommand.FIND_ME)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        await self.send(
            RoborockCommand.SET_CUSTOM_MODE,
            [v for k, v in self._device_status.fan_power.items() if k == fan_speed],
        )

    async def async_set_mop_mode(self, mop_mode: str, _=None) -> None:
        """Change vacuum mop mode."""
        await self.send(
            RoborockCommand.SET_MOP_MODE,
            [v for k, v in self._device_status.mop_mode.items() if k == mop_mode],
        )

    async def async_set_mop_intensity(self, mop_intensity: str, _=None):
        """Set vacuum mop intensity."""
        await self.send(
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
            [v for k, v in self._device_status.water_box_mode.items() if k == mop_intensity],
        )

    async def async_manual_start(self):
        """Start manual control mode."""
        self.manual_seqnum = 0
        await self.send(RoborockCommand.APP_RC_START)

    async def async_manual_stop(self):
        """Stop manual control mode."""
        self.manual_seqnum = 0
        await self.send(RoborockCommand.APP_RC_END)

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
                f"Given rotation is invalid, should be ]{self.MANUAL_ROTATION_MIN}, {self.MANUAL_ROTATION_MAX}[,"
                f" was {rotation}"
            )
        if velocity < self.MANUAL_VELOCITY_MIN or velocity > self.MANUAL_VELOCITY_MAX:
            raise ValueError(
                f"Given velocity is invalid, should be ]{self.MANUAL_VELOCITY_MIN}, {self.MANUAL_VELOCITY_MAX}[,"
                f" was: {velocity}"
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

    async def async_clean_zone(self, zone: list, repeats: int = 1):
        """Clean selected area for the number of repeats indicated."""
        for _zone in zone:
            _zone.append(repeats)
        _LOGGER.debug("Zone with repeats: %s", zone)
        await self.send(RoborockCommand.APP_ZONED_CLEAN, zone)

    async def async_start_pause(self):
        """Start or pause cleaning if running."""
        if self.state == STATE_CLEANING:
            await self.async_pause()
        else:
            await self.async_start()

    async def async_reset_consumable(self):
        """Reset the consumable data(ex. brush work time)."""
        await self.send(RoborockCommand.RESET_CONSUMABLE)

    async def async_load_multi_map(self, map_flag: int):
        """Load another map."""
        device_info = self.coordinator.data
        is_valid_flag = True
        if device_info.map_mapping:
            is_valid_flag = device_info.map_mapping.get(map_flag)

        if is_valid_flag:
            await self.send(RoborockCommand.LOAD_MULTI_MAP, [map_flag])
            self.set_invalid_map()
        else:
            raise HomeAssistantError(
                f"Map flag {map_flag} is invalid"
            )

    async def async_send_command(
        self,
        command: RoborockCommand,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ):
        """Send a command to a vacuum cleaner."""
        return await self.send(command, params)
