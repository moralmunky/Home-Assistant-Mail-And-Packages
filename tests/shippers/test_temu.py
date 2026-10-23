"""Temu notification patterns from six redacted real-message examples.

Subjects and carrier labels reflect observed messages. All order identifiers,
tracking identifiers and recipient details here are synthetic, not copied from mail.
"""

import re
from unittest.mock import MagicMock

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    MARKETPLACE_CARRIER_TRACKING,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
)
from custom_components.mail_and_packages.coordinator.tracking import (
    dedupe_marketplace_duplicates,
)
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from tests.conftest import _generate_fetch_side_effect, _generate_search_side_effect


@pytest.mark.parametrize(
    ("subject", "body", "expected_sensor", "tracking"),
    [
        (
            "Order shipped and GOFO tracking number is ready (Order ID: #PO-000-00000000000000000)",
            "The GOFO tracking number is GFUS000000000001",
            "temu_delivering",
            "GFUS000000000001",
        ),
        (
            "Your Temu order has been transferred to GOFO for delivery (#PO-000-00000000000000000)",
            "View details on GOFO GFUS000000000001",
            "temu_delivering",
            "GFUS000000000001",
        ),
        (
            "Your Temu package is arriving soon",
            "Your Package Is Out for Delivery. Waybill no. GFUS000000000001",
            "temu_delivering",
            "GFUS000000000001",
        ),
        (
            "Your Temu order delivered notification (#PO-000-00000000000000000)",
            "Your order was delivered on October 11. View details on GOFO GFUS000000000001",
            "temu_delivered",
            "GFUS000000000001",
        ),
        (
            "Order shipped and FedEx tracking number is ready (Order ID: #PO-000-00000000000000000)",
            "The FedEx tracking number is 000000000002",
            "temu_delivering",
            "000000000002",
        ),
        (
            "Your Temu order delivered notification (#PO-000-00000000000000000)",
            "Your order was delivered on October 20. View details on FedEx 000000000002",
            "temu_delivered",
            "000000000002",
        ),
    ],
)
def test_temu_redacted_message_patterns(subject, body, expected_sensor, tracking):
    """Each observed notification maps to one status and its carrier number."""
    assert "temu" in SHIPPERS
    assert all(
        sensor in SENSOR_TYPES
        for sensor in ("temu_delivering", "temu_delivered", "temu_packages")
    )
    statuses = ("temu_delivering", "temu_delivered")
    matched = [
        sensor
        for sensor in statuses
        if any(
            phrase.lower() in subject.lower()
            for phrase in SENSOR_DATA[sensor]["subject"]
        )
    ]
    assert matched == [expected_sensor]
    assert SENSOR_DATA[expected_sensor]["email"] == ["orders@transaction.temu.com"]
    id_match = re.search(SENSOR_DATA["temu_tracking"]["pattern"][0], body)
    carrier_match = re.search(MARKETPLACE_CARRIER_TRACKING["temu"], body, re.IGNORECASE)
    assert id_match is not None and id_match.group() == tracking
    assert carrier_match is not None and carrier_match.group(1) == tracking


@pytest.mark.parametrize(
    "subject",
    ["Your Temu order confirmed", "Your delayed delivery coupon code"],
)
def test_temu_unrelated_subjects_do_not_match(subject):
    """Purchase and promotional notices must not count as shipments."""
    for sensor in ("temu_delivering", "temu_delivered"):
        assert not any(
            phrase.lower() in subject.lower()
            for phrase in SENSOR_DATA[sensor]["subject"]
        )


@pytest.mark.parametrize(
    ("subject", "body", "sensor", "tracking"),
    [
        (
            "Your Temu package is arriving soon",
            "Waybill no. GFUS000000000001",
            "temu_delivering",
            "GFUS000000000001",
        ),
        (
            "Your Temu order delivered notification (#PO-000-00000000000000000)",
            "View details on FedEx 000000000002",
            "temu_delivered",
            "000000000002",
        ),
    ],
)
@pytest.mark.asyncio
async def test_temu_generic_shipper_parses_redacted_email(
    hass, mock_imap, subject, body, sensor, tracking
):
    """Exercise IMAP search, subject verification, and tracking extraction."""
    raw = (
        "From: Temu <orders@transaction.temu.com>\r\n"
        "To: recipient@example.invalid\r\n"
        f"Subject: {subject}\r\n"
        "Date: Fri, 23 Oct 2026 12:00:00 -0400\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/plain; charset=UTF-8\r\n\r\n"
        f"{body}\r\n"
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.search.side_effect = _generate_search_side_effect()
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(raw)
    result = await GenericShipper(hass, {}).process(mock_imap, "today", sensor)
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [tracking]


def test_temu_fedex_delivery_is_not_double_counted():
    """A carrier email with the same number removes the Temu duplicate."""
    tracking = "000000000002"
    data = {
        "temu_delivered": 1,
        "temu_packages": 1,
        "fedex_delivered": 1,
        "temu_carrier_tracking": {tracking: tracking},
    }
    details = {"temu_delivered": [tracking], "fedex_delivered": [tracking]}
    dedupe_marketplace_duplicates(data, details)
    assert data["temu_delivered"] == 0
    assert data["temu_packages"] == 0
    assert details["temu_delivered"] == []
    assert data["fedex_delivered"] == 1
