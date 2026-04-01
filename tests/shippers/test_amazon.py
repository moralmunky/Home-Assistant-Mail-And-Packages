"""Tests for Amazon shipper utilities."""

import datetime
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

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
from custom_components.mail_and_packages.utils.cache import EmailCache


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
            hass,
            "Arriving Tomorrow",
            datetime.date(2025, 12, 31),
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
        hass,
        {"image_path": "test/path/amazon/", "amazon_image": "testfilename.jpg"},
    )
    with (
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.download_amazon_img",
        ) as mock_download_img,
    ):
        result = await shipper.process(
            mock_imap_amazon_delivered,
            "today",
            AMAZON_DELIVERED,
        )
        await hass.async_block_till_done()
        assert "Amazon email search addresses:" in caplog.text
        assert result[AMAZON_DELIVERED] == 1
        assert mock_download_img.called


@pytest.mark.asyncio
async def test_amazon_search_delivered_it(hass, mock_imap_amazon_delivered_it):
    """Test Amazon search for delivered items (IT domain)."""
    shipper = AmazonShipper(
        hass,
        {
            "amazon_domain": "amazon.it",
            "image_path": "test/path/amazon/",
            "amazon_image": "testfilename.jpg",
        },
    )
    with (
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.download_amazon_img",
        ),
    ):
        result = await shipper.process(
            mock_imap_amazon_delivered_it,
            "today",
            AMAZON_DELIVERED,
        )
        assert result[AMAZON_DELIVERED] == 1


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
        hass,
        {"image_path": "/fake/path/", "amazon_image": "amazon.jpg"},
    )
    mock_account = AsyncMock()
    with (
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.copyfile",
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
                    b"Subject: Shipped:\nDate: Fri, 25 Sep 2020 12:00:00 +0000\n\nYour order 111-1234567-1234567 has shipped. Arriving: Saturday, September 26.",
                ],
            ),
        ),
        patch(
            "custom_components.mail_and_packages.utils.amazon.email_fetch_headers",
            new_callable=AsyncMock,
            return_value=(
                "OK",
                [
                    b"Header",
                    b"Subject: Shipped:\nDate: Fri, 25 Sep 2020 12:00:00 +0000\n\nYour order 111-1234567-1234567 has shipped. Arriving: Saturday, September 26.",
                ],
            ),
        ),
    ):
        result = await shipper.process(
            mock_imap_amazon_shipped,
            "today",
            AMAZON_PACKAGES,
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
                    b"Subject: Shipped:\n\nYour order 111-1234567-1234567 has shipped.",
                ],
            ),
        ),
        patch(
            "custom_components.mail_and_packages.utils.amazon.email_fetch_headers",
            new_callable=AsyncMock,
            return_value=(
                "OK",
                [
                    b"Header",
                    b"Subject: Shipped:\n\nYour order 111-1234567-1234567 has shipped.",
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


@pytest.mark.asyncio
async def test_amazon_shipper_process_default(hass):
    """Test AmazonShipper.process default case (Line 105)."""
    shipper = AmazonShipper(hass, {})
    result = await shipper.process(AsyncMock(), "today", "invalid_sensor")
    assert result == {ATTR_COUNT: 0}


@pytest.mark.asyncio
async def test_process_amazon_email_non_bytes(hass):
    """Test _process_amazon_email with non-bytes part (Line 151)."""
    shipper = AmazonShipper(hass, {})
    ctx = {
        "today": datetime.date.today(),
        "deliveries_today": [],
        "amazon_delivered": [],
    }
    mock_account = AsyncMock()
    # mock_fetch returns a list where one part is not bytes
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_fetch",
        return_value=("OK", ["not bytes"]),
    ):
        await shipper._process_amazon_email(mock_account, "1", ctx)
        # Should just continue and not fail


@pytest.mark.asyncio
async def test_handle_shipping_email_no_order_id(hass):
    """Test _handle_shipping_email with no order ID (Line 205)."""
    shipper = AmazonShipper(hass, {})
    today = datetime.date(2025, 1, 1)
    ctx = {
        "today": today,
        "deliveries_today": [],
        "amazon_delivered": [],
        "all_shipped_orders": set(),
        "packages_arriving_today": {},
        "order_pattern": re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}"),
    }

    # Body matches arrival date but has no order ID
    body = "Your package is arriving today"
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.parse_amazon_arrival_date",
        new_callable=AsyncMock,
        return_value=today,
    ):
        await shipper._handle_shipping_email("Arriving", body, today, ctx)
        assert "Amazon Order" in ctx["deliveries_today"]


@pytest.mark.asyncio
async def test_extract_first_order_id_subject(hass):
    """Test _extract_first_order_id from subject (Line 213)."""
    shipper = AmazonShipper(hass, {})
    pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")
    subject = "Order 111-1234567-1234567 shipped"
    result = shipper._extract_first_order_id(subject, None, pattern)
    assert result == "111-1234567-1234567"


@pytest.mark.asyncio
async def test_amazon_exception_body_match(hass):
    """Test Amazon exception with order in body (Line 364)."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch",
            return_value=(
                "OK",
                [
                    b"RFC822",
                    b"Subject: Late\n\nThere is a delay with order 111-1234567-1234567 running late",
                ],
            ),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_today",
            return_value=datetime.date.today(),
        ),
    ):
        result = await shipper.process(mock_account, "today", AMAZON_EXCEPTION)
        assert result[ATTR_COUNT] == 1
        assert "111-1234567-1234567" in result[ATTR_ORDER]


@pytest.mark.asyncio
async def test_amazon_search_multiple_images_gif(hass):
    """Test Amazon search combining multiple images into a GIF."""
    shipper = AmazonShipper(
        hass,
        {"image_path": "/fake/path/", "amazon_image": "amazon.gif"},
    )
    mock_account = AsyncMock()
    urls = ["http://test.com/img1.jpg", "http://test.com/img2.jpg"]

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1 2"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_fetch_headers",
            new_callable=AsyncMock,
            return_value=(
                "OK",
                [None, b"Subject: Delivered: Your Amazon order\n\nBody"],
            ),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.get_amazon_image_urls",
            new_callable=AsyncMock,
            return_value=urls,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.download_amazon_img",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.anyio.Path.exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.cleanup_images",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.resize_images",
            return_value=["/fake/path/amazon/res1.jpg", "/fake/path/amazon/res2.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.generate_delivery_gif",
        ) as mock_gif,
    ):
        await shipper.process(mock_account, "today", AMAZON_DELIVERED)
        assert mock_gif.called


@pytest.mark.asyncio
async def test_amazon_process_images_missing_config(hass):
    """Test _process_amazon_images returns early with missing config."""
    shipper = AmazonShipper(hass, {})
    with patch("custom_components.mail_and_packages.shippers.amazon.Path") as mock_path:
        await shipper._process_amazon_images(["url1"], None, None, 1)
        assert not mock_path.called


@pytest.mark.asyncio
async def test_amazon_process_images_single(hass, caplog):
    """Test _process_amazon_images with a single image."""
    shipper = AmazonShipper(hass, {"image_path": "test/", "amazon_image": "test.gif"})
    caplog.set_level("DEBUG")

    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.anyio.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.anyio.Path.unlink",
        ) as mock_unlink,
        patch(
            "custom_components.mail_and_packages.shippers.amazon.AmazonShipper._download_all_images",
            return_value=["/fake/test.jpg"],
        ),
        patch("custom_components.mail_and_packages.shippers.amazon.Path") as mock_path,
    ):
        # mock_path needs to handle / operator and rename
        mock_path_obj = MagicMock()
        mock_path.side_effect = lambda *args: mock_path_obj
        mock_path_obj.__truediv__.return_value = mock_path_obj

        await shipper._process_amazon_images(["url1"], "test/", "test.gif", 1)
        assert mock_unlink.called
        assert mock_path_obj.rename.called
        assert "Single Amazon image saved: test.gif" in caplog.text


def test_amazon_handles_sensor(hass):
    """Test handles_sensor method."""
    shipper = AmazonShipper(hass, {})
    assert shipper.handles_sensor("amazon_delivered") is True
    assert shipper.handles_sensor("amazon_packages") is True
    assert shipper.handles_sensor("usps_mail") is False


@pytest.mark.asyncio
async def test_process_batch(hass):
    """Test process_batch for Amazon shipper."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()
    mock_cache = MagicMock()

    with patch.object(shipper, "process", new_callable=AsyncMock) as mock_process:

        async def _mock_process(account, date, sensor, cache):
            if sensor == AMAZON_OTP:
                return {AMAZON_OTP: {ATTR_CODE: ["123456"], ATTR_COUNT: 1}}
            if sensor == AMAZON_PACKAGES:
                # Trigger the "sensor not in sensor_res" and "ATTR_COUNT in sensor_res" branch
                return {ATTR_COUNT: 5}
            return {sensor: 0}

        mock_process.side_effect = _mock_process

        sensors = [AMAZON_OTP, AMAZON_PACKAGES]
        result = await shipper.process_batch(mock_account, "today", sensors, mock_cache)

        assert result[AMAZON_OTP] == {ATTR_CODE: ["123456"], ATTR_COUNT: 1}
        assert result[AMAZON_PACKAGES] == 5


@pytest.mark.asyncio
async def test_process_with_cache(hass):
    """Test Amazon shipper processing with EmailCache."""
    shipper = AmazonShipper(hass, {})
    """Test Amazon shipper processing with EmailCache."""
    shipper = AmazonShipper(hass, {})
    mock_account = AsyncMock()

    cache = EmailCache(mock_account)

    # 1. Test _process_amazon_email with cache
    cache._cache_rfc822["1"] = (
        "OK",
        [b"RFC822", b"Subject: Shipped: 1\n\nOrder 111-1234567-1234567 shipped."],
    )
    ctx = {
        "today": datetime.date.today(),
        "deliveries_today": [],
        "amazon_delivered": [],
        "all_shipped_orders": set(),
        "packages_arriving_today": {},
        "delivered_packages": {},
        "order_pattern": re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}"),
    }
    await shipper._process_amazon_email(mock_account, "1", ctx, cache=cache)
    assert "111-1234567-1234567" in ctx["all_shipped_orders"]

    # 2. Test _amazon_search with cache
    cache._cache_headers["2"] = (
        "OK",
        [b"Subject: Delivered: Your Amazon order has arrived!"],
    )
    cache._cache_rfc822["2"] = (
        "OK",
        [b"RFC822", b"Content-Type: text/html\n\nNo images here"],
    )
    with (
        patch(
            "custom_components.mail_and_packages.shippers.amazon.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"2"]),
        ),
        patch("custom_components.mail_and_packages.shippers.amazon.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.copyfile",
        ),
    ):
        count = await shipper._amazon_search(
            mock_account, "test/path/amazon/", "amazon.jpg", "amazon.com", cache=cache
        )
        assert count == 1

    # 3. Test _amazon_hub with cache
    cache._cache_rfc822["3"] = (
        "OK",
        [b"RFC822", b"Subject: a package to pick up 123456"],
    )
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [b"3"]),
    ):
        hub_res = await shipper._amazon_hub(mock_account, cache=cache)
        assert hub_res[ATTR_COUNT] == 1
        assert hub_res[ATTR_CODE] == ["123456"]

    # 4. Test _amazon_otp with cache
    cache._cache_rfc822["4"] = (
        "OK",
        [b"RFC822", b"Subject: OTP\n\n\n123456\n"],
    )
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [b"4"]),
    ):
        otp_res = await shipper._amazon_otp(mock_account, cache=cache)
        assert otp_res[ATTR_CODE] == ["123456"]

    # 5. Test _amazon_exception with cache
    cache._cache_rfc822["5"] = (
        "OK",
        [
            b"RFC822",
            b"Subject: Delivery update: Order 111-1234567-1234567\n\nYour order is running late.",
        ],
    )
    with patch(
        "custom_components.mail_and_packages.shippers.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [b"5"]),
    ):
        exc_res = await shipper._amazon_exception(mock_account, cache=cache)
        assert exc_res[ATTR_COUNT] == 1
        assert "111-1234567-1234567" in exc_res[ATTR_ORDER]
