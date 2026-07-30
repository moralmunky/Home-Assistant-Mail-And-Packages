"""Tests for persistent EmailCache utility."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.utils.cache import EmailCache


@pytest.mark.asyncio
async def test_email_cache_persistent_store_and_purge(hass):
    """Test EmailCache persistence, load, save, and carrier expiration rules."""
    with patch(
        "custom_components.mail_and_packages.utils.cache.Store"
    ) as mock_store_cls:
        mock_store = AsyncMock()
        mock_store.async_load.return_value = {"entries": {}}
        mock_store_cls.return_value = mock_store

        cache = EmailCache(hass=hass)
        await cache.async_load()

        now = datetime.datetime.now(datetime.UTC)
        yesterday = now - datetime.timedelta(days=1)
        four_days_ago = now - datetime.timedelta(days=4)

        # Seed entries including malformed / invalid dates
        cache._persistent_store = {
            "usps_yesterday": {
                "fetched_at": yesterday.isoformat(),
                "shipper": "usps",
                "data": ["OK", ["usps mail"]],
            },
            "amazon_old": {
                "fetched_at": four_days_ago.isoformat(),
                "shipper": "amazon",
                "data": ["OK", ["amazon old"]],
            },
            "amazon_recent": {
                "fetched_at": yesterday.isoformat(),
                "shipper": "amazon",
                "data": ["OK", ["amazon recent"]],
            },
            "invalid_date": {
                "fetched_at": "invalid_iso_string",
                "shipper": "generic",
                "data": ["OK", ["invalid date"]],
            },
            "no_date": {
                "shipper": "generic",
                "data": ["OK", ["no date"]],
            },
        }

        # Purge expired entries
        await cache.async_purge_expired(custom_days=3)

        assert "usps_yesterday" not in cache._persistent_store
        assert "amazon_old" not in cache._persistent_store
        assert "invalid_date" not in cache._persistent_store
        assert "no_date" not in cache._persistent_store
        assert "amazon_recent" in cache._persistent_store


@pytest.mark.asyncio
async def test_email_cache_load_and_save_errors(caplog):
    """Test EmailCache OSError handling on load and save."""
    # Test when self._store is None
    cache_no_store = EmailCache()
    await cache_no_store.async_load()
    await cache_no_store.async_save()

    mock_store = AsyncMock()
    mock_store.async_load.side_effect = OSError("Load error")
    mock_store.async_save.side_effect = OSError("Save error")

    cache = EmailCache()
    cache._store = mock_store

    await cache.async_load()
    assert cache._persistent_store == {}
    assert "Failed to load email cache" in caplog.text

    await cache.async_save()
    assert "Failed to save email cache" in caplog.text


@pytest.mark.asyncio
async def test_email_cache_fetch_variations(hass):
    """Test EmailCache fetch branches, restored byte structures, and fallback behavior."""
    mock_account = AsyncMock()

    cache = EmailCache(account=mock_account, hass=hass)

    # 1. Test restoration from persistent store (tuples, bytes, lists, non-string items)
    cache._persistent_store = {
        "1:(RFC822)": {
            "fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "shipper": "generic",
            "data": ["OK", [["header", "body"], "plain_str", 123, None]],
        },
        "2:HEADER": {
            "fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "shipper": "generic",
            "data": ["OK", "non_list_response"],
        },
    }

    res_rfc822 = await cache.fetch("1", "(RFC822)")
    assert res_rfc822[0] == "OK"
    assert res_rfc822[1][0] == (b"header", b"body")
    assert res_rfc822[1][1] == b"plain_str"
    assert res_rfc822[1][2] == 123

    res_header_cached = await cache.fetch("2", "HEADER")
    assert res_header_cached == ("OK", "non_list_response")

    # 2. Test transient cache hits (RFC822, HEADER, TEXT)
    cache._cache_rfc822["3"] = ("OK", [b"rfc822 cached"])
    assert await cache.fetch("3", "(RFC822)") == ("OK", [b"rfc822 cached"])
    assert await cache.fetch("3", "HEADER") == ("OK", [b"rfc822 cached"])
    assert await cache.fetch("3", "TEXT") == ("OK", [b"rfc822 cached"])

    cache._cache_headers["4"] = ("OK", [b"header cached"])
    assert await cache.fetch("4", "HEADER") == ("OK", [b"header cached"])

    cache._cache_text["5"] = ("OK", [b"text cached"])
    assert await cache.fetch("5", "TEXT") == ("OK", [b"text cached"])

    # 3. Test IMAP fetch execution & persistent storage serialization
    with (
        patch(
            "custom_components.mail_and_packages.utils.cache.email_fetch",
            AsyncMock(return_value=("OK", [(b"header", b"body"), b"raw_bytes", 456])),
        ),
        patch(
            "custom_components.mail_and_packages.utils.cache.email_fetch_headers",
            AsyncMock(return_value=("OK", "string_resp")),
        ),
        patch(
            "custom_components.mail_and_packages.utils.cache.email_fetch_text",
            AsyncMock(return_value=("OK", [b"text_body"])),
        ),
    ):
        res_fetch = await cache.fetch("6", "(RFC822)")
        assert res_fetch[0] == "OK"
        assert "6:(RFC822)" in cache._persistent_store

        res_h_fetch = await cache.fetch("7", "HEADER")
        assert res_h_fetch[0] == "OK"
        assert "7:HEADER" in cache._persistent_store

        res_t_fetch = await cache.fetch("8", "TEXT")
        assert res_t_fetch[0] == "OK"
        assert "8:TEXT" in cache._persistent_store

        res_other = await cache.fetch("9", "OTHER_PARTS")
        assert res_other[0] == "OK"

    # 3b. Test IMAP fetch with bytearray response data
    with patch(
        "custom_components.mail_and_packages.utils.cache.email_fetch",
        AsyncMock(
            return_value=(
                "OK",
                [
                    (b"header", bytearray(b"bytearray_body")),
                    bytearray(b"raw_bytearray"),
                ],
            )
        ),
    ):
        res_ba_fetch = await cache.fetch("12", "(RFC822)")
        assert res_ba_fetch[0] == "OK"
        assert "12:(RFC822)" in cache._persistent_store
        # Verify store entry contains JSON-serializable strings instead of bytearray
        stored_entry = cache._persistent_store["12:(RFC822)"]["data"]
        assert stored_entry[1][0] == ("header", "bytearray_body")
        assert stored_entry[1][1] == "raw_bytearray"

        # Verify restoration on re-fetch returns bytes
        res_ba_restore = await cache.fetch("12", "(RFC822)")
        assert res_ba_restore[0] == "OK"
        assert res_ba_restore[1][0] == (b"header", b"bytearray_body")
        assert res_ba_restore[1][1] == b"raw_bytearray"

    # 4. Test fetch_batch with active account
    with patch(
        "custom_components.mail_and_packages.utils.cache.email_fetch_batch",
        AsyncMock(return_value=("OK", [b"batch response"])),
    ):
        assert (await cache.fetch_batch(["11"], "(RFC822)")) == (
            "OK",
            [b"batch response"],
        )

    # 5. Test no active IMAP connection fallbacks
    cache.account = None
    assert (await cache.fetch("10", "(RFC822)")) == (
        "NO",
        ["No active IMAP connection"],
    )
    assert (await cache.fetch("10", "HEADER")) == ("NO", ["No active IMAP connection"])
    assert (await cache.fetch("10", "TEXT")) == ("NO", ["No active IMAP connection"])
    assert (await cache.fetch("10", "OTHER_PARTS")) == (
        "NO",
        ["No active IMAP connection"],
    )
    assert (await cache.fetch_batch(["10"], "(RFC822)")) == (
        "NO",
        ["No active IMAP connection"],
    )

    # 6. Test set_account and clear
    cache._cache_rfc822["test"] = ("OK", [])
    cache.set_account(mock_account)
    assert cache.account == mock_account
    assert len(cache._cache_rfc822) == 0

    cache._cache_text["test"] = ("OK", [])
    cache.clear()
    assert len(cache._cache_text) == 0
