"""Shippers for Mail and Packages."""

from .amazon import AmazonShipper
from .generic import GenericShipper
from .usps import USPSShipper

SHIPPER_REGISTRY = {
    "amazon": AmazonShipper,
    "generic": GenericShipper,
    "usps": USPSShipper,
}
