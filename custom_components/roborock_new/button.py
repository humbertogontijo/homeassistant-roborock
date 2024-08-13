"""Support for Roborock button."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock.roborock_typing import RoborockCommand

from . import EntryData
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo


@dataclass
class RoborockButtonDescriptionMixin:
    """Define an entity description mixin for button entities."""

    command: RoborockCommand
    param: list | dict | None


@dataclass
class RoborockButtonDescription(
    ButtonEntityDescription, RoborockButtonDescriptionMixin
):
    """Describes a Roborock button entity."""


CONSUMABLE_BUTTON_DESCRIPTIONS = [
    RoborockButtonDescription(
        key="consumable_reset_sensor",
        device_class=ButtonDeviceClass.UPDATE,
        translation_key="reset_sensor_consumable",
        name="Reset sensor consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["sensor_dirty_time"],
    ),
    RoborockButtonDescription(
        key="consumable_reset_filter",
        device_class=ButtonDeviceClass.UPDATE,
        translation_key="reset_filter_consumable",
        name="Reset filter consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["filter_work_time"],
    ),
    RoborockButtonDescription(
        key="consumable_reset_side_brush",
        device_class=ButtonDeviceClass.UPDATE,
        translation_key="reset_side_brush_consumable",
        name="Reset side brush consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["side_brush_work_time"],
    ),
    RoborockButtonDescription(
        key="consumable_reset_main_brush",
        device_class=ButtonDeviceClass.UPDATE,
        translation_key="reset_main_brush_consumable",
        name="Reset main brush consumable",
        command=RoborockCommand.RESET_CONSUMABLE,
        param=["main_brush_work_time"],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock button platform."""
    domain_data: EntryData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockButtonEntity] = []
    for device_id, device_entry_data in domain_data.get("devices").items():
        coordinator = device_entry_data["coordinator"]
        device_info = coordinator.data
        for description in CONSUMABLE_BUTTON_DESCRIPTIONS:
            entities.append(
                RoborockButtonEntity(
                    f"{description.key}_{slugify(device_id)}",
                    device_info,
                    coordinator,
                    description,
                )
            )
    async_add_entities(entities)


class RoborockButtonEntity(RoborockCoordinatedEntity, ButtonEntity):
    """A class to define Roborock button entities."""

    entity_description: RoborockButtonDescription

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockButtonDescription,
    ) -> None:
        """Create a button entity."""
        super().__init__(device_info, coordinator, unique_id)
        self.entity_description = entity_description

    async def async_press(self) -> None:
        """Press the button."""
        await self.send(self.entity_description.command, self.entity_description.param)
