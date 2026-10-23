"""USPS pickup email parsing and exposed sensor data."""

import re
from datetime import date
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.const import SENSOR_DATA
from custom_components.mail_and_packages.sensor import PackagesSensor
from custom_components.mail_and_packages.shippers.generic import GenericShipper, pickup
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


def message(html, completed=False, subject=None):
    """Build an email with redacted HTML and a selectable subject."""
    msg = MIMEText(html, "html")
    if subject is None:
        subject = "USPS - Your Package Pickup Request" + (
            "" if completed else " Confirmation"
        )
    msg["Subject"] = subject
    return msg.as_bytes()


def booking(when, ref="WEC784165980", packages=16):
    """Construct a second pickup or an edited confirmation."""
    return message(
        CONFIRMATION.replace("10/20/2026", when)
        .replace("WEC784165980", ref)
        .replace("<span>16</span>", f"<span>{packages}</span>")
    )


def test_parse_pickup_rejects_unrecognized_subject():
    """Reject unrelated messages."""
    assert parse_pickup(message(CONFIRMATION, subject="Other")) is None


def test_parse_pickup_rejects_unexpected_subject_suffix():
    """Reject unsupported USPS subject suffixes."""
    subject = "USPS - Your Package Pickup Request Update"
    assert parse_pickup(message(CONFIRMATION, subject=subject)) is None


def test_html_part_without_bytes_payload(monkeypatch):
    """Ignore an HTML part with a nonbytes decoded payload."""
    msg = MIMEMultipart()
    part = MIMEBase("text", "html")
    msg.attach(part)
    monkeypatch.setattr(part, "get_payload", lambda decode=True: "text")
    assert pickup._pickup_text(msg) == ""


def test_parse_pickup_with_empty_html_body():
    """Return no pickup when an HTML part has an empty body."""
    msg = MIMEText("", "html")
    msg["Subject"] = "USPS - Your Package Pickup Request Confirmation"
    assert parse_pickup(msg.as_bytes()) is None


def test_parse_pickup_without_html_body():
    """Return no pickup for plain text mail."""
    assert parse_pickup(MIMEText("plain text").as_bytes()) is None


def test_completed_pickup_with_spaces_in_subject():
    """Normalize surrounding whitespace in a completion subject."""
    html = COMPLETION
    msg = MIMEText(html, "html")
    msg["Subject"] = " USPS - Your Package Pickup Request "
    assert parse_pickup(msg.as_bytes())["completed"] is True


def test_parse_pickup_requires_completion_phrase():
    """Require the USPS completion phrase."""
    html = "<html>Scheduled Pickup Date: 10/20/2026 Confirmation #: WEC123456789</html>"
    assert parse_pickup(message(html, completed=True)) is None


def test_parse_pickup_without_date():
    """Return no pickup when the date is absent."""
    assert parse_pickup(message("<html>Confirmation #: WEC123456789</html>")) is None


def test_parse_pickup_with_invalid_date():
    """Reject malformed calendar dates."""
    html = CONFIRMATION.replace("10/20/2026", "13/40/2026")
    assert parse_pickup(message(html)) is None


def test_parse_pickup_without_reference():
    """Return no pickup without a reference."""
    html = "<html>Requested Pickup Date 10/20/2026</html>"
    assert parse_pickup(message(html)) is None


def test_parse_pickup_without_package_count():
    """Allow a missing package count."""
    html = "<html>Requested Pickup Date Confirmation # 10/20/2026 WEC123456789</html>"
    result = parse_pickup(message(html))
    assert result["packages"] is None


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
