"""Tests for the Home Depot shipper."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.const import ATTR_COUNT, ATTR_TRACKING
from custom_components.mail_and_packages.shippers.generic import GenericShipper


@pytest.mark.asyncio
async def test_home_depot_delivering(hass):
    """Test Home Depot out for delivery email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {})

    msg = MIMEMultipart("alternative")
    msg["From"] = "The Home Depot <homedepot@order.homedepot.com>"
    msg["Subject"] = "Your Home Depot order is out for delivery today."
    msg["Date"] = "Tue, 10 Mar 2026 11:16:00 -0400"

    html_body = """
    <html>
      <body>
        <h2>Order # WK00000000</h2>
        <p>Get ready, Customer! Your delivery arrives today!</p>
        <p>Your delivery is on track to arrive between 6:00am and 8:00pm with one of our carriers.</p>
        <p>Deliver to Customer: 123 Main St, Anytown, CT 00000</p>
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
            "custom_components.mail_and_packages.utils.shipper.email_fetch",
            return_value=("OK", [msg.as_bytes()]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch_headers",
            return_value=(
                "OK",
                [b"Subject: Your Home Depot order is out for delivery today.\r\n"],
            ),
        ),
    ):
        result = await shipper.process(
            account=mock_account,
            date="10-Mar-2026",
            sensor_type="home_depot_delivering",
        )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["WK00000000"]


@pytest.mark.asyncio
async def test_home_depot_shipped(hass):
    """Test Home Depot package shipped email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {})

    msg = MIMEMultipart("alternative")
    msg["From"] = "The Home Depot <HomeDepot@order.homedepot.com>"
    msg["Subject"] = "Order #WK00000000 Shipped: Your order is on its way, Customer!"
    msg["Date"] = "Sun, 08 Mar 2026 18:07:00 -0400"

    html_body = """
    <html>
      <body>
        <b>Order #: </b><a href="#">WK00000000</a>
        <b>Your package has shipped, Customer!</b>
        <p>Tracking ID: 123456789012</p>
        <p>ETA by FedEx: Tue, Mar 10</p>
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
            "custom_components.mail_and_packages.utils.shipper.email_fetch",
            return_value=("OK", [msg.as_bytes()]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch_headers",
            return_value=(
                "OK",
                [
                    b"Subject: Order #WK00000000 Shipped: Your order is on its way, Customer!\r\n"
                ],
            ),
        ),
    ):
        result = await shipper.process(
            account=mock_account,
            date="08-Mar-2026",
            sensor_type="home_depot_packages",
        )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["WK00000000"]
    assert result["home_depot_carrier_tracking"] == {"WK00000000": "123456789012"}


@pytest.mark.asyncio
async def test_home_depot_marketplace_carrier_tracking(hass):
    """Test extraction of embedded carrier tracking number for Home Depot deduplication."""
    shipper = GenericShipper(hass, {})

    msg = MIMEMultipart("alternative")
    msg["From"] = "The Home Depot <HomeDepot@order.homedepot.com>"
    msg["Subject"] = "Order #WK00000000 Shipped: Your order is on its way, Customer!"
    msg["Date"] = "Sun, 08 Mar 2026 18:07:00 -0400"

    html_body = """
    <html>
      <body>
        <b>Order #: </b><a href="#">WK00000000</a>
        <p>Tracking ID: 123456789012</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            return_value=["WK00000000"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic._find_carrier_number",
            return_value="123456789012",
        ),
        patch(
            "custom_components.mail_and_packages.utils.shipper.email_fetch",
            return_value=("OK", [msg.as_bytes()]),
        ),
    ):
        mapping = await shipper._collect_carrier_tracking(
            "home_depot_packages",
            [b"1"],
            mock_account,
        )

    assert mapping == {"home_depot_carrier_tracking": {"WK00000000": "123456789012"}}
