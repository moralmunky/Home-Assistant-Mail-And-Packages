"""Camera that loads a picture from a local file."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import voluptuous as vol
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import ServiceCall
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
from .const import (
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    CAMERA,
    CAMERA_DATA,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    COORDINATOR,
    DOMAIN,
    SENSOR_NAME,
    VERSION,
)
from .helpers import generate_delivery_gif

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

        if ATTR_ENTITY_ID in service.data:
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

        # Derive config keys and default image from camera type name
        # Remove "_camera" suffix to get base name (e.g., "usps_camera" -> "usps")
        base_name = self._type.replace("_camera", "")

        # USPS uses special config keys (no prefix), others use prefixed keys
        if base_name == "usps":
            custom_img_key = CONF_CUSTOM_IMG
            custom_img_file_key = CONF_CUSTOM_IMG_FILE
            default_image = "mail_none.gif"
        else:
            # Derive config key names dynamically (e.g., "amazon" -> CONF_AMAZON_CUSTOM_IMG)
            custom_img_key = getattr(
                const, f"CONF_{base_name.upper()}_CUSTOM_IMG", None
            )
            custom_img_file_key = getattr(
                const, f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE", None
            )
            default_image = f"no_deliveries_{base_name}.jpg"

        # Set custom image paths
        self._no_mail = None
        if custom_img_key and config.data.get(custom_img_key):
            self._no_mail = config.data.get(custom_img_file_key)
            _LOGGER.debug(
                "%s camera - custom image enabled: %s", self._type, self._no_mail
            )

        # Set initial file path based on camera type and custom settings
        if custom_img_key and config.data.get(custom_img_key):
            self._file_path = config.data.get(custom_img_file_key)
            _LOGGER.debug(
                "%s camera - initial file path set to: %s",
                self._type,
                self._file_path,
            )
        else:
            self._file_path = f"{Path(__file__).parent}/{default_image}"

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

        if self._type == "usps_camera":
            self._update_usps_camera()
        elif self._type == "generic_camera":
            await self._update_generic_camera()
        else:
            await self._update_standard_camera()

        self.check_file_path_access(self._file_path)
        self.schedule_update_ha_state()

    def _update_usps_camera(self) -> None:
        """Update file path for USPS camera."""
        self._file_path = f"{Path(__file__).parent}/mail_none.gif"
        required_keys = {ATTR_IMAGE_NAME, ATTR_IMAGE_PATH}
        if required_keys.issubset(self.coordinator.data):
            image = self.coordinator.data[ATTR_IMAGE_NAME]
            path = self.coordinator.data[ATTR_IMAGE_PATH]
            self._file_path = f"{self.hass.config.path()}/{path}{image}"
        elif self._no_mail:
            self._file_path = self._no_mail

    async def _update_generic_camera(self) -> None:
        """Update file path for Generic camera."""
        self._file_path = f"{Path(__file__).parent}/no_deliveries_generic.jpg"

        # Check if custom image is configured for generic camera
        if self._no_mail:
            self._file_path = self._no_mail
            _LOGGER.debug("Generic camera - using custom no mail: %s", self._file_path)
            return

        # Collect all delivery images from different cameras
        delivery_images = self._collect_generic_delivery_images()

        # Create animated GIF if we have multiple delivery images
        if len(delivery_images) > 0:
            gif_path = f"{Path(__file__).parent}/generic_deliveries.gif"

            # Generate animated GIF using helper function
            # Run in executor to avoid blocking the event loop
            gif_created = await self.hass.async_add_executor_job(
                generate_delivery_gif, delivery_images, gif_path
            )

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

    def _collect_generic_delivery_images(self) -> list[str]:
        """Collect delivery images for the generic camera."""
        delivery_images = []
        enabled_resources = self.config.data.get("resources", [])

        for camera_type in CAMERA_DATA:
            # Skip generic and USPS cameras
            if camera_type in ("generic_camera", "usps_camera"):
                continue

            base_name = camera_type.replace("_camera", "")

            # Check if this camera's sensor is enabled
            sensor_name = self._get_sensor_name_for_camera(camera_type)
            if sensor_name and sensor_name not in enabled_resources:
                _LOGGER.debug(
                    "Generic camera - skipping %s (sensor %s not enabled)",
                    base_name,
                    sensor_name,
                )
                continue

            # Set image attributes
            image_attr_name = f"ATTR_{base_name.upper()}_IMAGE"
            image_attr = getattr(const, image_attr_name, None)
            path_suffix = f"{base_name}/"
            no_mail_check = "no_deliveries"

            if image_attr is None:
                continue

            required_keys = {image_attr, ATTR_IMAGE_PATH}
            if not required_keys.issubset(self.coordinator.data):
                continue

            image = self.coordinator.data[image_attr]
            path = f"{self.coordinator.data[ATTR_IMAGE_PATH]}{path_suffix}"
            delivery_file_path = f"{self.hass.config.path()}/{path}{image}"

            is_no_mail = image.startswith(
                no_mail_check
            ) or self._is_custom_no_mail_image(base_name, delivery_file_path)

            delivery_count_key = f"{base_name}_delivered"
            has_current_deliveries = (
                delivery_count_key in self.coordinator.data
                and self.coordinator.data[delivery_count_key] > 0
            )

            if (
                not is_no_mail
                and Path(delivery_file_path).exists()
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
                    "Generic camera - filtered out %s (no current deliveries, count=%s): %s",
                    base_name,
                    self.coordinator.data.get(delivery_count_key, 0),
                    image,
                )

        return delivery_images

    async def _update_standard_camera(self) -> None:
        """Update file path for standard cameras (Amazon, UPS, etc)."""
        base_name = self._type.replace("_camera", "")
        self._file_path = f"{Path(__file__).parent}/no_deliveries_{base_name}.jpg"

        if self._no_mail:
            self._file_path = self._no_mail
            _LOGGER.debug(
                "%s camera - using custom no mail: %s", self._type, self._file_path
            )
            return

        image_attr_name = f"ATTR_{base_name.upper()}_IMAGE"
        image_attr = getattr(const, image_attr_name, None)

        if not image_attr:
            return

        required_keys = {image_attr, ATTR_IMAGE_PATH}
        if not required_keys.issubset(self.coordinator.data):
            return

        image = self.coordinator.data[image_attr]
        image_path = self.coordinator.data[ATTR_IMAGE_PATH].rstrip("/") + "/"
        path = f"{image_path}{base_name}/"
        coordinator_file_path = f"{self.hass.config.path()}/{path}{image}"

        _LOGGER.info(
            "=== %s CAMERA UPDATE === coordinator %s = '%s'",
            self._type,
            image_attr,
            image,
        )

        # Log all image-related keys in coordinator for this camera
        all_image_keys = {
            k: self.coordinator.data.get(k, "NOT SET")
            for k in self.coordinator.data
            if "image" in k.lower()
        }
        _LOGGER.info(
            "%s camera - All image keys in coordinator: %s",
            self._type,
            all_image_keys,
        )

        if Path(coordinator_file_path).exists() and os.access(
            coordinator_file_path, os.R_OK
        ):
            self._file_path = coordinator_file_path
            _LOGGER.debug(
                "%s camera - found coordinator file: %s", self._type, self._file_path
            )
        else:
            await self._find_alternative_image(coordinator_file_path, image)

    async def _find_alternative_image(
        self, coordinator_file_path: str, expected_image: str
    ) -> None:
        """Attempt to find an alternative image in the directory."""
        path_dir = Path(coordinator_file_path).parent
        _LOGGER.debug(
            "%s camera - coordinator file not found: %s",
            self._type,
            coordinator_file_path,
        )

        # Define a helper to run blocking I/O in the executor
        def _scan_images():
            if not path_dir.exists():
                _LOGGER.debug(
                    "%s camera - directory does not exist: %s", self._type, path_dir
                )
                return None

            try:
                found_images = []
                for file_path in path_dir.iterdir():
                    if file_path.name.lower().endswith(
                        (".jpg", ".jpeg", ".png", ".gif")
                    ):
                        if file_path.exists() and os.access(file_path, os.R_OK):
                            if "no_deliveries" not in file_path.name:
                                found_images.append(
                                    (str(file_path), file_path.stat().st_mtime)
                                )
            except OSError as err:
                _LOGGER.debug(
                    "%s camera - error listing directory %s: %s",
                    self._type,
                    path_dir,
                    err,
                )
                return None
            else:
                return found_images

        # Execute the scan in a background thread
        image_files = await self.hass.async_add_executor_job(_scan_images)

        if image_files:
            image_files.sort(key=lambda x: x[1], reverse=True)
            self._file_path = image_files[0][0]
            _LOGGER.debug(
                "%s camera - found alternative image file (most recent): %s",
                self._type,
                self._file_path,
            )

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
            if custom_file_path and Path(custom_file_path).exists():
                # Check if the file path matches the custom "no mail" image
                return Path(file_path).resolve() == Path(custom_file_path).resolve()

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

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "%s camera - coordinator update received, updating file path",
            self._type,
        )
        super()._handle_coordinator_update()
        self.hass.async_create_task(self.update_file_path())

    async def async_update(self):
        """Update camera entity and refresh attributes."""
        await self.update_file_path()
