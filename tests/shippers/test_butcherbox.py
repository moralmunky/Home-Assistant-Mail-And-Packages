"""Tests for the ButcherBox shipper."""

import email
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
)
from custom_components.mail_and_packages.shippers.generic import GenericShipper

TRACKING = "SH123456789012345678"

# Two real shipments a month apart, both SH + exactly 18 digits. The pattern
# keeps a tolerant range around that rather than pinning the width: failing to
# extract is silent (a delivered box keeps showing as out for delivery until
# the email ages out of the search window), while the extra slack costs
# nothing observable.
OBSERVED_IDS = ["SH523753089708052026", "SH495736686534322026"]

# Klaviyo's unsubscribe ULIDs appear in every one of these emails and can carry
# an "SH<digits>" substring -- SH7 in this real example.
KLAVIYO_ULID = "01KZXRR6FY04KNC7SH7T6J6KX8"

OUT_FOR_DELIVERY_SUBJECT = "Your box is out for delivery!"
# The live subject ends in a package emoji carried as a MIME encoded-word.
DELIVERED_SUBJECT = "Your order is HERE! =?UTF-8?B?8J+Tpg==?="
SHIPPED_SUBJECT = "Your order has shipped!"


def _load(name: str) -> bytes:
    """Read a ButcherBox email fixture."""
    return Path(f"tests/test_emails/{name}").read_bytes()


async def _process(hass, raw: bytes, subject: str, sensor_type: str) -> dict:
    """Run GenericShipper against a single fixture email."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.search.email_search",
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.helpers.email_fetch",
            return_value=("OK", [raw]),
        ),
        patch(
            "custom_components.mail_and_packages.utils.email.email_fetch",
            return_value=("OK", [raw]),
        ),
        patch(
            "custom_components.mail_and_packages.utils.shipper.email_fetch",
            return_value=("OK", [raw]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.helpers.email_fetch_headers",
            return_value=("OK", [f"Subject: {subject}\r\n".encode()]),
        ),
    ):
        return await shipper.process(
            account=mock_account,
            date="11-Sep-2026",
            sensor_type=sensor_type,
        )


@pytest.mark.asyncio
async def test_butcherbox_delivering(hass):
    """Test ButcherBox out for delivery email parsing."""
    result = await _process(
        hass,
        _load("butcherbox_out_for_delivery.eml"),
        OUT_FOR_DELIVERY_SUBJECT,
        "butcherbox_delivering",
    )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [TRACKING]


@pytest.mark.asyncio
async def test_butcherbox_delivered(hass):
    """Test ButcherBox delivered email parsing.

    The subject carries a trailing emoji as a MIME encoded-word, so this also
    covers the header decode in _verify_matched_subjects.
    """
    result = await _process(
        hass,
        _load("butcherbox_delivered.eml"),
        DELIVERED_SUBJECT,
        "butcherbox_delivered",
    )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [TRACKING]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sensor_type", ["butcherbox_delivering", "butcherbox_delivered"]
)
async def test_butcherbox_shipped_is_not_tracked(hass, sensor_type):
    """ButcherBox's "order has shipped" notice must not count as a package.

    General in-transit notices are excluded by design (docs/architecture.md);
    the shipment is counted once it is out for delivery.
    """
    result = await _process(
        hass,
        _load("butcherbox_shipped.eml"),
        SHIPPED_SUBJECT,
        sensor_type,
    )

    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []


def test_butcherbox_tracking_survives_quoted_printable_soft_break():
    """The tracking number is split across a soft line break in the HTML part.

    ButcherBox's templates wrap the AfterShip tracking URL mid-number, so in
    the HTML part the number is only recoverable after quoted-printable
    decoding.
    """
    msg = email.message_from_bytes(_load("butcherbox_out_for_delivery.eml"))
    html = next(p for p in msg.walk() if p.get_content_type() == "text/html")

    # Broken across a soft line break on the wire...
    assert TRACKING not in html.get_payload(decode=False)
    # ...and whole once decoded, where the configured pattern can see it.
    decoded = html.get_payload(decode=True).decode("utf-8")
    pattern = SENSOR_DATA["butcherbox_tracking"]["pattern"][0]
    assert re.findall(pattern, decoded) == [TRACKING]


@pytest.mark.asyncio
async def test_butcherbox_delivered_dedupes_delivering(hass):
    """A delivered box stops being counted as out for delivery.

    Both emails carry the same ButcherBox shipment id, which is what makes the
    two sensors joinable.
    """
    shipper = GenericShipper(hass, {})
    delivering = (
        "butcherbox_delivering",
        {
            ATTR_COUNT: 1,
            ATTR_TRACKING: [TRACKING],
            "butcherbox_delivering": 1,
        },
    )
    delivered = (
        "butcherbox_delivered",
        {
            ATTR_COUNT: 1,
            ATTR_TRACKING: [TRACKING],
            "butcherbox_delivered": 1,
        },
    )

    shipper._deduplicate_batch_tracking([delivering, delivered])

    assert delivering[1]["butcherbox_delivering"] == 0
    assert delivering[1][ATTR_TRACKING] == []
    assert delivered[1]["butcherbox_delivered"] == 1


@pytest.mark.asyncio
async def test_butcherbox_packages_is_rollup(hass):
    """butcherbox_packages is computed as delivering + delivered."""
    shipper = GenericShipper(hass, {})
    packages = ("butcherbox_packages", {})
    batch = [
        ("butcherbox_delivering", {"butcherbox_delivering": 1}),
        ("butcherbox_delivered", {"butcherbox_delivered": 2}),
        packages,
    ]

    shipper._compute_package_totals(batch)

    assert packages[1]["butcherbox_packages"] == 3


def test_butcherbox_is_registered():
    """ButcherBox is wired into the shipper and sensor registries."""
    assert "butcherbox" in SHIPPERS
    for suffix in ("delivering", "delivered", "packages"):
        assert f"butcherbox_{suffix}" in SENSOR_DATA
        assert f"butcherbox_{suffix}" in SENSOR_TYPES

    # An empty config is what marks a sensor as a computed rollup rather than
    # one that runs its own IMAP search.
    assert SENSOR_DATA["butcherbox_packages"] == {}


@pytest.mark.parametrize("tracking_id", OBSERVED_IDS)
def test_butcherbox_pattern_matches_observed_ids(tracking_id):
    """Both observed shipment ids are matched by the configured pattern."""
    pattern = SENSOR_DATA["butcherbox_tracking"]["pattern"][0]
    assert re.findall(pattern, f"tracking-number={tracking_id}") == [tracking_id]


def test_butcherbox_pattern_ignores_klaviyo_ulid():
    """The Klaviyo unsubscribe ULID must not be read as a shipment id.

    It is present in every ButcherBox email and contains an "SH<digits>"
    substring, so a looser pattern would pick it up instead.
    """
    pattern = SENSOR_DATA["butcherbox_tracking"]["pattern"][0]
    assert re.findall(pattern, KLAVIYO_ULID) == []


@pytest.mark.parametrize(
    "fixture",
    [
        "butcherbox_out_for_delivery.eml",
        "butcherbox_delivered.eml",
        "butcherbox_shipped.eml",
    ],
)
def test_butcherbox_one_tracking_id_per_email(fixture):
    """Each email yields exactly one shipment id across all of its parts.

    The fixtures carry a Klaviyo footer, so this fails if the pattern starts
    matching unsubscribe tokens.
    """
    msg = email.message_from_bytes(_load(fixture))
    pattern = SENSOR_DATA["butcherbox_tracking"]["pattern"][0]
    found = set()
    for part in msg.walk():
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        body = part.get_payload(decode=True).decode("utf-8", "ignore")
        found.update(re.findall(pattern, body))
    assert found == {TRACKING}
