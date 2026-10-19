"""Amazon delivery dates use the same local day as other carrier sensors."""

import datetime as dt
import email
import os
import time
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.shippers.amazon import AmazonShipper
from custom_components.mail_and_packages.utils.cache import EmailCache

pytestmark = pytest.mark.skipif(
    not hasattr(time, "tzset"), reason="Host timezone tests require time.tzset"
)


@contextmanager
def host_timezone(zone):
    """Set and restore the process timezone used by get_today and astimezone."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = zone
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


@pytest.mark.asyncio
@pytest.mark.parametrize("use_cache", [False, True])
@pytest.mark.parametrize("body", ["", "Arriving today by 10 PM."])
@pytest.mark.parametrize(
    ("zone", "today", "headers", "expected"),
    [
        (
            "America/New_York",
            dt.date(2026, 10, 18),
            ("Mon, 19 Oct 2026 00:30:00 +0000", "Sun, 18 Oct 2026 20:30:00 -0400"),
            1,
        ),
        (
            "America/New_York",
            dt.date(2026, 10, 19),
            ("Mon, 19 Oct 2026 00:30:00 +0000", "Sun, 18 Oct 2026 20:30:00 -0400"),
            0,
        ),
        (
            "Asia/Tokyo",
            dt.date(2026, 10, 19),
            ("Sun, 18 Oct 2026 15:30:00 +0000", "Mon, 19 Oct 2026 00:30:00 +0900"),
            1,
        ),
        (
            "UTC",
            dt.date(2026, 10, 19),
            ("Mon, 19 Oct 2026 00:30:00 +0000", "Sun, 18 Oct 2026 20:30:00 -0400"),
            1,
        ),
        (
            "America/New_York",
            dt.date(2026, 10, 19),
            ("Mon, 19 Oct 2026 18:30:00 +0000", "Mon, 19 Oct 2026 14:30:00 -0400"),
            1,
        ),
    ],
)
async def test_amazon_delivering_equivalent_header_instants(
    hass, zone, today, headers, expected, body, use_cache
):
    """Changing only the Date header's timezone must not change the delivery count."""
    assert parsedate_to_datetime(headers[0]) == parsedate_to_datetime(headers[1])
    account = AsyncMock()
    counts = []
    with (
        host_timezone(zone),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.search.get_today",
            return_value=today,
        ),
        patch(
            "custom_components.mail_and_packages.utils.amazon.get_today",
            return_value=today,
        ),
        patch(
            "custom_components.mail_and_packages.utils.amazon.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.amazon.search.email_fetch",
            new_callable=AsyncMock,
        ) as fetch,
    ):
        for date_header in headers:
            raw = (
                "Subject: Out for delivery: Your order 123-4567890-1234567\r\n"
                f"Date: {date_header}\r\n"
                "Content-Type: text/plain; charset=utf-8\r\n\r\n"
                f"{body}"
            ).encode()
            response = ("OK", [raw])
            cache = EmailCache() if use_cache else None
            if cache is not None:
                cache.store("1", "(RFC822)", response)
            fetch.return_value = response
            shipper = AmazonShipper(hass, {})
            result = await shipper.process(
                account, "today", "amazon_delivering", cache=cache
            )
            counts.append(result["amazon_delivering"])
        assert fetch.await_count == (0 if use_cache else 2)
    assert counts == [expected, expected]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("not a valid date", None),
        ("Sun, 18 Oct 2026 20:30:00", dt.date(2026, 10, 18)),
    ],
)
async def test_amazon_email_date_fallbacks(hass, header, expected):
    """Missing, invalid and timezone-naive dates retain their existing behavior."""
    msg = email.message.Message()
    if header is not None:
        msg["Date"] = header
    with host_timezone("Asia/Tokyo"):
        assert await AmazonShipper(hass, {})._parse_email_date(msg) == expected
