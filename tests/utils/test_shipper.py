"""Tests for shipper utility functions."""

from custom_components.mail_and_packages.utils.shipper import filter_localized_strings


def test_filter_localized_strings_amazon():
    """Test filter_localized_strings for Amazon."""
    strings = [
        "Delivered: ",  # Base
        "Geliefert:",  # German
        "Livré",  # French
    ]

    # .com (English only)
    result = filter_localized_strings(strings, "amazon.com", "amazon")
    assert result == ["Delivered: "]

    # .de (German only)
    result = filter_localized_strings(strings, "amazon.de", "amazon")
    assert result == ["Geliefert:"]

    # .ca (English and French)
    result = filter_localized_strings(strings, "amazon.ca", "amazon")
    assert "Delivered: " in result
    assert "Livré" in result


def test_filter_localized_strings_dhl():
    """Test filter_localized_strings for DHL."""
    strings = [
        "DHL Shipment Notification",  # Base
        "Powiadomienie o przesyłce",  # Polish
        "Paket kommt heute",  # German
    ]

    # .pl (Polish only)
    result = filter_localized_strings(strings, "amazon.pl", "dhl")
    assert result == ["Powiadomienie o przesyłce"]

    # .de (German only)
    result = filter_localized_strings(strings, "amazon.de", "dhl")
    assert result == ["Paket kommt heute"]

    # .co.uk (English only)
    result = filter_localized_strings(strings, "amazon.co.uk", "dhl")
    assert result == ["DHL Shipment Notification"]


def test_filter_localized_strings_ups():
    """Test filter_localized_strings for UPS."""
    strings = [
        "Your UPS Package was delivered",  # Base
        "Votre colis UPS a été livré",  # French
    ]

    # .fr (French only)
    result = filter_localized_strings(strings, "amazon.fr", "ups")
    assert result == ["Votre colis UPS a été livré"]

    # .ca (English and French)
    result = filter_localized_strings(strings, "amazon.ca", "ups")
    assert "Your UPS Package was delivered" in result
    assert "Votre colis UPS a été livré" in result


def test_filter_localized_strings_fedex():
    """Test filter_localized_strings for FedEx."""
    strings = [
        "Your package has been delivered",  # Base
        "Ihre Sendung wird voraussichtlich heute zugestellt",  # German
    ]

    # .de (German only)
    result = filter_localized_strings(strings, "amazon.de", "fedex")
    assert result == ["Ihre Sendung wird voraussichtlich heute zugestellt"]

    # .com (English only)
    result = filter_localized_strings(strings, "amazon.com", "fedex")
    assert result == ["Your package has been delivered"]


def test_filter_localized_strings_unmapped_shipper():
    """Test filter_localized_strings for a shipper not in mapping."""
    strings = ["Order Delivered", "Order Shipped"]

    # Should return all strings as "base"
    result = filter_localized_strings(strings, "amazon.de", "walmart")
    assert result == strings
