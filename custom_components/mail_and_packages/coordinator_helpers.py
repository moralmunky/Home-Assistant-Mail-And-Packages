"""Helper functions for Mail and Packages data update coordinator."""

from __future__ import annotations

import datetime
import logging
from http import HTTPStatus
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

import anyio
from aiohttp import ClientResponseError
from aioimaplib import IMAP4_SSL, AioImapException
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    UpdateFailed,
)

from . import const
from .shippers import get_shipper_for_sensor
from .utils.cache import EmailCache
from .utils.image import default_image_path, image_file_name

if TYPE_CHECKING:
    from .coordinator import MailDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_oauth_access_token(
    hass: HomeAssistant,
    config_entry: ConfigEntry | None,
    auth_type: str,
    flow_mod=config_entry_oauth2_flow,
) -> str:
    """Return a valid OAuth2 access token, refreshing it when required.

    Raises ConfigEntryAuthFailed when the grant itself is gone, so Home
    Assistant starts a reauth flow instead of retrying forever.
    """
    try:
        hass.data.setdefault(const.DOMAIN, {})
        hass.data[const.DOMAIN]["oauth_provider"] = auth_type

        implementation = await flow_mod.async_get_config_entry_implementation(
            hass,
            config_entry,
        )
        session = flow_mod.OAuth2Session(
            hass,
            config_entry,
            implementation,
        )
        await session.async_ensure_token_valid()
    except ClientResponseError as err:
        # The token endpoint rejecting the grant (typically "invalid_grant")
        # means the refresh token has been revoked or has expired. Retrying
        # can never recover from that, so surface it as an auth failure and
        # let Home Assistant start a reauth flow.
        if err.status in (HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED):
            _LOGGER.error(
                "OAuth token refresh was rejected (HTTP %s): %s. "
                "Reauthentication is required",
                err.status,
                err.message,
            )
            raise ConfigEntryAuthFailed(
                "OAuth token refresh failed, reauthentication required"
            ) from err
        _LOGGER.error("Error refreshing OAuth token: %s", err)
        raise UpdateFailed("OAuth token refresh failed") from err
    except Exception as err:
        _LOGGER.error("Error refreshing OAuth token: %s", err)
        raise UpdateFailed("OAuth token refresh failed") from err

    return session.token["access_token"]


def initialize_data(config: dict) -> dict:
    """Initialize core data structure with default values."""
    data = {
        "mail_updated": datetime.datetime.now(datetime.UTC).isoformat(),
        "amazon_delivered_by_others": 0,
    }
    resources = config.get(CONF_RESOURCES, [])
    for sensor in resources:
        if sensor not in data:
            data[sensor] = 0
    return data


async def setup_image_config(hass: HomeAssistant, config: dict) -> dict:
    """Configure image paths and filenames for all shippers."""
    image_path = default_image_path(hass, config)
    config["image_path"] = image_path

    shipper_images = {
        "amazon_image": (True, False, False, False),
        "ups_image": (False, True, False, False),
        "walmart_image": (False, False, True, False),
        "fedex_image": (False, False, False, True),
        "usps_image": (False, False, False, False),
        "post_de_image": (False, False, False, False),
        "home_depot_image": (False, False, False, False),
    }

    for key, params in shipper_images.items():
        config[key] = await hass.async_add_executor_job(
            image_file_name, hass, config, *params
        )
    return config


async def update_shippers(
    hass: HomeAssistant,
    account: IMAP4_SSL,
    config: dict,
    today: str,
    since_date: str,
    cache: EmailCache,
    shipper_fn=get_shipper_for_sensor,
) -> dict:
    """Group and process sensors by shipper."""
    data = {}
    resources = config.get(CONF_RESOURCES, [])
    sensors_by_shipper = {}

    for sensor in resources:
        shipper = shipper_fn(hass, config, sensor)
        if shipper:
            sensors_by_shipper.setdefault(shipper.name, []).append((shipper, sensor))

    for shipper_name, shipper_group in sensors_by_shipper.items():
        shipper_instance = shipper_group[0][0]
        sensors = [s[1] for s in shipper_group]

        shipper_start = monotonic()
        success = False
        try:
            results = await shipper_instance.process_batch(
                account, today, sensors, cache, since_date=since_date
            )
            if isinstance(results, dict):
                if "_tracking_details" in results:
                    data.setdefault("_tracking_details", {}).update(
                        results.pop("_tracking_details")
                    )
                data.update(results)
            success = True
        except (
            AioImapException,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            AttributeError,
            IndexError,
        ) as err:
            _LOGGER.error("Error processing shipper %s: %s", shipper_name, err)
        finally:
            _LOGGER.debug(
                "Shipper %s %s in %.1fs",
                shipper_name,
                "processed" if success else "failed",
                monotonic() - shipper_start,
            )

    return data


def sum_delivered_counts(data: dict) -> int:
    """Sum delivered packages from all shippers."""
    delivered = 0
    exclude_keys = (
        "zpackages_delivered",
        "amazon_delivered_by_others",
        "usps_mail_delivered",
    )

    for key, value in data.items():
        if (
            isinstance(value, int)
            and value > 0
            and key.endswith("_delivered")
            and key not in exclude_keys
        ):
            delivered += value
    return delivered


def sum_delivering_counts(data: dict) -> int:
    """Sum out-for-delivery packages from all shippers."""
    delivering = 0
    for key, value in data.items():
        if (
            isinstance(value, int)
            and value > 0
            and key.endswith("_delivering")
            and key != "zpackages_delivering"
        ):
            delivering += value
    return delivering


def sum_transit_counts(data: dict) -> int:
    """Sum transit and exception packages from all shippers."""
    transit = 0
    shippers_counted = set()

    # Amazon is special as it uses amazon_packages for total arriving
    if data.get("amazon_packages", 0) > 0:
        transit += data["amazon_packages"]
        shippers_counted.add("amazon")

    for key, value in data.items():
        if not isinstance(value, int) or value <= 0:
            continue

        # Add exceptions for all shippers
        if key.endswith("_exception") and key != "zpackages_exception":
            transit += value
            continue

        # Match shipper prefix
        shipper = next((s for s in const.SHIPPERS if key.startswith(s)), None)
        if not shipper or shipper in shippers_counted:
            continue

        if key.endswith("_delivering"):
            transit += value
            shippers_counted.add(shipper)

    return transit


def aggregate_package_counts(data: dict) -> None:
    """Aggregate global transit and delivered counts from all shippers."""
    if "zpackages_transit" in data:
        data["zpackages_transit"] = sum_transit_counts(data)
    if "zpackages_delivering" in data:
        data["zpackages_delivering"] = sum_delivering_counts(data)
    if "zpackages_delivered" in data:
        data["zpackages_delivered"] = sum_delivered_counts(data)


async def check_camera_update(
    coordinator: MailDataUpdateCoordinator,
    base_name: str,
    data: dict | None = None,
    def_img_path=default_image_path,
    anyio_mod=anyio,
) -> None:
    """Check image hash changes for a specific delivery camera."""
    if data is None:
        data = getattr(coordinator, "_data", {})

    image_attr_name = f"ATTR_{base_name.upper()}_IMAGE"
    image_attr = getattr(const, image_attr_name, None)
    if not image_attr:
        return

    image = data.get(image_attr)
    _LOGGER.debug("%s image from data: %s", base_name.title(), image)
    if not image:
        return

    image_path = def_img_path(coordinator.hass, coordinator.config).rstrip("/") + "/"
    path = f"{image_path}{base_name}/"
    delivery_image = coordinator.hass.config.path(f"{path}{image}")
    _LOGGER.debug("Full %s image path: %s", base_name.title(), delivery_image)

    custom_img_key = getattr(const, f"CONF_{base_name.upper()}_CUSTOM_IMG", None)
    custom_img_file_key = getattr(
        const, f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE", None
    )
    if custom_img_key and coordinator.config.get(custom_img_key):
        none_image = coordinator.config.get(custom_img_file_key)
    elif base_name == "post_de":
        none_image = f"{Path(__file__).parent}/mail_none.gif"
    else:
        none_image = f"{Path(__file__).parent}/no_deliveries_{base_name}.jpg"

    if await anyio_mod.Path(delivery_image).exists():
        image_hash = await coordinator.async_get_file_hash_if_changed(delivery_image)
        none_hash = await coordinator.async_get_file_hash_if_changed(none_image)
        _LOGGER.debug("%s Image hash: %s", base_name.title(), image_hash)
        _LOGGER.debug("%s None hash: %s", base_name.title(), none_hash)
        data[f"{base_name}_update"] = image_hash != none_hash


async def binary_sensor_update(
    coordinator: MailDataUpdateCoordinator,
    data: dict | None = None,
    def_img_path=default_image_path,
    anyio_mod=anyio,
) -> None:
    """Update binary sensor states."""
    if data is None:
        data = getattr(coordinator, "_data", {})

    _LOGGER.debug("Data: %s", data)
    image = data.get(const.ATTR_USPS_IMAGE)
    if image:
        path = def_img_path(coordinator.hass, coordinator.config)
        usps_image = f"{path}/{image}"
        usps_none = f"{Path(__file__).parent}/mail_none.gif"
        if await anyio_mod.Path(usps_image).exists():
            image_hash = await coordinator.async_get_file_hash_if_changed(usps_image)
            none_hash = await coordinator.async_get_file_hash_if_changed(usps_none)
            _LOGGER.debug("USPS Image hash: %s", image_hash)
            _LOGGER.debug("USPS None hash: %s", none_hash)
            data["usps_update"] = image_hash != none_hash

    delivery_cameras = [
        camera_type.replace("_camera", "")
        for camera_type in const.CAMERA_DATA
        if camera_type not in ("usps_camera", "generic_camera")
    ]

    for base_name in delivery_cameras:
        check_update = getattr(
            coordinator,
            "async_check_camera_update",
            check_camera_update,
        )
        await check_update(base_name, data)
