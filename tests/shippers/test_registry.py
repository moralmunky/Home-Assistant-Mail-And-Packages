"""Tests for the shipper registry."""

from unittest.mock import MagicMock

from custom_components.mail_and_packages.const import AMAZON_PACKAGES
from custom_components.mail_and_packages.shippers import get_shipper_for_sensor
from custom_components.mail_and_packages.shippers.amazon import AmazonShipper
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from custom_components.mail_and_packages.shippers.usps import USPSShipper


def test_get_shipper_for_sensor():
    """Test get_shipper_for_sensor."""
    hass = MagicMock()
    config = {}

    # Test Amazon
    shipper = get_shipper_for_sensor(hass, config, "amazon_delivered")
    assert isinstance(shipper, AmazonShipper)

    shipper = get_shipper_for_sensor(hass, config, AMAZON_PACKAGES)
    assert isinstance(shipper, AmazonShipper)

    # Test USPS
    shipper = get_shipper_for_sensor(hass, config, "usps_mail")
    assert isinstance(shipper, USPSShipper)

    # Test Generic
    shipper = get_shipper_for_sensor(hass, config, "ups_delivered")
    assert isinstance(shipper, GenericShipper)

    shipper = get_shipper_for_sensor(hass, config, "fedex_delivering")
    assert isinstance(shipper, GenericShipper)

    shipper = get_shipper_for_sensor(hass, config, "usps_delivered")
    assert isinstance(shipper, GenericShipper)

    # Test unknown
    shipper = get_shipper_for_sensor(hass, config, "unknown_sensor")
    assert shipper is None
