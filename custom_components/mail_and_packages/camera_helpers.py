"""Helper functions and service setup for the Mail and Packages camera component."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID, CONF_RESOURCES
from homeassistant.core import HomeAssistant, ServiceCall

from . import const
from .const import (
    ATTR_IMAGE_PATH,
    CAMERA_DATA,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    DOMAIN,
    GENERIC_DELIVERIES_GIF,
)
from .utils.image import cleanup_images, generate_delivery_gif, resize_images

if TYPE_CHECKING:
    from . import MailAndPackagesConfigEntry
    from .camera import MailCam

SERVICE_UPDATE_IMAGE = "update_image"
_LOGGER = logging.getLogger(__name__)


def get_sensor_name_for_camera(camera_type: str) -> str | None:
    """Get the sensor name that corresponds to a camera type."""
    base_name = camera_type.removesuffix("_camera")

    if base_name == "usps":
        return "usps_mail"
    if base_name == "post_de":
        return "post_de_mail"
    if base_name == "generic":
        return None

    return f"{base_name}_delivered"


def is_camera_enabled(camera_type: str, resources: Sequence[str]) -> bool:
    """Check if a camera entity should be enabled based on resources."""
    if camera_type == "generic_camera":
        return any(res.endswith("_delivered") for res in resources)
    sensor_name = get_sensor_name_for_camera(camera_type)
    return bool(sensor_name and sensor_name in resources)


def resolve_initial_camera_paths(
    camera_type: str,
    config_data: dict[str, Any],
    parent_dir: Path,
) -> tuple[str | None, str, str]:
    """Resolve initial paths for a camera: (no_mail, file_path, default_image_path)."""
    base_name = camera_type.removesuffix("_camera")

    # USPS and Post DE use mail_none.gif, others use no_deliveries_*.jpg
    if base_name in ("usps", "post_de"):
        if base_name == "usps":
            custom_img_key = CONF_CUSTOM_IMG
            custom_img_file_key = CONF_CUSTOM_IMG_FILE
        else:
            custom_img_key = CONF_POST_DE_CUSTOM_IMG
            custom_img_file_key = CONF_POST_DE_CUSTOM_IMG_FILE
        default_image = "mail_none.gif"
    else:
        # Derive config key names dynamically (e.g., "amazon" -> CONF_AMAZON_CUSTOM_IMG)
        custom_img_key = getattr(
            const,
            f"CONF_{base_name.upper()}_CUSTOM_IMG",
            None,
        )
        custom_img_file_key = getattr(
            const,
            f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE",
            None,
        )
        default_image = f"no_deliveries_{base_name}.jpg"

    no_mail = None
    if custom_img_key and config_data.get(custom_img_key):
        no_mail = config_data.get(custom_img_file_key)
        _LOGGER.debug(
            "%s camera - custom image enabled: %s",
            camera_type,
            no_mail,
        )

    if custom_img_key and config_data.get(custom_img_key):
        file_path = config_data.get(custom_img_file_key)
        _LOGGER.debug(
            "%s camera - initial file path set to: %s",
            camera_type,
            file_path,
        )
    else:
        file_path = f"{parent_dir}/{default_image}"

    default_image_path = f"{parent_dir}/{default_image}"
    return no_mail, file_path, default_image_path


def check_is_custom_no_mail_image(
    base_name: str,
    file_path: str,
    config_data: dict[str, Any],
) -> bool:
    """Check if the given file path is a custom 'no mail' image for the specified camera."""
    if base_name == "usps":
        custom_img_key = "CONF_CUSTOM_IMG"
        custom_img_file_key = "CONF_CUSTOM_IMG_FILE"
    else:
        custom_img_key = f"CONF_{base_name.upper()}_CUSTOM_IMG"
        custom_img_file_key = f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE"

    custom_img_conf = getattr(const, custom_img_key, None)
    custom_img_file_conf = getattr(const, custom_img_file_key, None)

    if custom_img_conf and custom_img_file_conf and config_data.get(custom_img_conf):
        custom_file_path = config_data.get(custom_img_file_conf)
        if custom_file_path and Path(custom_file_path).exists():
            return Path(file_path).resolve() == Path(custom_file_path).resolve()

    return False


def collect_generic_delivery_images(
    camera_data_map: dict[str, Any],
    coordinator_data: dict[str, Any],
    config_data: dict[str, Any],
    path_resolver: Any,
    custom_checker: Any,
) -> list[str]:
    """Collect delivery images for the generic camera."""
    delivery_images = []
    enabled_resources = config_data.get("resources", [])

    for camera_type in camera_data_map:
        if camera_type in ("generic_camera", "usps_camera", "post_de_camera"):
            continue

        base_name = camera_type.removesuffix("_camera")
        delivered_key = f"{base_name}_delivered"

        if delivered_key not in enabled_resources:
            _LOGGER.debug(
                "Generic camera - skipping %s (sensor %s not enabled)",
                base_name,
                delivered_key,
            )
            continue

        image_attr_name = f"ATTR_{base_name.upper()}_IMAGE"
        image_attr = getattr(const, image_attr_name, None)
        path_suffix = f"{base_name}/"
        no_mail_check = "no_deliveries"

        required_keys = {image_attr, ATTR_IMAGE_PATH}
        if not required_keys.issubset(coordinator_data):
            continue

        image = coordinator_data[image_attr]
        path = f"{coordinator_data[ATTR_IMAGE_PATH]}{path_suffix}"
        delivery_file_path = path_resolver(path, image)

        is_no_mail = image.startswith(
            no_mail_check,
        ) or custom_checker(base_name, delivery_file_path)

        delivery_count_key = f"{base_name}_delivered"
        has_current_deliveries = (
            delivery_count_key in coordinator_data
            and coordinator_data[delivery_count_key] > 0
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
                coordinator_data.get(delivery_count_key, 0),
                image,
            )

    return delivery_images


async def generate_generic_deliveries_gif(
    hass: HomeAssistant,
    delivery_images: list[str],
    image_storage_path: str,
    duration_sec: int,
) -> tuple[str, bool]:
    """Generate delivery GIF or fallback to first image. Returns (file_path, is_generic)."""
    full_storage_path = Path(hass.config.path(image_storage_path))
    gif_path = str(full_storage_path / GENERIC_DELIVERIES_GIF)

    # Generate delivery GIF using image utilities
    resized_images = await hass.async_add_executor_job(
        resize_images, delivery_images, 800, 600
    )

    duration = duration_sec * 1000
    gif_created = await hass.async_add_executor_job(
        generate_delivery_gif,
        resized_images,
        gif_path,
        duration,
    )

    if gif_created:
        result_file_path = gif_path
        _LOGGER.debug(
            "Generic camera - created animated GIF with %d delivery images at %s",
            len(delivery_images),
            gif_path,
        )
    else:
        _LOGGER.warning(
            "Failed to create animated GIF, using first delivery image",
        )
        result_file_path = delivery_images[0]

    for img in resized_images:
        if await anyio.Path(img).exists():
            await hass.async_add_executor_job(
                cleanup_images, str(Path(img).parent) + "/", Path(img).name
            )

    return result_file_path, False


def scan_for_alternative_images(
    coordinator_file_path: str, camera_type: str
) -> str | None:
    """Scan directory for the most recent delivery image if the coordinator file is missing."""
    # Support unit tests patching Path on camera module
    cam_mod = sys.modules.get("custom_components.mail_and_packages.camera")
    path_cls = getattr(cam_mod, "Path", Path) if cam_mod else Path

    path_dir = path_cls(coordinator_file_path).parent
    _LOGGER.debug(
        "%s camera - coordinator file not found: %s",
        camera_type,
        coordinator_file_path,
    )

    if not path_dir.exists():
        _LOGGER.debug(
            "%s camera - directory does not exist: %s",
            camera_type,
            path_dir,
        )
        return None

    try:
        found_images = []
        for file_path in path_dir.iterdir():
            if file_path.name.lower().endswith(
                (".jpg", ".jpeg", ".png", ".gif"),
            ):
                if file_path.exists() and os.access(file_path, os.R_OK):
                    if "no_deliveries" not in file_path.name:
                        found_images.append(
                            (str(file_path), file_path.stat().st_mtime),
                        )
    except OSError as err:
        _LOGGER.debug(
            "%s camera - error listing directory %s: %s",
            camera_type,
            path_dir,
            err,
        )
        return None

    if found_images:
        found_images.sort(key=lambda x: x[1], reverse=True)
        most_recent = found_images[0][0]
        _LOGGER.debug(
            "%s camera - found alternative image file (most recent): %s",
            camera_type,
            most_recent,
        )
        return most_recent

    return None


async def async_setup_camera_entities(
    hass: HomeAssistant,
    config: MailAndPackagesConfigEntry,
    async_add_entities: Any,
    camera_class: type[MailCam],
) -> None:
    """Set up the Camera entities that work with local files."""
    coordinator = config.runtime_data.coordinator
    resources = coordinator.config.get(CONF_RESOURCES, [])
    cameras = []

    for variable in CAMERA_DATA:
        if not is_camera_enabled(variable, resources):
            continue
        temp_cam = camera_class(hass, variable, config, coordinator)
        cameras.append(temp_cam)
        config.runtime_data.cameras.append(temp_cam)

    async def _update_image(service: ServiceCall) -> bool:
        """Refresh camera image."""
        _LOGGER.debug("Updating image: %s", service)
        registered_cameras = config.runtime_data.cameras
        entity_id = service.data.get(ATTR_ENTITY_ID)

        if entity_id is None:
            for cam in registered_cameras:
                await cam.update_file_path()
        else:
            for cam in registered_cameras:
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
            },
        ),
    )

    async_add_entities(cameras)
