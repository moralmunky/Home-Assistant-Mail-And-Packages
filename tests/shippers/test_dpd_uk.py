"""Tests for DPD UK email handling."""

import re

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
)
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from tests.conftest import (
    _generate_fetch_side_effect,
    _generate_search_side_effect,
)


def _dpd_uk_email(
    subject: str,
    sender: str = "yourdelivery@dpd.co.uk",
) -> bytes:
    """Build a synthetic quoted-printable DPD UK notification."""
    return (
        f"From: Example Shop <{sender}>\r\n"
        "To: testuser@fake.email\r\n"
        f"Subject: {subject}\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/html; charset=UTF-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n\r\n"
        "<div>Your parcel: 123=\r\n"
        "4 5678 901 234</div>\r\n"
    ).encode()


def test_dpd_uk_registration():
    """DPD UK has independent data, entity, and aggregate registrations."""
    sensor_keys = {
        "dpd_uk_delivered",
        "dpd_uk_delivering",
        "dpd_uk_packages",
    }

    assert sensor_keys <= SENSOR_DATA.keys()
    assert sensor_keys <= SENSOR_TYPES.keys()
    assert "dpd_uk_tracking" in SENSOR_DATA
    assert "dpd_uk" in SHIPPERS
    assert SENSOR_DATA["dpd_uk_delivered"] == {}
    assert SENSOR_DATA["dpd_uk_delivering"]["today_only"] is True
    assert SENSOR_DATA["dpd_com_pl_tracking"]["pattern"] == ["\\d{13}[A-Z0-9]{1,2}"]


@pytest.mark.parametrize(
    "text",
    [
        "Your parcel: 1234 5678 901 234",
        "Your parcel:\t1234  5678\n901\t234",
    ],
)
def test_dpd_uk_tracking_pattern_and_normalization(text):
    """DPD UK references tolerate whitespace and normalize to 14 digits."""
    config = SENSOR_DATA["dpd_uk_tracking"]
    match = re.search(config["pattern"][0], text)

    assert match is not None
    assert re.sub(r"\s+", "", match.group(1)) == "12345678901234"


@pytest.mark.asyncio
async def test_dpd_uk_delivery_day_email(hass, mock_imap):
    """A delivery-day email is counted and returns canonical tracking."""
    email_content = _dpd_uk_email(
        "Your Samsung order will be delivered today between 14:39 - 15:39"
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.side_effect = _generate_search_side_effect()
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_content)

    result = await GenericShipper(hass, {}).process(
        mock_imap,
        "today",
        "dpd_uk_delivering",
    )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["12345678901234"]


@pytest.mark.asyncio
async def test_dpd_uk_expected_email_is_not_delivery_day(hass, mock_imap):
    """An early expectation notice is not counted as out for delivery."""
    email_content = _dpd_uk_email(
        "We're expecting your Example Shop parcel",
        sender="yourorder@dpd.co.uk",
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.side_effect = _generate_search_side_effect()
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_content)

    result = await GenericShipper(hass, {}).process(
        mock_imap,
        "today",
        "dpd_uk_delivering",
    )

    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []


def test_dpd_uk_sender_addresses_are_scoped():
    """Only the verified DPD UK sender addresses are configured."""
    assert SENSOR_DATA["dpd_uk_delivering"]["email"] == [
        "yourorder@dpd.co.uk",
        "yourdelivery@dpd.co.uk",
    ]
    assert "shop@example.com" not in SENSOR_DATA["dpd_uk_delivering"]["email"]


def test_dpd_uk_ignores_extended_search_window():
    """DPD UK arriving-today messages are searched only for the current day."""
    assert (
        GenericShipper._determine_search_date(
            "dpd_uk_delivering",
            "22-Apr-2026",
            "19-Apr-2026",
        )
        == "22-Apr-2026"
    )
    assert (
        GenericShipper._determine_search_date(
            "ups_delivering",
            "22-Apr-2026",
            "19-Apr-2026",
        )
        == "19-Apr-2026"
    )
