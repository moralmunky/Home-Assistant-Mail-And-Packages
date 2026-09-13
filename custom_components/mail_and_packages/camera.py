"""Camera that loads a picture from a local file."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import anyio
from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MailAndPackagesConfigEntry, const
from .camera_helpers import (
    async_setup_camera_entities,
    check_is_custom_no_mail_image,
    collect_generic_delivery_images,
    generate_generic_deliveries_gif,
    get_sensor_name_for_camera,
    is_camera_enabled,
    resolve_initial_camera_paths,
    scan_for_alternative_images,
)
from .const import (
    ATTR_IMAGE_PATH,
    ATTR_USPS_IMAGE,
    CAMERA_DATA,
    CONF_DURATION,
    DOMAIN,
    SENSOR_NAME,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Backward-compatibility aliases
_get_sensor_name_for_camera = get_sensor_name_for_camera
_is_camera_enabled = is_camera_enabled


async def async_setup_entry(
    hass,
    config: MailAndPackagesConfigEntry,
    async_add_entities,
):
    """Set up the Camera that works with local files."""
    await async_setup_camera_entities(hass, config, async_add_entities, MailCam)


class MailCam(CoordinatorEntity, Camera):
    """Representation of a local file camera."""

    @property
    def config_data(self) -> dict[str, Any]:
        """Return merged data and options."""
        return {**self.config.data, **self.config.options}

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
        self._host = self.config_data.get(CONF_HOST)
        self._unique_id = config.entry_id

        # Resolve initial paths and custom settings
        self._no_mail, self._file_path, self._default_image_path = (
            resolve_initial_camera_paths(
                self._type, self.config_data, Path(__file__).parent
            )
        )

        self._cached_image_path: str | None = None
        self._cached_image_bytes: bytes | None = None
        self._last_delivery_images: list[str] | None = None
        self._is_generic: bool = True

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return image response."""
        if (
            self._file_path == self._cached_image_path
            and self._cached_image_bytes is not None
        ):
            return self._cached_image_bytes

        _LOGGER.debug(
            "Camera %s reading image from: %s",
            self._name,
            self._file_path,
        )

        def _read_file(path: str) -> bytes:
            with Path(path).open("rb") as f:
                data = f.read()
            if not data:
                raise FileNotFoundError(f"empty image file: {path}")
            return data

        try:
            image_bytes = await self.hass.async_add_executor_job(
                _read_file, self._file_path
            )
        except FileNotFoundError:
            _LOGGER.debug(
                "Could not read camera %s image from file: %s; "
                "falling back to bundled placeholder %s",
                self._name,
                self._file_path,
                self._default_image_path,
            )
            if self._file_path != self._default_image_path:
                try:
                    image_bytes = await self.hass.async_add_executor_job(
                        _read_file, self._default_image_path
                    )
                except FileNotFoundError:
                    _LOGGER.warning(
                        "Camera %s placeholder image also missing: %s",
                        self._name,
                        self._default_image_path,
                    )
                    return None
                else:
                    self._cached_image_path = self._default_image_path
                    self._cached_image_bytes = image_bytes
                    return image_bytes
            return None
        else:
            self._cached_image_path = self._file_path
            self._cached_image_bytes = image_bytes
            return image_bytes

    def check_file_path_access(self, file_path: str) -> None:
        """Check that filepath given is readable."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.debug(
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

        # Invalidate the cache so the next frontend request re-reads the image from disk.
        self._cached_image_path = None
        self._cached_image_bytes = None

        self.check_file_path_access(self._file_path)
        self.schedule_update_ha_state()

    def _update_usps_camera(self) -> None:
        """Update file path for USPS camera."""
        self._file_path = f"{Path(__file__).parent}/mail_none.gif"
        self._is_generic = True
        required_keys = {ATTR_USPS_IMAGE, ATTR_IMAGE_PATH}
        if required_keys.issubset(self.coordinator.data):
            image = self.coordinator.data[ATTR_USPS_IMAGE]
            path = self.coordinator.data[ATTR_IMAGE_PATH]
            self._file_path = self.hass.config.path(path, image)
            self._is_generic = not self.coordinator.data.get("usps_update", False)
            _LOGGER.debug(
                "usps_camera camera - file path set to: %s",
                self._file_path,
            )
        elif self._no_mail:
            self._file_path = self._no_mail

    async def _update_generic_camera(self) -> None:
        """Update file path for Generic camera."""
        if self._no_mail:
            self._file_path = self._no_mail
            self._is_generic = True
            _LOGGER.debug("Generic camera - using custom no mail: %s", self._file_path)
            return

        delivery_images = self._collect_generic_delivery_images()

        if (
            self._last_delivery_images is not None
            and delivery_images == self._last_delivery_images
            and await anyio.Path(self._file_path).exists()
        ):
            _LOGGER.debug(
                "Generic camera - delivery images unchanged, skipping GIF regeneration"
            )
            return

        self._last_delivery_images = delivery_images

        if not delivery_images:
            self._file_path = f"{Path(__file__).parent}/no_deliveries_generic.jpg"
            self._is_generic = True
            _LOGGER.debug(
                "Generic camera - no deliveries found, using default: %s",
                self._file_path,
            )
            return

        image_path = self.coordinator.data.get(ATTR_IMAGE_PATH, "")
        duration = self.config_data.get(CONF_DURATION, 5)

        self._file_path, self._is_generic = await generate_generic_deliveries_gif(
            self.hass,
            delivery_images,
            image_path,
            duration,
        )

    def _collect_generic_delivery_images(self) -> list[str]:
        """Collect delivery images for the generic camera."""
        cam_data = sys.modules[__name__].CAMERA_DATA
        return collect_generic_delivery_images(
            cam_data,
            self.coordinator.data,
            self.config_data,
            self.hass.config.path,
            self._is_custom_no_mail_image,
        )

    async def _update_standard_camera(self) -> None:
        """Update file path for standard cameras (Amazon, UPS, etc)."""
        base_name = self._type.removesuffix("_camera")
        if base_name == "post_de":
            self._file_path = f"{Path(__file__).parent}/mail_none.gif"
        else:
            self._file_path = f"{Path(__file__).parent}/no_deliveries_{base_name}.jpg"
        self._is_generic = True

        if self._no_mail:
            self._file_path = self._no_mail
            _LOGGER.debug(
                "%s camera - using custom no mail: %s",
                self._type,
                self._file_path,
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
        coordinator_file_path = self.hass.config.path(path, image)

        _LOGGER.debug(
            "=== %s CAMERA UPDATE === coordinator %s = '%s'",
            self._type,
            image_attr,
            image,
        )

        all_image_keys = {
            k: self.coordinator.data.get(k, "NOT SET")
            for k in self.coordinator.data
            if "image" in k.lower()
        }
        _LOGGER.debug(
            "%s camera - All image keys in coordinator: %s",
            self._type,
            all_image_keys,
        )

        if await anyio.Path(coordinator_file_path).exists() and os.access(
            coordinator_file_path,
            os.R_OK,
        ):
            self._file_path = coordinator_file_path
            _LOGGER.debug(
                "%s camera - found coordinator file: %s",
                self._type,
                self._file_path,
            )
        else:
            await self._find_alternative_image(coordinator_file_path, image)

        self._is_generic = not self.coordinator.data.get(f"{base_name}_update", False)

    async def _find_alternative_image(
        self,
        coordinator_file_path: str,
        expected_image: str,
    ) -> None:
        """Attempt to find an alternative image in the directory."""
        if found := await self.hass.async_add_executor_job(
            scan_for_alternative_images, coordinator_file_path, self._type
        ):
            self._file_path = found

    def _is_custom_no_mail_image(self, base_name: str, file_path: str) -> bool:
        """Check if the given file path is a custom 'no mail' image for the specified camera."""
        return check_is_custom_no_mail_image(base_name, file_path, self.config_data)

    def _get_sensor_name_for_camera(self, camera_type: str) -> str | None:
        """Get the sensor name that corresponds to a camera type."""
        return _get_sensor_name_for_camera(camera_type)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass."""
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            await self.update_file_path()

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
        return f"camera_{self._host}_{self._type}_{self._unique_id}"

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the camera state attributes."""
        return {
            "file_path": self._file_path,
            "is_generic": self._is_generic,
        }

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "%s camera - coordinator update received, updating file path",
            self._type,
        )
        self.hass.async_create_task(self._async_handle_coordinator_update())

    async def _async_handle_coordinator_update(self) -> None:
        """Update file path then write state so the frontend gets the correct image URL."""
        await self.update_file_path()
        self.async_write_ha_state()
