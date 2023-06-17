"""Support for Roborock switch."""
import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand
from roborock.containers import RoborockBase
from config.custom_components.roborock.domain import DomainData

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity, RoborockEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    # Gets the status of the switch
    get_value: Callable[[RoborockEntity], Coroutine[Any, Any, RoborockBase]]
    # Evaluate the result of get_value to determine a bool
    evaluate_value: Callable[[RoborockBase], bool]
    # Sets the status of the switch
    set_command: Callable[[RoborockEntity, bool], Coroutine[Any, Any, dict]]
    # Check support of this feature
    check_support: Callable[[RoborockDataUpdateCoordinator], Coroutine[Any, Any, dict]]


@dataclass
class RoborockCoordinatedSwitchDescriptionMixIn:
    """Define an entity description mixin for switch entities."""

    get_value: Callable[[RoborockCoordinatedEntity], bool]
    set_command: Callable[[RoborockCoordinatedEntity, bool], Coroutine[Any, Any, dict]]
    # Check support of this feature
    check_support: Callable[[RoborockDataUpdateCoordinator], dict]


@dataclass
class RoborockSwitchDescription(
    SwitchEntityDescription, RoborockSwitchDescriptionMixin
):
    """Class to describe an Roborock switch entity."""


@dataclass
class RoborockCoordinatedSwitchDescription(
    SwitchEntityDescription, RoborockCoordinatedSwitchDescriptionMixIn
):
    """Class to describe an Roborock switch entity that needs a coordinator."""


SWITCH_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_CHILD_LOCK_STATUS, {"lock_status": 1 if value else 0}
        ),
        get_value=lambda data: data.api.get_child_lock_status(),
        check_support=lambda data: data.api.get_child_lock_status(),
        evaluate_value=lambda data: data.as_dict()["lockStatus"] == 1,
        key="child_lock",
        translation_key="child_lock",
        icon="mdi:account-lock",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_FLOW_LED_STATUS, {"status": 1 if value else 0}
        ),
        get_value=lambda data: data.api.get_flow_led_status(),
        check_support=lambda data: data.api.get_flow_led_status(),
        evaluate_value=lambda data: data.as_dict()["status"] == 1,
        key="flow_led_status",
        translation_key="flow_led_status",
        icon="mdi:alarm-light-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                entity.api.dnd_timer.start_hour,
                entity.api.dnd_timer.start_minute,
                entity.api.dnd_timer.end_hour,
                entity.api.dnd_timer.end_minute,
            ]
            if value
            else entity.send(RoborockCommand.CLOSE_DND_TIMER),
        ),
        check_support=lambda data: data.api.get_dnd_timer(),
        get_value=lambda data: data.api.get_dnd_timer(),
        evaluate_value=lambda data: data.as_dict()["enabled"],
        key="dnd_switch",
        name="DnD switch",
        translation_key="dnd_switch",
        icon="mdi:bell-cancel",
        entity_category=EntityCategory.CONFIG,
    ),
    # RoborockSwitchDescription(
    #     set_command=lambda entity, value: entity.send(
    #         RoborockCommand.SET_VALLEY_ELECTRICITY_TIMER,
    #         [
    #             entity.api.valley_timer.start_hour,
    #             entity.api.valley_timer.start_minute,
    #             entity.api.valley_timer.end_hour,
    #             entity.api.valley_timer.end_minute,
    #         ]
    #         if value
    #         else entity.send(RoborockCommand.CLOSE_VALLEY_ELECTRICITY_TIMER),
    #     ),
    #     check_support=lambda data: data.api.get_valley_electricity_timer(),
    #     get_value=lambda data: data.api.get_valley_electricity_timer(),
    #     evaluate_value=lambda data: data.as_dict()["enabled"],
    #     key="valley_timer",
    #     name="Valley Timer",
    #     translation_key="valley_timer",
    #     icon="",
    #     entity_category=EntityCategory.CONFIG,
    # ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""

    domain_data: DomainData = hass.data[DOMAIN][config_entry.entry_id]
    coordinators: list[RoborockDataUpdateCoordinator] = domain_data["coordinators"]
    possible_entities: list[
        tuple[str, RoborockDataUpdateCoordinator, RoborockSwitchDescription]
    ] = [
        (coordinator.roborock_device_info.device.duid, coordinator, description)
        for coordinator in coordinators
        for description in SWITCH_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(
            description.check_support(coordinator)
            for _, coordinator, description in possible_entities
        ),
        return_exceptions=True,
    )
    valid_entities: list[RoborockNonCoordinatedSwitchEntity] = []
    for posible_entity, result in zip(possible_entities, results):
        if isinstance(result, Exception):
            if not isinstance(result, RoborockException):
                raise result
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockNonCoordinatedSwitchEntity(
                    f"{posible_entity[2].key}_{slugify(posible_entity[0])}",
                    posible_entity[1],
                    posible_entity[2],
                    result,
                )
            )
    async_add_entities(
        valid_entities,
        True,
    )


class RoborockNonCoordinatedSwitchEntity(RoborockEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does not need a coordinator."""

    entity_description: RoborockSwitchDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSwitchDescription,
        initial_value: bool,
    ) -> None:
        """Create a switch entity."""
        self.entity_description = entity_description
        super().__init__(
            unique_id,
            coordinator.device_info,
            coordinator.api,
            coordinator.roborock_device_info,
        )
        self._attr_is_on = initial_value

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_command(self, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.set_command(self, True)

    async def async_update(self) -> None:
        """Update switch."""
        self._attr_is_on = self.entity_description.evaluate_value(
            await self.entity_description.get_value(self)
        )
