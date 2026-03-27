"""Shippers for Mail and Packages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .amazon import AmazonShipper
from .generic import GenericShipper
from .usps import USPSShipper

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .base import Shipper

SHIPPER_REGISTRY = {
    "amazon": AmazonShipper,
    "generic": GenericShipper,
    "usps": USPSShipper,
}


def get_shipper_for_sensor(
    hass: HomeAssistant,
    config: dict,
    sensor_type: str,
) -> Shipper | None:
    """Return the appropriate shipper for the given sensor type."""
    # Check specialized shippers first
    for name, shipper_class in SHIPPER_REGISTRY.items():
        if name == "generic":
            continue
        if shipper_class.handles_sensor(sensor_type):
            return shipper_class(hass, config)

    # Fallback to generic
    if GenericShipper.handles_sensor(sensor_type):
        return GenericShipper(hass, config)

    return None
