"""Camera that loads a picture from a local file."""

from __future__ import annotations

import logging
import os

import voluptuous as vol
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import ServiceCall
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .helpers import generate_delivery_gif
from .const import (
    ATTR_AMAZON_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_UPS_IMAGE,
    ATTR_WALMART_IMAGE,
    CAMERA,
    CAMERA_DATA,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    COORDINATOR,
    DOMAIN,
    SENSOR_NAME,
    VERSION,
)

SERVICE_UPDATE_IMAGE = "update_image"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the Camera that works with local files."""
    if CAMERA not in hass.data[DOMAIN][config.entry_id]:
        hass.data[DOMAIN][config.entry_id][CAMERA] = []

    coordinator = hass.data[DOMAIN][config.entry_id][COORDINATOR]
    camera = []

    for variable in CAMERA_DATA:
        temp_cam = MailCam(hass, variable, config, coordinator)
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
                await cam.update_file_path()

        else:
            for cam in cameras:
                if cam.entity_id in entity_id:
                    await cam.update_file_path()
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


class MailCam(CoordinatorEntity, Camera):
    """Representation of a local file camera."""

    def __init__(
        self,
        hass,
        name: str,
        config: ConfigEntry,
        coordinator,
    ) -> None:
        """Initialize Local File Camera component."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)

        self.hass = hass
        self.config = config
        self._name = CAMERA_DATA[name][SENSOR_NAME]
        self._type = name
        self._host = config.data.get(CONF_HOST)
        self._unique_id = config.entry_id
        # Set custom image paths for each camera type
        self._no_mail = None
        if self._type == "usps_camera":
            if config.data.get(CONF_CUSTOM_IMG):
                self._no_mail = config.data.get(CONF_CUSTOM_IMG_FILE)
        elif self._type == "amazon_camera":
            if config.data.get(CONF_AMAZON_CUSTOM_IMG):
                self._no_mail = config.data.get(CONF_AMAZON_CUSTOM_IMG_FILE)
                _LOGGER.debug("Amazon camera - custom image enabled: %s", self._no_mail)
        elif self._type == "ups_camera":
            if config.data.get(CONF_UPS_CUSTOM_IMG):
                self._no_mail = config.data.get(CONF_UPS_CUSTOM_IMG_FILE)
                _LOGGER.debug("UPS camera - custom image enabled: %s", self._no_mail)
        elif self._type == "walmart_camera":
            if config.data.get(CONF_WALMART_CUSTOM_IMG):
                self._no_mail = config.data.get(CONF_WALMART_CUSTOM_IMG_FILE)
                _LOGGER.debug(
                    "Walmart camera - custom image enabled: %s", self._no_mail
                )
        elif self._type == "generic_camera":
            if config.data.get(CONF_GENERIC_CUSTOM_IMG):
                self._no_mail = config.data.get(CONF_GENERIC_CUSTOM_IMG_FILE)
                _LOGGER.debug(
                    "Generic camera - custom image enabled: %s", self._no_mail
                )

        # Set initial file path based on camera type and custom settings
        if self._type == "usps_camera":
            if config.data.get(CONF_CUSTOM_IMG):
                self._file_path = config.data.get(CONF_CUSTOM_IMG_FILE)
            else:
                self._file_path = f"{os.path.dirname(__file__)}/mail_none.gif"
        elif self._type == "amazon_camera":
            if config.data.get(CONF_AMAZON_CUSTOM_IMG):
                self._file_path = config.data.get(CONF_AMAZON_CUSTOM_IMG_FILE)
                _LOGGER.debug(
                    "Amazon camera - initial file path set to: %s", self._file_path
                )
            else:
                self._file_path = (
                    f"{os.path.dirname(__file__)}/no_deliveries_amazon.jpg"
                )
        elif self._type == "ups_camera":
            if config.data.get(CONF_UPS_CUSTOM_IMG):
                self._file_path = config.data.get(CONF_UPS_CUSTOM_IMG_FILE)
                _LOGGER.debug(
                    "UPS camera - initial file path set to: %s", self._file_path
                )
            else:
                self._file_path = f"{os.path.dirname(__file__)}/no_deliveries_ups.jpg"
        elif self._type == "walmart_camera":
            if config.data.get(CONF_WALMART_CUSTOM_IMG):
                self._file_path = config.data.get(CONF_WALMART_CUSTOM_IMG_FILE)
                _LOGGER.debug(
                    "Walmart camera - initial file path set to: %s", self._file_path
                )
            else:
                self._file_path = (
                    f"{os.path.dirname(__file__)}/no_deliveries_walmart.jpg"
                )
        elif self._type == "generic_camera":
            if config.data.get(CONF_GENERIC_CUSTOM_IMG):
                self._file_path = config.data.get(CONF_GENERIC_CUSTOM_IMG_FILE)
                _LOGGER.debug(
                    "Generic camera - initial file path set to: %s", self._file_path
                )
            else:
                self._file_path = (
                    f"{os.path.dirname(__file__)}/no_deliveries_generic.jpg"
                )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        _LOGGER.debug(
            "Camera %s attempting to read image from: %s", self._name, self._file_path
        )
        try:
            file = await self.hass.async_add_executor_job(open, self._file_path, "rb")
            return file.read()
        except FileNotFoundError:
            _LOGGER.info(
                "Could not read camera %s image from file: %s",
                self._name,
                self._file_path,
            )

    def check_file_path_access(self, file_path: str) -> None:
        """Check that filepath given is readable."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.info(
                "Could not read camera %s image from file: %s", self._name, file_path
            )

    async def update_file_path(self) -> None:
        """Update the file_path."""
        _LOGGER.debug("Camera Update: %s", self._type)
        _LOGGER.debug("Custom No Mail: %s", self._no_mail)

        if not self.coordinator.last_update_success:
            _LOGGER.debug("Update to update camera image. Unavailable.")
            return

        if self.coordinator.data is None:
            _LOGGER.debug("Unable to update camera image, no data.")
            return

        # Map camera type to: (subdir, default_img, image_attr, log_name)
        # Note: USPS and Generic are handled separately due to unique logic
        cam_config = {
            "amazon_camera": (
                "amazon/",
                "no_deliveries_amazon.jpg",
                ATTR_AMAZON_IMAGE,
                "Amazon",
            ),
            "ups_camera": ("ups/", "no_deliveries_ups.jpg", ATTR_UPS_IMAGE, "UPS"),
            "walmart_camera": (
                "walmart/",
                "no_deliveries_walmart.jpg",
                ATTR_WALMART_IMAGE,
                "Walmart",
            ),
        }

        if self._type == "usps_camera":
            # USPS Logic: Data > Custom No Mail > Default
            self._file_path = f"{os.path.dirname(__file__)}/mail_none.gif"
            if {ATTR_IMAGE_NAME, ATTR_IMAGE_PATH}.issubset(
                self.coordinator.data.keys()
            ):
                image = self.coordinator.data[ATTR_IMAGE_NAME]
                path = self.coordinator.data[ATTR_IMAGE_PATH]
                self._file_path = f"{self.hass.config.path()}/{path}{image}"
            elif self._no_mail:
                self._file_path = self._no_mail

        elif self._type in cam_config:
            # Amazon/UPS/Walmart Logic: Custom No Mail > Data > Default
            subdir, default_img, img_attr, log_name = cam_config[self._type]

            # 1. Default
            self._file_path = f"{os.path.dirname(__file__)}/{default_img}"

            # 2. Check Custom Image (Highest Priority for these cameras)
            if self._no_mail:
                self._file_path = self._no_mail
                _LOGGER.debug(
                    "%s camera - using custom no mail: %s", log_name, self._file_path
                )
            # 3. Check Data
            elif {img_attr, ATTR_IMAGE_PATH}.issubset(self.coordinator.data.keys()):
                image = self.coordinator.data[img_attr]
                path = f"{self.coordinator.data[ATTR_IMAGE_PATH]}{subdir}"
                self._file_path = f"{self.hass.config.path()}/{path}{image}"
                _LOGGER.debug(
                    "%s camera - using coordinator data: %s", log_name, self._file_path
                )

        elif self._type == "generic_camera":
            # Update camera image for generic package deliveries
            self._file_path = f"{os.path.dirname(__file__)}/no_deliveries_generic.jpg"

            # Check if custom image is configured for generic camera
            if self._no_mail:
                # Use custom image (takes priority over everything)
                self._file_path = self._no_mail
                _LOGGER.debug(
                    "Generic camera - using custom no mail: %s", self._file_path
                )
            else:
                # Collect all delivery images from different cameras to create an animated GIF
                delivery_images = []

                # Get enabled resources from config
                enabled_resources = self.config.data.get("resources", [])

                # Loop through all cameras in CAMERA_DATA, skipping generic and USPS
                for camera_type in CAMERA_DATA:
                    # Skip generic camera (we're the generic camera) and USPS camera
                    if camera_type in ("generic_camera", "usps_camera"):
                        continue

                    # Extract the base name from camera_type (e.g., "amazon_camera" -> "amazon")
                    base_name = camera_type.replace("_camera", "")

                    # Check if this camera's sensor is enabled in the configuration
                    sensor_name = self._get_sensor_name_for_camera(camera_type)
                    if sensor_name and sensor_name not in enabled_resources:
                        _LOGGER.debug(
                            "Generic camera - skipping %s (sensor %s not enabled)",
                            base_name,
                            sensor_name,
                        )
                        continue

                    # Set image attributes (UPS, Amazon, Walmart all use the same pattern)
                    image_attr_name = f"ATTR_{base_name.upper()}_IMAGE"

                    image_attr = getattr(const, image_attr_name, None)
                    path_suffix = f"{base_name}/"  # All cameras have subdirectory
                    no_mail_check = "no_deliveries"  # All cameras default no mail

                    if image_attr is not None:
                        # Check if this camera's image data is available
                        required_keys = set([image_attr, ATTR_IMAGE_PATH])
                        if required_keys.issubset(self.coordinator.data.keys()):
                            image = self.coordinator.data[image_attr]
                            path = (
                                f"{self.coordinator.data[ATTR_IMAGE_PATH]}{path_suffix}"
                            )
                            delivery_file_path = (
                                f"{self.hass.config.path()}/{path}{image}"
                            )

                            # Check if not a "no mail" image (default or custom)
                            # and file exists
                            is_no_mail = image.startswith(
                                no_mail_check
                            ) or self._is_custom_no_mail_image(  # Default no mail images
                                base_name, delivery_file_path
                            )  # Custom no mail images

                            # Check if there are actual current deliveries for this carrier
                            delivery_count_key = f"{base_name}_delivered"
                            has_current_deliveries = (
                                delivery_count_key in self.coordinator.data
                                and self.coordinator.data[delivery_count_key] > 0
                            )

                            if (
                                not is_no_mail
                                and os.path.exists(delivery_file_path)
                                and has_current_deliveries
                            ):
                                delivery_images.append(delivery_file_path)
                            elif is_no_mail:
                                _LOGGER.debug(
                                    "Generic camera - filtered out %s no-mail image: %s",
                                    base_name,
                                    image,
                                )
                            elif not has_current_deliveries:
                                _LOGGER.debug(
                                    "Generic camera - filtered out %s "
                                    "(no current deliveries, count=%s): %s",
                                    base_name,
                                    self.coordinator.data.get(delivery_count_key, 0),
                                    image,
                                )

                # Create animated GIF if we have multiple delivery images
                if len(delivery_images) > 0:
                    gif_path = f"{os.path.dirname(__file__)}/generic_deliveries.gif"

                    # Generate animated GIF using helper function
                    gif_created = await generate_delivery_gif(delivery_images, gif_path)

                    if gif_created:
                        self._file_path = gif_path
                        _LOGGER.debug(
                            "Generic camera - created animated GIF with %d delivery images",
                            len(delivery_images),
                        )
                    else:
                        _LOGGER.warning(
                            "Failed to create animated GIF, using first delivery image"
                        )
                        self._file_path = delivery_images[0]
                else:
                    # No deliveries found, use default generic no mail image
                    _LOGGER.debug(
                        "Generic camera - no deliveries found, using default: %s",
                        self._file_path,
                    )

        self.check_file_path_access(self._file_path)
        self.schedule_update_ha_state()

    def _is_custom_no_mail_image(self, base_name: str, file_path: str) -> bool:
        """Check if the given file path is a custom 'no mail' image for the specified camera.

        Args:
            base_name: The base name of the camera (e.g., 'amazon', 'ups', 'walmart', 'usps')
            file_path: The full file path to check

        Returns:
            True if this is a custom 'no mail' image, False otherwise
        """
        # Handle USPS camera differently (uses CONF_CUSTOM_IMG instead of CONF_USPS_CUSTOM_IMG)
        if base_name == "usps":
            custom_img_key = "CONF_CUSTOM_IMG"
            custom_img_file_key = "CONF_CUSTOM_IMG_FILE"
        else:
            # Handle other cameras (Amazon, UPS, Walmart)
            custom_img_key = f"CONF_{base_name.upper()}_CUSTOM_IMG"
            custom_img_file_key = f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE"

        custom_img_conf = getattr(const, custom_img_key, None)
        custom_img_file_conf = getattr(const, custom_img_file_key, None)

        if (
            custom_img_conf
            and custom_img_file_conf
            and self.config.data.get(custom_img_conf)
        ):
            custom_file_path = self.config.data.get(custom_img_file_conf)
            if custom_file_path and os.path.exists(custom_file_path):
                # Check if the file path matches the custom "no mail" image
                return os.path.abspath(file_path) == os.path.abspath(custom_file_path)

        return False

    def _get_sensor_name_for_camera(self, camera_type: str) -> str:
        """Get the sensor name that corresponds to a camera type.

        Args:
            camera_type: The camera type (e.g., 'amazon_camera', 'ups_camera', etc.)

        Returns:
            The corresponding sensor name, or None if no mapping exists
        """
        # Extract base name from camera type (e.g., "amazon_camera" -> "amazon")
        base_name = camera_type.split("_")[0]

        # Special case for USPS (uses usps_mail instead of usps_delivered)
        if base_name == "usps":
            return "usps_mail"

        # For other cameras, use the pattern: {base_name}_delivered
        return f"{base_name}_delivered"

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    @property
    def device_info(self) -> dict:
        """Return device information about the mailbox."""
        return {
            "connections": {(DOMAIN, self._unique_id)},
            "name": self._host,
            "manufacturer": "IMAP E-Mail",
            "sw_version": VERSION,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._host}_{self._name}_{self._unique_id}"

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        return {"file_path": self._file_path}

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        await self.update_file_path()
