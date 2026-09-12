"""Shippers for Mail and Packages."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from . import amazon, generic, usps
from .amazon import AmazonShipper
from .amazon import image as amazon_image
from .generic import GenericShipper
from .post_de import PostDEShipper
from .usps import USPSShipper
from .usps import image as usps_image

# Backward-compatible module aliases for external imports and unittest patch targets
sys.modules["custom_components.mail_and_packages.shippers.amazon_image"] = amazon_image
sys.modules["custom_components.mail_and_packages.shippers.usps_image"] = usps_image

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .base import Shipper

SHIPPER_REGISTRY = {
    "amazon": AmazonShipper,
    "generic": GenericShipper,
    "post_de": PostDEShipper,
    "usps": USPSShipper,
}


def get_shipper_for_sensor(
    hass: HomeAssistant,
    config: dict,
    sensor_type: str,
) -> Shipper | None:
    """Return the appropriate shipper for the given sensor type."""
    for name, shipper_class in SHIPPER_REGISTRY.items():
        if name == "generic":
            continue
        if shipper_class.handles_sensor(sensor_type):
            return shipper_class(hass, config)

    # Fallback to generic
    if GenericShipper.handles_sensor(sensor_type):
        return GenericShipper(hass, config)

    return None


__all__ = [
    "SHIPPER_REGISTRY",
    "AmazonShipper",
    "GenericShipper",
    "PostDEShipper",
    "USPSShipper",
    "amazon",
    "generic",
    "get_shipper_for_sensor",
    "usps",
]
