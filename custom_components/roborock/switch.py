"""Support for Roborock switch."""
from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock import RoborockBase
from roborock.roborock_typing import RoborockCommand

from . import DomainData, RoborockHassDeviceInfo
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    # Gets the status of the switch
    get_value: Callable[[RoborockCoordinatedEntity], bool]
    # Sets the status of the switch
    set_command: Callable[[RoborockCoordinatedEntity, bool], Coroutine[Any, Any, dict]]
    # Check support of this feature
    check_support: Callable[[RoborockDataUpdateCoordinator], RoborockBase | None]


@dataclass
class RoborockSwitchDescription(
    SwitchEntityDescription, RoborockSwitchDescriptionMixin
):
    """Class to describe an Roborock switch entity."""


SWITCH_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_CHILD_LOCK_STATUS, {"lock_status": 1 if value else 0}
        ),
        get_value=lambda entity: entity.coordinator.data.child_lock_status.lock_status == 1,
        check_support=lambda coordinator: coordinator.data.child_lock_status.lock_status,
        key="child_lock",
        name="Child lock",
        translation_key="child_lock",
        icon="mdi:account-lock",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_FLOW_LED_STATUS, {"status": 1 if value else 0}
        ),
        get_value=lambda entity: entity.coordinator.data.flow_led_status.status == 1,
        check_support=lambda coordinator: coordinator.data.flow_led_status,
        key="flow_led_status",
        name="Flow led status",
        translation_key="flow_led_status",
        icon="mdi:alarm-light-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                entity.coordinator.data.props.dnd_timer.start_hour,
                entity.coordinator.data.props.dnd_timer.start_minute,
                entity.coordinator.data.props.dnd_timer.end_hour,
                entity.coordinator.data.props.dnd_timer.end_minute,
            ],
        )
        if value
        else entity.send(RoborockCommand.CLOSE_DND_TIMER),
        get_value=lambda entity: entity.coordinator.data.props.dnd_timer.enabled == 1,
        check_support=lambda coordinator: coordinator.data.props.dnd_timer,
        key="dnd_switch",
        name="DnD switch",
        translation_key="dnd_switch",
        icon="mdi:bell-cancel",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_VALLEY_ELECTRICITY_TIMER,
            [
                entity.coordinator.data.props.valley_electricity_timer.start_hour,
                entity.coordinator.data.props.valley_electricity_timer.start_minute,
                entity.coordinator.data.props.valley_electricity_timer.end_hour,
                entity.coordinator.data.props.valley_electricity_timer.end_minute,
            ],
        )
        if value
        else entity.send(RoborockCommand.CLOSE_VALLEY_ELECTRICITY_TIMER),
        get_value=lambda entity: entity.coordinator.data.props.valley_electricity_timer.enabled == 1,
        check_support=lambda coordinator: coordinator.data.props.valley_electricity_timer,
        key="valley_electricity_switch",
        name="Valley Electricity switch",
        translation_key="valley_electricity_switch",
        icon="mdi:bell-cancel",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""
    domain_data: DomainData = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = domain_data.get("coordinators")
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockSwitchDescription]
    ] = [
        (coordinator, description)
        for coordinator in coordinators
        for description in SWITCH_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = (
            description.check_support(coordinator)
            for coordinator, description in possible_entities
    )
    valid_entities: list[RoborockSwitch] = []
    for (coordinator, description), result in zip(possible_entities, results):
        device_info = coordinator.data
        if result is None:
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockSwitch(
                    f"{description.key}_{slugify(coordinator.data.device.duid)}",
                    device_info,
                    coordinator,
                    description,
                    result,
                )
            )
    async_add_entities(valid_entities)


class RoborockSwitch(RoborockCoordinatedEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does need a coordinator."""

    entity_description: RoborockSwitchDescription

    def __init__(
            self,
            unique_id: str,
            device_info: RoborockHassDeviceInfo,
            coordinator: RoborockDataUpdateCoordinator,
            description: RoborockSwitchDescription,
            initial_value: bool,
    ) -> None:
        """Initialize the entity."""
        SwitchEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = description
        self._attr_is_on = initial_value

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_command(self, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.set_command(self, True)

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.entity_description.get_value(self)
