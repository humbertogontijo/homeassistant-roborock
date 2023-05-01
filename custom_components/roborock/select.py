"""Support for Roborock select."""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock.code_mappings import (
    RoborockEnum,
    RoborockMopIntensityCode,
    RoborockMopModeCode,
)
from roborock.roborock_typing import RoborockCommand

from . import DomainData
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import RoborockHassDeviceInfo


@dataclass
class RoborockSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    api_command: RoborockCommand
    option_code: RoborockEnum


@dataclass
class RoborockSelectDescription(
    SelectEntityDescription, RoborockSelectDescriptionMixin
):
    """Class to describe an Roborock select entity."""


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        name="Mop intensity",
        translation_key="mop_intensity",
        options=RoborockMopIntensityCode.values(),
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        option_code=RoborockMopIntensityCode,
    ),
    RoborockSelectDescription(
        key="mop_mode",
        name="Mop mode",
        translation_key="mop_mode",
        options=RoborockMopModeCode.values(),
        api_command=RoborockCommand.SET_MOP_MODE,
        option_code=RoborockMopModeCode,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock select platform."""
    domain_data: DomainData = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[RoborockSelectEntity] = []
    for coordinator in domain_data.get("coordinators"):
        device_info = coordinator.data
        unique_id = slugify(device_info.device.duid)
        for description in SELECT_DESCRIPTIONS:
            entities.append(
                RoborockSelectEntity(
                    f"{description.key}_{unique_id}",
                    device_info,
                    coordinator,
                    description,
                )
            )
    async_add_entities(entities)


class RoborockSelectEntity(RoborockCoordinatedEntity, SelectEntity, ABC):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSelectDescription,
    ) -> None:
        """Create a select entity."""
        SelectEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device_info, coordinator, unique_id)
        self.entity_description = entity_description
        self.api_command = entity_description.api_command
        self.option_code = entity_description.option_code
        self.key = entity_description.key

    async def async_select_option(self, option: str) -> None:
        """Set the mop intensity."""
        await self.send(
            self.api_command,
            [k for k, v in self.option_code.items() if v == option],
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        if hasattr(self._device_status, self.key) is None:
            return None
        return getattr(self._device_status, self.key)
