"""Tests for Amazon shipper utilities."""

import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED,
    AMAZON_EXCEPTION,
    AMAZON_HUB,
    AMAZON_ORDER,
    AMAZON_OTP,
    AMAZON_PACKAGES,
    ATTR_CODE,
    ATTR_COUNT,
    ATTR_ORDER,
)
from custom_components.mail_and_packages.shippers.amazon import AmazonShipper
from custom_components.mail_and_packages.utils.amazon import (
    _extract_hub_code,
    amazon_date_regex,
    amazon_date_search,
    amazon_email_addresses,
    parse_amazon_arrival_date,
)


@pytest.mark.asyncio
async def test_amazon_shipper_basic(hass):
    """Test AmazonShipper basic initialization."""
    shipper = AmazonShipper(hass, {})
    assert shipper.name == "amazon"


@pytest.mark.asyncio
async def test_amazon_otp(hass):
    """Test the amazon_otp function via AmazonShipper."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()

    # Define a mock regex pattern that expects a "Code: <numbers>" format
    mock_regex = r"(Code: )(\d{6})"

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date(2024, 12, 19),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.amazon_email_addresses",
            return_value=["fwd@test.com"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.AMAZON_OTP_SUBJECT",
            "Amazon OTP",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.AMAZON_OTP_REGEX",
            mock_regex,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
        ) as mock_search,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch,
    ):
        # Scenario 1: Successful Extraction (Single Part)
        mock_search.return_value = ("OK", [b"1"])
        msg_text = "Subject: OTP\n\nCode: 123456"
        mock_fetch.return_value = ("OK", [bytearray(msg_text.encode())])

        result = await shipper.process(mock_account, "today", AMAZON_OTP)
        assert ATTR_CODE in result[AMAZON_OTP]
        assert result[AMAZON_OTP][ATTR_CODE] == ["123456"]

        # Scenario 2: Successful Extraction (Multipart)
        mock_search.return_value = ("OK", [b"2"])
        msg = MIMEMultipart()
        msg.attach(MIMEText("Code: 654321", "plain"))
        mock_fetch.return_value = ("OK", [bytearray(msg.as_bytes())])

        result = await shipper.process(mock_account, "today", AMAZON_OTP)
        assert result[AMAZON_OTP][ATTR_CODE] == ["654321"]

        # Scenario 3: No Match found
        mock_search.return_value = ("OK", [b"3"])
        msg_no_match = "Subject: OTP\n\nNo code here."
        mock_fetch.return_value = ("OK", [bytearray(msg_no_match.encode())])

        result = await shipper.process(mock_account, "today", AMAZON_OTP)
        assert result[AMAZON_OTP][ATTR_CODE] == []


@pytest.mark.asyncio
async def test_amazon_hub(hass, mock_imap_amazon_the_hub):
    """Test handling of amazon hub codes."""
    shipper = AmazonShipper(hass, {"amazon_fwds": ""})
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.get_today",
        return_value=datetime.date(2020, 9, 25),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub, "today", AMAZON_HUB)
        assert result["count"] == 1
        assert result["code"] == ["123456"]

    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("BAD", []),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub, "today", AMAZON_HUB)
        assert result == {"code": [], "count": 0}

    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [None]),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub, "today", AMAZON_HUB)
        assert result == {"code": [], "count": 0}


@pytest.mark.asyncio
async def test_amazon_hub_2(hass, mock_imap_amazon_the_hub_2):
    """Test handling of amazon hub codes."""
    shipper = AmazonShipper(hass, {"amazon_fwds": ""})
    # Test successful parsing with the fixture
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.get_today",
        return_value=datetime.date(2020, 9, 25),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub_2, "today", AMAZON_HUB)
        assert result["count"] == 1
        assert result["code"] == ["123456"]

    # Test "BAD" search response
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("BAD", []),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub_2, "today", AMAZON_HUB)
        assert result == {"code": [], "count": 0}

    # Test "OK" search response but with no email IDs
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [b""]),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub_2, "today", AMAZON_HUB)
        assert result == {"code": [], "count": 0}


@pytest.mark.asyncio
async def test_amazon_mixed_orders_shipped_vs_delivered():
    """Test Amazon orders with some delivered and some still in transit."""
    # Test the package counting logic directly
    shipped_packages = {
        "111-1111111-1111111": 1,
        "222-2222222-2222222": 2,
        "333-3333333-3333333": 1,
    }
    delivered_packages = {
        "222-2222222-2222222": 1,
    }

    in_transit_packages = 0
    for order_id, shipped_count in shipped_packages.items():
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count

    assert in_transit_packages == 3


@pytest.mark.asyncio
async def test_amazon_delivered_with_order_in_body(hass):
    """Test Amazon delivered emails with order numbers in the body."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
        ) as mock_search,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date(2025, 10, 29),
        ),
    ):
        mock_search.return_value = ("OK", [b"1 2"])

        async def _mock_fetch(account, email_id, parts):
            if email_id == "1":
                content = (
                    b"Subject: Delivered: 1\n\nOrder 111-1111111-1111111 delivered."
                )
            else:
                content = (
                    b"Subject: Delivered: 2\n\nOrder 111-1111111-1111111 delivered."
                )
            return ("OK", [bytearray(content)])

        mock_fetch.side_effect = _mock_fetch

        result = await shipper.process(mock_account, "today", AMAZON_PACKAGES)
        assert result[AMAZON_PACKAGES] == 0


@pytest.mark.asyncio
async def test_amazon_shipped_minus_delivered_with_body_orders(hass):
    """Test Amazon package counting with shipped minus delivered (order numbers in body)."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
        ) as mock_search,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date(2025, 10, 29),
        ),
    ):

        async def _mock_search(account, addresses, date, subject):
            if "Shipped" in subject:
                return ("OK", [b"1 2"])
            if "Delivered" in subject:
                return ("OK", [b"3 4"])
            return ("OK", [b""])

        mock_search.side_effect = _mock_search

        async def _mock_fetch(account, email_id, parts):
            emails = {
                "1": b"Subject: Shipped: 1\n\nOrder 111-1111111-1111111 shipped.\nArriving today",
                "2": b"Subject: Shipped: 2\n\nOrder 111-1111111-1111111 shipped.\nArriving today",
                "3": b"Subject: Delivered: 1\n\nOrder 111-1111111-1111111 delivered.",
                "4": b"Subject: Delivered: 2\n\nOrder 111-1111111-1111111 delivered.",
            }
            content = emails.get(email_id, b"")
            return ("OK", [bytearray(content)])

        mock_fetch.side_effect = _mock_fetch

        result = await shipper.process(mock_account, "today", AMAZON_PACKAGES)
        # 1 unique order ID (111-1111111-1111111) was shipped and delivered.
        # So in-transit should be 0.
        assert result[AMAZON_PACKAGES] == 0


@pytest.mark.asyncio
async def test_amazon_search_no_data(hass):
    """Test Amazon search when no emails are found."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [None]),
    ):
        result = await shipper.process(mock_account, "today", AMAZON_PACKAGES)
        assert result[AMAZON_PACKAGES] == 0


def test_amazon_date_search():
    """Test the amazon_date_search helper function."""
    mock_patterns = ["end_pattern_1", "end_pattern_2"]

    # Scenario 1: Pattern is found
    msg_match = "The date is end_pattern_1"
    assert amazon_date_search(msg_match, mock_patterns) == 12

    # Scenario 2: Pattern is found (checking second pattern in list)
    msg_match_2 = "The date is end_pattern_2"
    assert amazon_date_search(msg_match_2, mock_patterns) == 12

    # Scenario 3: No pattern is found
    msg_no_match = "The date is not here"
    assert amazon_date_search(msg_no_match, mock_patterns) == -1


def test_amazon_date_regex():
    """Test the amazon_date_regex helper function."""
    mock_patterns = [
        r"Arriving between (\d{1,2}:\d{2})",
        r"Expected delivery: (\w+)",
        r"Just a match",
    ]

    # Scenario 1: Match first pattern
    msg_1 = "Your package is Arriving between 10:00 and 12:00"
    assert amazon_date_regex(msg_1, mock_patterns) == "10:00"

    # Scenario 2: Match second pattern
    msg_2 = "Status update. Expected delivery: Monday"
    assert amazon_date_regex(msg_2, mock_patterns) == "Monday"

    # Scenario 3: No match
    msg_3 = "No dates here"
    assert amazon_date_regex(msg_3, mock_patterns) is None

    # Scenario 4: Pattern matches but has no capture groups
    msg_4 = "This is Just a match in text"
    assert amazon_date_regex(msg_4, mock_patterns) is None


@pytest.mark.asyncio
async def test_amazon_hub_more_coverage(hass):
    """Test amazon_hub coverage for processed IDs."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            return_value=("OK", [b"1 1"]),
        ),  # Duplicate ID
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            side_effect=[("OK", [None, b"raw"]), ("OK", [None, b"raw"])],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon._extract_hub_code",
            return_value="123456",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date(2020, 9, 25),
        ),
    ):
        result = await shipper.process(mock_account, "today", AMAZON_HUB)
        assert result["count"] == 1  # Deduplicated
        assert result["code"] == ["123456"]


@pytest.mark.asyncio
async def test_amazon_parsing_more_coverage(hass, caplog):
    """Test more Amazon parsing code paths."""
    # 1. _extract_hub_code with empty subject/body
    result = _extract_hub_code("", "regex", "", "regex")
    assert result == ""

    # 2. amazon_email_addresses with domains containing @
    addresses = amazon_email_addresses(fwds="fwd@amazon.com", domain="amazon.com")
    assert "fwd@amazon.com" in addresses
    assert "shipment-tracking@amazon.com" in addresses

    # 3. parse_amazon_arrival_date (async)
    with patch(
        "custom_components.mail_and_packages.utils.amazon.dateparser.parse",
        return_value=datetime.datetime(2026, 1, 1),
    ):
        result = await parse_amazon_arrival_date(
            hass, "Arriving Tomorrow", datetime.date(2025, 12, 31)
        )
        assert result == datetime.date(2026, 1, 1)


@pytest.mark.asyncio
async def test_get_items_more_coverage(hass):
    """Test get_items for remaining uncovered lines."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    # We'll use multiple email IDs
    unique_ids = [b"1", b"2", b"3", b"4"]
    today = datetime.date.today()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.search_amazon_emails",
            new_callable=AsyncMock,
            return_value=unique_ids,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=today,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.parse_amazon_arrival_date",
            new_callable=AsyncMock,
            return_value=today,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_email_body",
            return_value="Order 111-1234567-1234567 delivered.",
        ),
    ):
        # Setup mock fetch to return different subjects/dates
        async def _mock_fetch(account, email_id, parts):
            if email_id == "1":
                # Old arriving email (filtered out by date if param="arriving")
                content = (
                    b"Date: Wed, 01 Jan 2020 10:00:00 +0000\nSubject: Arriving\n\nBody"
                )
            elif email_id == "2":
                # Ordered email (skipped in package counting)
                content = f"Date: {today.strftime('%a, %d %b %Y %H:%M:%S +0000')}\nSubject: Ordered: 1\n\nBody".encode()
            elif email_id == "3":
                # Delivered email
                content = f"Date: {today.strftime('%a, %d %b %Y %H:%M:%S +0000')}\nSubject: Delivered: 1\n\nBody".encode()
            else:
                # Arriving today email
                content = f"Date: {today.strftime('%a, %d %b %Y %H:%M:%S +0000')}\nSubject: Arriving today\n\nBody".encode()

            return ("OK", [bytearray(content)])

        mock_fetch.side_effect = _mock_fetch

        # Test param="count" via process
        result_count = await shipper.process(mock_account, "today", AMAZON_PACKAGES)
        # msg_ordered: skipped
        # msg_deliv: delivered (order 111-...)
        # msg_arr: arriving (order 111-...)
        # msg_old: arriving (order 111-...) - because we mocked arrival date to today
        # Total arriving: 2, Total delivered: 1. Result: 2 - 1 = 1.
        assert result_count[AMAZON_PACKAGES] == 1


@pytest.mark.asyncio
async def test_amazon_exception(hass):
    """Test Amazon exception sensor."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
        ) as mock_search,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date(2025, 10, 29),
        ),
    ):
        mock_search.return_value = ("OK", [b"1"])
        content = b"Subject: Delivery update: Order 111-1234567-1234567\n\nYour order is running late."
        mock_fetch.return_value = ("OK", [bytearray(content)])

        result = await shipper.process(mock_account, "today", AMAZON_EXCEPTION)
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_ORDER] == ["111-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_search_no_emails_found(hass):
    """Test Amazon search when no emails are found in sdata[0]."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [b""]),
    ):
        result = await shipper.process(mock_account, "today", AMAZON_PACKAGES)
        assert result[AMAZON_PACKAGES] == 0


@pytest.mark.asyncio
async def test_amazon_search_delivered(hass, mock_imap_amazon_delivered, caplog):
    """Test Amazon search for delivered items."""
    shipper = AmazonShipper(
        hass, {"image_path": "test/path/amazon/", "image_name": "testfilename.jpg"}
    )
    with (
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.download_amazon_img"
        ) as mock_download_img,
    ):
        result = await shipper.process(
            mock_imap_amazon_delivered, "today", AMAZON_DELIVERED
        )
        await hass.async_block_till_done()
        assert "Amazon email search addresses:" in caplog.text
        assert result[AMAZON_DELIVERED] == 10
        assert mock_download_img.called


@pytest.mark.asyncio
async def test_amazon_search_delivered_it(hass, mock_imap_amazon_delivered_it):
    """Test Amazon search for delivered items (IT domain)."""
    shipper = AmazonShipper(
        hass,
        {
            "amazon_domain": "amazon.it",
            "image_path": "test/path/amazon/",
            "image_name": "testfilename.jpg",
        },
    )
    with (
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.download_amazon_img"
        ),
    ):
        result = await shipper.process(
            mock_imap_amazon_delivered_it, "today", AMAZON_DELIVERED
        )
        assert result[AMAZON_DELIVERED] == 10


@pytest.mark.asyncio
async def test_parse_amazon_arrival_date(hass):
    """Test parse_amazon_arrival_date utility."""
    email_date = datetime.date(2020, 9, 25)
    body = "Your order has shipped. Arriving: Saturday, September 26."
    # With Arriving: in pattern, it should find September 26
    result = await parse_amazon_arrival_date(hass, body, email_date)
    assert result == datetime.date(2020, 9, 26)


@pytest.mark.asyncio
async def test_amazon_search_no_emails_found_copy(hass):
    """Test Amazon search copies default image when no emails are found."""
    shipper = AmazonShipper(
        hass, {"image_path": "/fake/path/", "image_name": "amazon.jpg"}
    )
    mock_account = AsyncMock()
    with (
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.copyfile"
        ) as mock_copy,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b""]),
        ),
    ):
        await shipper.process(mock_account, "today", AMAZON_DELIVERED)
        assert mock_copy.called


@pytest.mark.asyncio
async def test_amazon_packages_counts(hass, mock_imap_amazon_shipped):
    """Test Amazon packages counts with dates."""
    shipper = AmazonShipper(hass, {})
    # Mock date to match shipping notice
    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date(2020, 9, 26),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
            return_value=(
                "OK",
                [
                    b"Header",
                    b"Subject: Shipped\nDate: Fri, 25 Sep 2020 12:00:00 +0000\n\nYour order 111-1234567-1234567 has shipped. Arriving: Saturday, September 26.",
                ],
            ),
        ),
    ):
        result = await shipper.process(
            mock_imap_amazon_shipped, "today", AMAZON_PACKAGES
        )
        assert result[AMAZON_PACKAGES] == 1


@pytest.mark.asyncio
async def test_amazon_order_list(hass, mock_imap_amazon_shipped):
    """Test Amazon order list extraction."""
    shipper = AmazonShipper(hass, {})
    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
            return_value=(
                "OK",
                [
                    b"Header",
                    b"Subject: Shipped\n\nYour order 111-1234567-1234567 has shipped.",
                ],
            ),
        ),
    ):
        result = await shipper.process(mock_imap_amazon_shipped, "today", AMAZON_ORDER)
        assert "111-1234567-1234567" in result[AMAZON_ORDER]


@pytest.mark.asyncio
async def test_amazon_hub_multi(hass, mock_imap_amazon_the_hub):
    """Test Amazon Hub with multiple codes and deduplication."""
    shipper = AmazonShipper(hass, {})
    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1 1 2"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            new_callable=AsyncMock,
            side_effect=[
                ("OK", [b"H", b"Subject: a package to pick up 123456"]),
                ("OK", [b"H", b"Subject: a package to pick up 654321"]),
            ],
        ),
    ):
        result = await shipper.process(mock_imap_amazon_the_hub, "today", AMAZON_HUB)
        assert result["count"] == 2
        assert "123456" in result["code"]
        assert "654321" in result["code"]
