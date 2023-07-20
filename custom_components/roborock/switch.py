"""Support for Roborock switch."""
from __future__ import annotations

import asyncio
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
from roborock.api import AttributeCache, RoborockClient
from roborock.command_cache import CacheableAttribute

from . import EntryData, RoborockHassDeviceInfo
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, bool], Coroutine[Any, Any, dict]]
    # Attribute from cache
    attribute: str


@dataclass
class RoborockSwitchDescription(
    SwitchEntityDescription, RoborockSwitchDescriptionMixin
):
    """Class to describe an Roborock switch entity."""


SWITCH_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.child_lock_status,
        update_value=lambda cache, value: cache.update_value({"lock_status": 1 if value else 0}),
        attribute="lock_status",
        key="child_lock",
        name="Child lock",
        translation_key="child_lock",
        icon="mdi:account-lock",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.flow_led_status,
        update_value=lambda cache, value: cache.update_value({"status": 1 if value else 0}),
        attribute="status",
        key="flow_led_status",
        name="Status Indicator Light",
        translation_key="flow_led_status",
        icon="mdi:alarm-light-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.dnd_timer,
        update_value=lambda cache, value: cache.update_value([
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]) if value
        else cache.close_value(),
        attribute="enabled",
        key="dnd_switch",
        name="DnD switch",
        translation_key="dnd_switch",
        icon="mdi:bell-cancel",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.valley_electricity_timer,
        update_value=lambda cache, value: cache.update_value([
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]) if value
        else cache.close_value(),
        attribute="enabled",
        key="valley_electricity_switch",
        name="Off-Peak charging switch",
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
    domain_data: EntryData = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = [device_entry_data["coordinator"] for device_entry_data in domain_data.get("devices").values()]
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockSwitchDescription]
    ] = [
        (coordinator, description)
        for coordinator in coordinators
        for description in SWITCH_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(coordinator.api.cache.get(description.cache_key).async_value()
          for coordinator, description in possible_entities),
        return_exceptions=True
    )
    valid_entities: list[RoborockSwitch] = []
    for (coordinator, description), result in zip(possible_entities, results):
        device_info = coordinator.data
        if result is None or isinstance(result, Exception):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockSwitch(
                    f"{description.key}_{slugify(coordinator.data.device.duid)}",
                    device_info,
                    description,
                    coordinator.api,
                )
            )
    async_add_entities(valid_entities)


class RoborockSwitch(RoborockEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does need a coordinator."""

    entity_description: RoborockSwitchDescription

    def __init__(
            self,
            unique_id: str,
            device_info: RoborockHassDeviceInfo,
            description: RoborockSwitchDescription,
            api: RoborockClient,
    ) -> None:
        """Initialize the entity."""
        SwitchEntity.__init__(self)
        RoborockEntity.__init__(self, device_info, unique_id, api)
        self.entity_description = description

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.update_value(self.api.cache.get(self.entity_description.cache_key), False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.update_value(self.api.cache.get(self.entity_description.cache_key), True)

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.api.cache.get(self.entity_description.cache_key).value.get(self.entity_description.attribute) == 1
