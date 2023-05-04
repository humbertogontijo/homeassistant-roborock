"""Support for Roborock select."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from roborock.code_mappings import ModelSpecification
from roborock.containers import Status
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .roborock_typing import DomainData, RoborockHassDeviceInfo


@dataclass
class RoborockSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    api_command: RoborockCommand
    value_fn: Callable[[Status], str]
    options_lambda: Callable[[ModelSpecification], list[str]]
    option_lambda: Callable[[tuple[str, ModelSpecification]], list[int]]


@dataclass
class RoborockSelectDescription(
    SelectEntityDescription, RoborockSelectDescriptionMixin
):
    """Class to describe an Roborock select entity."""


SELECT_DESCRIPTIONS: list[RoborockSelectDescription] = [
    RoborockSelectDescription(
        key="water_box_mode",
        translation_key="mop_intensity",
        api_command=RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
        value_fn=lambda data: data.water_box_mode_enum.name if data.water_box_mode_enum else None,
        options_lambda=lambda data: data.mop_intensity_code.values(),
        option_lambda=lambda data: [
            k for k, v in data[1].mop_intensity_code.items() if v == data[0]
        ],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda data: data.mop_mode_enum.name if data.mop_mode_enum else None,
        options_lambda=lambda data: data.mop_mode_code.values(),
        option_lambda=lambda data: [
            k for k, v in data[1].mop_mode_code.items() if v == data[0]
        ],
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
        if isinstance(coordinator, RoborockDataUpdateCoordinator):
            device_info = coordinator.data
            unique_id = slugify(device_info.device.duid)
            for description in SELECT_DESCRIPTIONS:
                if description.options_lambda(device_info.model_specification) is not None:
                    entities.append(
                        RoborockSelectEntity(
                            f"{description.key}_{unique_id}",
                            device_info,
                            coordinator,
                            description,
                        )
                    )
    async_add_entities(entities)


class RoborockSelectEntity(RoborockCoordinatedEntity, SelectEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockSelectDescription

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSelectDescription,
    ) -> None:
        """Create a select entity."""
        self.entity_description = entity_description
        self._attr_options = self.entity_description.options_lambda(
            device_info.model_specification
        )
        super().__init__(device_info, coordinator, unique_id)

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.send(
            self.entity_description.api_command,
            self.entity_description.option_lambda((option, self._model_specification)),
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        return self.entity_description.value_fn(self._device_status)
