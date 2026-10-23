"""USPS pickup email parsing and exposed sensor data."""

import re
from datetime import date
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.const import SENSOR_DATA
from custom_components.mail_and_packages.sensor import PackagesSensor
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from custom_components.mail_and_packages.shippers.generic.pickup import (
    parse_pickup,
    summarize_pickups,
)

# Redacted structure from actual USPS confirmation and completion emails.
# No sender recipient, address, phone, or other personal information retained.
CONFIRMATION = """<html><body>
<div>Confirmation #: WEC784165980</div>
<p>This email confirms your Package Pickup request.</p>
<h3>Pickup Details</h3>
<div>Pick Up for: [REDACTED]</div>
<div>Total Packages:<span>16</span></div>
<h3>Scheduled Pickups</h3>
<table><tr><th>Requested Pickup Date</th><th>Confirmation #</th></tr>
<tr><td>10/20/2026</td><td>WEC784165980</td></tr></table>
</body></html>"""
COMPLETION = """<html><body>
<div>Confirmation #: WEC784165980</div>
<p>Collected Piece Count:16</p>
<p>We have successfully completed your Package Pickup.</p>
<div>Pickup Details</div><div>Confirmation #:</div><div>WEC784165980</div>
<div>Total Packages:<span>16</span></div>
<div>Scheduled Pickup Date:</div><div>10/20/2026</div>
</body></html>"""


def message(html, completed=False):
    """Build an email with the real subject and redacted HTML structure."""
    msg = MIMEText(html, "html")
    msg["Subject"] = "USPS - Your Package Pickup Request" + (
        "" if completed else " Confirmation"
    )
    return msg.as_bytes()


def booking(when, ref="WEC784165980", packages=16):
    """Construct a second pickup or an edited confirmation."""
    return message(
        CONFIRMATION.replace("10/20/2026", when)
        .replace("WEC784165980", ref)
        .replace("<span>16</span>", f"<span>{packages}</span>")
    )


def test_real_message_shapes_and_count_regex():
    """Real header ordering and tags before count both parse."""
    assert (
        re.search(SENSOR_DATA["usps_pickup"]["body"][0], CONFIRMATION).group(1) == "16"
    )
    assert parse_pickup(message(CONFIRMATION))["pickup_date"] == date(2026, 10, 20)
    completed = parse_pickup(message(COMPLETION, completed=True))
    assert completed["completed"] is True
    assert completed["packages"] == 16
    assert completed["confirmation"] == "WEC784165980"
    assert parse_pickup(message(CONFIRMATION, completed=True)) is None


@pytest.mark.parametrize(
    ("today", "when", "expected"),
    [
        (date(2026, 10, 20), "10/20/2026", (True, False, 0)),
        (date(2026, 10, 19), "10/20/2026", (False, True, 1)),
        (date(2026, 10, 17), "10/20/2026", (False, False, 3)),
    ],
)
def test_upcoming_dates(today, when, expected):
    """Upcoming pickup includes any future date and local day offset."""
    result = summarize_pickups([parse_pickup(booking(when))], today)
    assert (
        result["pickup_today"],
        result["pickup_tomorrow"],
        result["days_until"],
    ) == expected
    assert result["pickup_date"] == "2026-10-20"
    assert result["confirmation"] == "WEC784165980"
    assert result["packages"] == 16


def test_past_and_completed():
    """Past or completed pickup cannot remain upcoming."""
    booked = parse_pickup(message(CONFIRMATION))
    done = parse_pickup(message(COMPLETION, completed=True))
    assert summarize_pickups([booked], date(2026, 10, 21))["pickup_date"] is None
    result = summarize_pickups([booked, done], date(2026, 10, 20))
    assert result["pickup_date"] is None
    assert result["last_pickup_completed_date"] == "2026-10-20"
    assert result["last_pickup_completed_confirmation"] == "WEC784165980"
    assert result["last_pickup_completed_packages"] == 16


def test_two_pickups_and_replacement():
    """Select earliest future date; later email with same reference wins."""
    events = [
        parse_pickup(booking("10/21/2026")),
        parse_pickup(booking("10/23/2026", "WEC222222222", 3)),
        parse_pickup(booking("10/24/2026", packages=4)),
    ]
    result = summarize_pickups(events, date(2026, 10, 20))
    assert result["pickup_date"] == "2026-10-23"
    assert result["confirmation"] == "WEC222222222"
    assert result["packages"] == 3


@pytest.mark.asyncio
async def test_shipper_process_publishes_pickup_details(hass):
    """The shipper exposes attributes and counts only upcoming packages."""
    shipper = GenericShipper(hass, {})
    with (
        patch.object(
            shipper,
            "_search_for_emails",
            new=AsyncMock(return_value=(16, [b"1"], False)),
        ),
        patch.object(
            shipper, "_process_tracking_numbers", new=AsyncMock(return_value=[])
        ),
        patch.object(
            shipper, "_collect_carrier_tracking", new=AsyncMock(return_value={})
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch",
            new=AsyncMock(return_value=("OK", [message(CONFIRMATION)])),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.dt_util.now",
            return_value=__import__("datetime").datetime(
                2026, 10, 19, 12, 0, tzinfo=__import__("datetime").UTC
            ),
        ),
    ):
        result = await shipper.process(AsyncMock(), "19-Oct-2026", "usps_pickup")
    assert result["count"] == 16
    assert result["usps_pickup_details"]["pickup_tomorrow"] is True
    assert result["usps_pickup_details"]["pickup_date"] == "2026-10-20"


def test_sensor_exposes_pickup_details():
    """Coordinator details become the pickup sensor's visible attributes."""
    sensor = object.__new__(PackagesSensor)
    sensor.type = "usps_pickup"
    sensor._name = "Mail USPS Scheduled Pickup"
    sensor.coordinator = AsyncMock()
    sensor.coordinator.data = {
        "usps_pickup_details": summarize_pickups(
            [parse_pickup(message(CONFIRMATION))], date(2026, 10, 19)
        )
    }
    assert sensor.extra_state_attributes["pickup_tomorrow"] is True
    assert sensor.extra_state_attributes["confirmation"] == "WEC784165980"


def test_pickup_uses_lookback_search_date():
    """Booking emails remain visible on the following days."""
    assert (
        GenericShipper._determine_search_date(
            "usps_pickup", "20-Oct-2026", "17-Oct-2026"
        )
        == "17-Oct-2026"
    )


def test_completed_pickup_keeps_other_upcoming_booking():
    """Completion for one reference does not hide a separate future pickup."""
    events = [
        parse_pickup(message(CONFIRMATION)),
        parse_pickup(booking("10/24/2026", "WEC222222222", 3)),
        parse_pickup(message(COMPLETION, completed=True)),
    ]
    result = summarize_pickups(events, date(2026, 10, 20))
    assert result["pickup_date"] == "2026-10-24"
    assert result["packages"] == 3
    assert result["last_pickup_completed_confirmation"] == "WEC784165980"
