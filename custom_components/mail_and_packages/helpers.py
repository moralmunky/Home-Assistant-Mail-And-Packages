"""Helper functions for Mail and Packages."""

from __future__ import annotations

import datetime
import logging
import os
from pathlib import Path
from shutil import copyfile
from typing import Any

from aioimaplib import IMAP4_SSL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_HUB_SUBJECT,
    AMAZON_OTP_SUBJECT,
    ATTR_COUNT,
    ATTR_TRACKING,
    CONF_PATH,
    SENSOR_TYPES,
)
from .shippers import SHIPPER_REGISTRY
from .shippers.usps import USPSShipper
from .utils.image import (
    default_image_path,
)

_LOGGER = logging.getLogger(__name__)

# Legacy constants for tests

amazon_exception = AMAZON_EXCEPTION_SUBJECT
amazon_hub = AMAZON_HUB_SUBJECT
amazon_otp = AMAZON_OTP_SUBJECT
amazon_search_legacy = AMAZON_DELIVERED_SUBJECT
image_file_name = "mail_today.gif"


async def get_count(
    account: IMAP4_SSL,
    sensor_type: str,
    body_count: bool,
    image_path: str,
    hass: HomeAssistant,
) -> dict[str, Any]:
    """Legacy get_count wrapper for tests."""
    shipper_class = SHIPPER_REGISTRY.get(sensor_type)
    if not shipper_class:
        _LOGGER.error("No shipper found for %s", sensor_type)
        return {ATTR_COUNT: 0, ATTR_TRACKING: []}

    shipper = shipper_class(hass, {CONF_PATH: image_path})
    today = datetime.datetime.now().strftime("%d-%b-%Y")
    return await shipper.process(account, today, sensor_type)


async def get_mails(
    account: IMAP4_SSL,
    address_list: list[str],
    hass: HomeAssistant,
    config: dict[str, Any],
) -> int:
    """Legacy get_mails wrapper for tests."""
    shipper = USPSShipper(hass, config)
    today = datetime.datetime.now().strftime("%d-%b-%Y")
    result = await shipper.process(account, today, "usps_mail")
    return result.get(ATTR_COUNT, 0)


async def fetch(
    hass: HomeAssistant,
    config: dict[str, Any],
    account: IMAP4_SSL,
    sensor: str,
) -> int:
    """Legacy fetch wrapper for tests."""
    shipper_class = SHIPPER_REGISTRY.get(sensor)
    if not shipper_class:
        return 0

    shipper = shipper_class(hass, config)
    today = datetime.datetime.now().strftime("%d-%b-%Y")
    data = await shipper.process(account, today, sensor)
    return data.get(ATTR_COUNT, 0)


async def get_items(
    hass: HomeAssistant,
    config: dict[str, Any],
    account: IMAP4_SSL,
    sensor: str,
) -> dict[str, Any]:
    """Legacy get_items wrapper for tests."""
    shipper_class = SHIPPER_REGISTRY.get(sensor)
    if not shipper_class:
        return {ATTR_COUNT: 0, ATTR_TRACKING: []}

    shipper = shipper_class(hass, config)
    today = datetime.datetime.now().strftime("%d-%b-%Y")
    return await shipper.process(account, today, sensor)


def get_resources(hass: HomeAssistant | None = None) -> list:
    """Return resources from const."""
    return list(SENSOR_TYPES.keys())


def copy_images(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Copy processed images to www directory."""
    image_path = Path(hass.config.path()) / default_image_path(hass, config)
    www_path = Path(hass.config.path()) / "www" / "mail_and_packages"

    if not www_path.is_dir():
        www_path.mkdir(parents=True, exist_ok=True)

    for root, _, files in os.walk(image_path):
        for file in files:
            if file.endswith((".gif", ".jpg", ".png")):
                src = Path(root) / file
                dest = www_path / file
                try:
                    copyfile(str(src), str(dest))
                except OSError as err:
                    _LOGGER.error("Error copying image: %s", err)
