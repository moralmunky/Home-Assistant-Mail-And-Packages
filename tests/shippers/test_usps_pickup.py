"""Tests for USPS pickup sensor processing via generic shipper."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.shippers.generic import GenericShipper


@pytest.mark.asyncio
async def test_usps_pickup_email_generic_shipper(hass):
    """Test parsing of USPS Scheduled Pickup email via GenericShipper."""
    shipper = GenericShipper(hass, {})

    msg = MIMEMultipart("alternative")
    msg["From"] = "auto-reply@usps.com"
    msg["Subject"] = "USPS - Your Package Pickup Request"
    msg["Date"] = "Wed, 12 Aug 2026 12:46:26 -0400"
    html_body = """
    <html>
      <body>
        <p>Thank you for using USPS.com. We have successfully completed your Package Pickup.</p>
        <p>Confirmation #: WEC000000000</p>
        <p>Total Packages: 50</p>
        <p>Scheduled Pickup Date: 08/12/2026</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch",
            return_value=("OK", [msg.as_bytes()]),
        ),
        patch(
            "custom_components.mail_and_packages.utils.email.email_fetch",
            return_value=("OK", [msg.as_bytes()]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch_headers",
            return_value=("OK", [b"Subject: USPS - Your Package Pickup Request\r\n"]),
        ),
    ):
        result = await shipper.process(
            account=mock_account,
            date="12-Aug-2026",
            sensor_type="usps_pickup",
        )

    assert result["count"] == 50
