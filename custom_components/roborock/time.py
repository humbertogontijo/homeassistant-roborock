"""Support for Roborock time."""
# from __future__ import annotations
# import asyncio
# from collections.abc import Callable, Coroutine
# from dataclasses import dataclass
# from datetime import time
# from typing import Any

# from roborock.roborock_typing import RoborockCommand
# from roborock.containers import RoborockBaseTimer
# from config.custom_components.roborock.domain import DomainData

# from homeassistant.components.time import TimeEntity, TimeEntityDescription
# from homeassistant.config_entries import ConfigEntry
# from homeassistant.const import EntityCategory
# from homeassistant.core import HomeAssistant
# from homeassistant.helpers.entity_platform import AddEntitiesCallback
# from homeassistant.util import slugify

# from .const import DOMAIN
# from .coordinator import RoborockDataUpdateCoordinator
# from .device import RoborockCoordinatedEntity, RoborockEntity


# @dataclass
# class RoborockTimeDescriptionMixin:
#     """Define an entity description mixin for time entities."""

#     # Gets the current time of the entity.
#     get_time: Callable[[RoborockTimeEntity], Coroutine[Any, Any, RoborockBaseTimer]]
#     # Sets the current time of the entity.
#     set_time: Callable[[RoborockTimeEntity, time], Coroutine[Any, Any, dict]]
#     evaluate_value: Callable[[RoborockBaseTimer], time]


# @dataclass
# class RoborockTimeDescription(TimeEntityDescription, RoborockTimeDescriptionMixin):
#     """Class to describe an Roborock time entity."""


# TIME_DESCRIPTIONS: list[RoborockTimeDescription] = [
#     RoborockTimeDescription(
#         key="dnd_start_time",
#         name="DnD start",
#         translation_key="dnd_start_time",
#         icon="mdi:bell-cancel",
#         get_time=lambda data: data.api.dnd_timer.start_time,
#         set_time=lambda entity, desired_time: entity.send(
#             RoborockCommand.SET_DND_TIMER,
#             [
#                 entity.native_value.hour,
#                 entity.native_value.minute,
#                 desired_time.hour,
#                 desired_time.minute,
#             ],
#         ),
#         evaluate_value=lambda data: data.start_time,
#         entity_category=EntityCategory.CONFIG,
#     ),
#     RoborockTimeDescription(
#         key="dnd_end_time",
#         name="DnD end",
#         translation_key="dnd_end_time",
#         icon="mdi:bell-ring",
#         get_time=lambda data: data.api.dnd_timer.end_time,
#         set_time=lambda entity, desired_time: entity.send(
#             RoborockCommand.SET_DND_TIMER,
#             [
#                 entity.native_value.hour,
#                 entity.native_value.minute,
#                 desired_time.hour,
#                 desired_time.minute,
#             ],
#         ),
#         evaluate_value=lambda data: data.end_time,
#         entity_category=EntityCategory.CONFIG,
#     ),
# ]


# async def async_setup_entry(
#     hass: HomeAssistant,
#     config_entry: ConfigEntry,
#     async_add_entities: AddEntitiesCallback,
# ) -> None:
#     """Set up Roborock time platform."""

#     domain_data: DomainData = hass.data[DOMAIN][config_entry.entry_id]
#     coordinators: list[RoborockDataUpdateCoordinator] = domain_data["coordinators"]
#     # Run once so that these all cache the data, In the future the switch entity will update them.
#     await asyncio.gather(
#         *(coordinator.api.get_dnd_timer() for coordinator in coordinators)
#     )
#     async_add_entities(
#         RoborockTimeEntity(
#             f"{description.key}_{slugify(coordinator.roborock_device_info.device.duid)}",
#             coordinator,
#             description,
#         )
#         for coordinator in coordinators
#         for description in TIME_DESCRIPTIONS,
#     )


# class RoborockTimeEntity(RoborockEntity, TimeEntity):
#     """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

#     entity_description: RoborockTimeDescription

#     def __init__(
#         self,
#         unique_id: str,
#         coordinator: RoborockDataUpdateCoordinator,
#         entity_description: RoborockTimeDescription,
#     ) -> None:
#         """Create a time entity."""
#         self.entity_description = entity_description
#         super().__init__(
#             unique_id,
#             coordinator.device_info,
#             coordinator.api,
#             coordinator.roborock_device_info,
#         )

#     @property
#     def native_value(self) -> time | None:
#         """Return the value reported by the time."""
#         return self.entity_description.get_time(self)

#     async def async_set_value(self, value: time) -> None:
#         """Set the time."""
#         await self.entity_description.set_time(self, value)
#         await self.entity_description.get_time(
#             self
#         )  # TODO: This is temporary until we setup cacheable commands
