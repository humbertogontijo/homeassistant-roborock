import io
import logging
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import PIL.Image as Image
from homeassistant.components.camera import Camera, SUPPORT_ON_OFF
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from custom_components.roborock import RoborockDataUpdateCoordinator
from custom_components.roborock.api.api import RoborockStatusField
from custom_components.roborock.common.image_handler import ImageHandlerRoborock
from custom_components.roborock.common.map_data import MapData
from custom_components.roborock.common.map_data_parser import MapDataParserRoborock
from custom_components.roborock.common.types import (
    Colors,
    Drawables,
    ImageConfig,
    Sizes,
    Texts,
)
from custom_components.roborock.const import *
from custom_components.roborock.device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

DEFAULT_TRIMS = {CONF_LEFT: 0, CONF_RIGHT: 0, CONF_TOP: 0, CONF_BOTTOM: 0}

DEFAULT_SIZES = {
    CONF_SIZE_VACUUM_RADIUS: 6,
    CONF_SIZE_PATH_WIDTH: 1,
    CONF_SIZE_IGNORED_OBSTACLE_RADIUS: 3,
    CONF_SIZE_IGNORED_OBSTACLE_WITH_PHOTO_RADIUS: 3,
    CONF_SIZE_OBSTACLE_RADIUS: 3,
    CONF_SIZE_OBSTACLE_WITH_PHOTO_RADIUS: 3,
    CONF_SIZE_CHARGER_RADIUS: 6,
}

NON_REFRESHING_STATES = [8]


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for device in coordinator.api.devices:
        device_id = device.get("duid")
        unique_id = slugify(device_id)
        entities.append(VacuumCamera(unique_id, device, coordinator))
    async_add_entities(entities)


class VacuumCamera(RoborockCoordinatedEntity, Camera):
    def __init__(self, unique_id: str, device: dict, coordinator: RoborockDataUpdateCoordinator):
        Camera.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device, coordinator, unique_id)
        self._store_map_image = False
        self._image_config = {CONF_SCALE: 1, CONF_ROTATE: 0, CONF_TRIM: DEFAULT_TRIMS}
        self._sizes = DEFAULT_SIZES
        self._texts = []
        self._drawables = CONF_AVAILABLE_DRAWABLES
        self._colors = ImageHandlerRoborock.COLORS
        self._store_map_raw = False
        self._store_map_path = "/tmp"
        self.content_type = CONTENT_TYPE
        self._status = CameraStatus.INITIALIZING
        self._device = device
        self._should_poll = True
        self._attributes = CONF_AVAILABLE_ATTRIBUTES
        self._map_data = None
        self._image = None

    def camera_image(
            self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        return self._image

    def turn_on(self):
        self._should_poll = True

    def turn_off(self):
        self._should_poll = False

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        attributes = {}
        if self._map_data is not None:
            attributes.update(self.extract_attributes(self._map_data, self._attributes))
        return attributes

    @property
    def should_poll(self) -> bool:
        return self._should_poll

    @staticmethod
    def extract_attributes(
            map_data: MapData, attributes_to_return: List[str]
    ) -> Dict[str, Any]:
        attributes = {}
        rooms = []
        if map_data.rooms is not None:
            rooms = dict(
                filter(
                    lambda x: x[0] is not None,
                    ((x[0], x[1].name) for x in map_data.rooms.items()),
                )
            )
            if len(rooms) == 0:
                rooms = list(map_data.rooms.keys())
        for name, value in {
            ATTRIBUTE_CALIBRATION: map_data.calibration(),
            ATTRIBUTE_CHARGER: map_data.charger,
            ATTRIBUTE_CLEANED_ROOMS: map_data.cleaned_rooms,
            ATTRIBUTE_GOTO: map_data.goto,
            ATTRIBUTE_GOTO_PATH: map_data.goto_path,
            ATTRIBUTE_GOTO_PREDICTED_PATH: map_data.predicted_path,
            ATTRIBUTE_IGNORED_OBSTACLES: map_data.ignored_obstacles,
            ATTRIBUTE_IGNORED_OBSTACLES_WITH_PHOTO: map_data.ignored_obstacles_with_photo,
            ATTRIBUTE_IMAGE: map_data.image,
            ATTRIBUTE_IS_EMPTY: map_data.image.is_empty,
            ATTRIBUTE_MAP_NAME: map_data.map_name,
            ATTRIBUTE_NO_GO_AREAS: map_data.no_go_areas,
            ATTRIBUTE_NO_MOPPING_AREAS: map_data.no_mopping_areas,
            ATTRIBUTE_OBSTACLES: map_data.obstacles,
            ATTRIBUTE_OBSTACLES_WITH_PHOTO: map_data.obstacles_with_photo,
            ATTRIBUTE_PATH: map_data.path,
            ATTRIBUTE_ROOM_NUMBERS: rooms,
            ATTRIBUTE_ROOMS: map_data.rooms,
            ATTRIBUTE_VACUUM_POSITION: map_data.vacuum_position,
            ATTRIBUTE_VACUUM_ROOM: map_data.vacuum_room,
            ATTRIBUTE_VACUUM_ROOM_NAME: map_data.vacuum_room_name,
            ATTRIBUTE_WALLS: map_data.walls,
            ATTRIBUTE_ZONES: map_data.zones,
        }.items():
            if name in attributes_to_return:
                attributes[name] = value
        return attributes

    async def async_update(self) -> None:
        try:
            await self._handle_map_data()
        except Exception as e:
            _LOGGER.exception(e)
            self._set_map_data(
                MapDataParserRoborock.create_empty(self._colors, str(self._status))
            )

    def enable_motion_detection(self) -> None:
        pass

    def disable_motion_detection(self) -> None:
        pass

    async def get_map(
            self,
            colors: Colors,
            drawables: Drawables,
            texts: Texts,
            sizes: Sizes,
            image_config: ImageConfig,
            store_map_path: Optional[str] = None,
    ) -> Tuple[Optional[MapData], bool]:
        response = await self.send("get_map_v1")
        if not response:
            return None, False
        elif not isinstance(response, bytes):
            _LOGGER.debug(f"Received not bytes value for get_map_v1 function: {response}")
            return None, False
        map_stored = False
        if store_map_path is not None:
            raw_map_file = open(f"{store_map_path}/map_data_{self.unique_id}.raw", "wb")
            raw_map_file.write(response)
            raw_map_file.close()
            map_stored = True
        map_data = self.decode_map(
            response, colors, drawables, texts, sizes, image_config
        )
        if map_data is None:
            return None, map_stored
        return map_data, map_stored

    def decode_map(
            self,
            raw_map: bytes,
            colors: Colors,
            drawables: Drawables,
            texts: Texts,
            sizes: Sizes,
            image_config: ImageConfig,
    ) -> Optional[MapData]:
        return MapDataParserRoborock.parse(
            raw_map, colors, drawables, texts, sizes, image_config
        )

    def _valid_refresh_state(self):
        updated_status = self._device_status
        if (
                updated_status is not None
                and isinstance(updated_status, dict)
                and updated_status.get(RoborockStatusField.STATE) not in NON_REFRESHING_STATES
        ):
            return True
        return False

    async def _handle_map_data(self):
        if self._image is not None and not self._valid_refresh_state():
            return
        _LOGGER.debug("Retrieving map from Roborock MQTT")
        store_map_path = self._store_map_path if self._store_map_raw else None
        map_data, map_stored = await self.get_map(
            self._colors,
            self._drawables,
            self._texts,
            self._sizes,
            self._image_config,
            store_map_path,
        )
        if map_data is not None:
            # noinspection PyBroadException
            try:
                _LOGGER.debug("Map data retrieved")
                self._map_saved = map_stored
                if map_data.image.is_empty:
                    _LOGGER.debug("Map is empty")
                    self._status = CameraStatus.EMPTY_MAP
                    if self._map_data is None or self._map_data.image.is_empty:
                        self._set_map_data(map_data)
                else:
                    _LOGGER.debug("Map is ok")
                    self._set_map_data(map_data)
                    self._status = CameraStatus.OK
            except:
                _LOGGER.warning("Unable to parse map data")
                self._status = CameraStatus.UNABLE_TO_PARSE_MAP
        else:
            _LOGGER.warning("Unable to retrieve map data")
            self._status = CameraStatus.UNABLE_TO_RETRIEVE_MAP

    def _set_map_data(self, map_data: MapData):
        img_byte_arr = io.BytesIO()
        map_data.image.data.save(img_byte_arr, format="PNG")
        self._image = img_byte_arr.getvalue()
        self._map_data = map_data
        self._store_image()

    def _store_image(self):
        if self._store_map_image:
            try:
                image = Image.open(io.BytesIO(self._image))
                image.save(f"{self._store_map_path}/map_image_{self.unique_id}.png")
            except:
                _LOGGER.warning("Error while saving image")


class CameraStatus(Enum):
    EMPTY_MAP = "Empty map"
    FAILED_LOGIN = "Failed to login"
    FAILED_TO_RETRIEVE_DEVICE = "Failed to retrieve device"
    FAILED_TO_RETRIEVE_MAP_FROM_VACUUM = "Failed to retrieve map from vacuum"
    INITIALIZING = "Initializing"
    NOT_LOGGED_IN = "Not logged in"
    OK = "OK"
    LOGGED_IN = "Logged in"
    TWO_FACTOR_AUTH_REQUIRED = "Two factor auth required (see logs)"
    UNABLE_TO_PARSE_MAP = "Unable to parse map"
    UNABLE_TO_RETRIEVE_MAP = "Unable to retrieve map"

    def __str__(self):
        return str(self._value_)
