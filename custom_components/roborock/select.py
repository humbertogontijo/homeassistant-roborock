"""Support for Roborock select."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from roborock.containers import Status
from roborock.roborock_typing import RoborockCommand

from . import EntryData, RoborockHassDeviceInfo
from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockSelectDescriptionMixin:
    """Define an entity description mixin for select entities."""

    api_command: RoborockCommand
    value_fn: Callable[[Status], str]
    options_lambda: Callable[[Status], list[str]]
    option_lambda: Callable[[tuple[str, Status]], list[int]]


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
        value_fn=lambda data: data.water_box_mode.name if data and data.water_box_mode else None,
        options_lambda=lambda data: data.water_box_mode.keys() if data and data.water_box_mode else None,
        option_lambda=lambda data: [
            v for k, v in data[1].water_box_mode.items() if k == data[0]
        ],
    ),
    RoborockSelectDescription(
        key="mop_mode",
        translation_key="mop_mode",
        api_command=RoborockCommand.SET_MOP_MODE,
        value_fn=lambda data: data.mop_mode.name if data and data.mop_mode else None,
        options_lambda=lambda data: data.mop_mode.keys() if data and data.mop_mode else None,
        option_lambda=lambda data: [
            v for k, v in data[1].mop_mode.items() if k == data[0]
        ],
    ),
]


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock select platform."""
    domain_data: EntryData = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[RoborockSelectEntity] = []
    for _device_id, device_entry_data in domain_data.get("devices").items():
        coordinator = device_entry_data["coordinator"]
        device_info = coordinator.data
        unique_id = slugify(device_info.device.duid)
        device_prop = device_info.props
        if device_prop:
            for description in SELECT_DESCRIPTIONS:
                if description.options_lambda(device_prop.status) is not None:
                    entities.append(
                        RoborockSelectEntity(
                            f"{description.key}_{unique_id}",
                            device_info,
                            coordinator,
                            description,
                        )
                    )
        else:
            _LOGGER.warning("Failed setting up selects: No Roborock data")
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
            device_info.props.status
        )
        super().__init__(device_info, coordinator, unique_id)

    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.send(
            self.entity_description.api_command,
            self.entity_description.option_lambda((option, self._device_status)),
        )

    @property
    def current_option(self) -> str | None:
        """Get the current status of the select entity from device_status."""
        return self.entity_description.value_fn(self._device_status)
