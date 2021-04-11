"""Camera that loads a picture from a local file."""
import logging
import os

import voluptuous as vol
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import ServiceCall

from .const import (
    ATTR_AMAZON_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    CAMERA,
    CAMERA_DATA,
    COORDINATOR,
    DOMAIN,
    SENSOR_NAME,
)

SERVICE_UPDATE_IMAGE = "update_image"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the Camera that works with local files."""
    if CAMERA not in hass.data[DOMAIN][config.entry_id]:
        hass.data[DOMAIN][config.entry_id][CAMERA] = []

    coordinator = hass.data[DOMAIN][config.entry_id][COORDINATOR]
    camera = []
    file_path = f"{os.path.dirname(__file__)}/mail_none.gif"

    for variable in CAMERA_DATA:
        temp_cam = MailCam(hass, variable, config, coordinator, file_path)
        camera.append(temp_cam)
        hass.data[DOMAIN][config.entry_id][CAMERA].append(temp_cam)

    async def _update_image(service: ServiceCall) -> None:
        """Refresh camera image."""
        _LOGGER.debug("Updating image: %s", service)
        cameras = hass.data[DOMAIN][config.entry_id][CAMERA]
        entity_id = None

        if ATTR_ENTITY_ID in service.data.keys():
            entity_id = service.data[ATTR_ENTITY_ID]

        # Update all cameras if no entity_id
        if entity_id is None:
            for cam in cameras:
                cam.update_file_path()

        else:
            for cam in cameras:
                if cam.entity_id in entity_id:
                    cam.update_file_path()
        return True

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_IMAGE,
        _update_image,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_ENTITY_ID): vol.Coerce(str),
            }
        ),
    )

    async_add_entities(camera)


class MailCam(Camera):
    """Representation of a local file camera."""

    def __init__(
        self,
        hass,
        name: str,
        config: ConfigEntry,
        coordinator,
        file_path: str,
    ) -> None:
        """Initialize Local File Camera component."""
        super().__init__()

        self.hass = hass
        self._name = CAMERA_DATA[name][SENSOR_NAME]
        self._type = name
        self.check_file_path_access(file_path)
        self._file_path = file_path
        self._coordinator = coordinator
        self._host = config.data.get(CONF_HOST)
        self._unique_id = config.entry_id

    async def async_camera_image(self):
        """Return image response."""
        try:
            with open(self._file_path, "rb") as file:
                return file.read()
        except FileNotFoundError:
            _LOGGER.warning(
                "Could not read camera %s image from file: %s",
                self._name,
                self._file_path,
            )

    def check_file_path_access(self, file_path: str) -> None:
        """Check that filepath given is readable."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.warning(
                "Could not read camera %s image from file: %s", self._name, file_path
            )

    def update_file_path(self) -> None:
        """Update the file_path."""

        _LOGGER.debug("Camera Update: %s", self._type)

        if self._type == "usps_camera":
            # Update camera image for USPS informed delivery imgages
            image = self._coordinator.data[ATTR_IMAGE_NAME]

            if ATTR_IMAGE_PATH in self._coordinator.data.keys():
                path = self._coordinator.data[ATTR_IMAGE_PATH]
                file_path = f"{self.hass.config.path()}/{path}{image}"
            else:
                file_path = f"{os.path.dirname(__file__)}/mail_none.gif"

        elif self._type == "amazon_camera":
            # Update camera image for Amazon deliveries
            image = self._coordinator.data[ATTR_AMAZON_IMAGE]

            if ATTR_IMAGE_PATH in self._coordinator.data.keys():
                path = f"{self._coordinator.data[ATTR_IMAGE_PATH]}amazon/"
                file_path = f"{self.hass.config.path()}/{path}{image}"
            else:
                file_path = f"{os.path.dirname(__file__)}/no_deliveries.jpg"

        self.check_file_path_access(file_path)
        self._file_path = file_path
        self.schedule_update_ha_state()

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._host}_{self._name}_{self._unique_id}"

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the camera state attributes."""
        return {"file_path": self._file_path, CONF_HOST: self._host}

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        self.update_file_path()
