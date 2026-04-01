"""Tests for EmailCache."""

from unittest.mock import AsyncMock

import pytest

from custom_components.mail_and_packages.utils.cache import EmailCache


@pytest.mark.asyncio
async def test_cache_fetch_rfc822():
    """Test fetching and caching RFC822."""
    account = AsyncMock()
    cache = EmailCache(account)

    # Mock email_fetch
    with pytest.MonkeyPatch.context() as mp:
        mock_fetch = AsyncMock(return_value=("OK", [b"Email data"]))
        mp.setattr(
            "custom_components.mail_and_packages.utils.cache.email_fetch", mock_fetch
        )

        # First fetch
        res = await cache.fetch("1", "(RFC822)")
        assert res == ("OK", [b"Email data"])
        assert mock_fetch.call_count == 1
        assert cache._cache_rfc822["1"] == ("OK", [b"Email data"])

        # Second fetch (cached)
        res = await cache.fetch("1", "(RFC822)")
        assert res == ("OK", [b"Email data"])
        assert mock_fetch.call_count == 1

        # Body[] variant
        res = await cache.fetch("1", "BODY[]")
        assert res == ("OK", [b"Email data"])
        assert mock_fetch.call_count == 1


@pytest.mark.asyncio
async def test_cache_fetch_headers():
    """Test fetching and caching HEADERS."""
    account = AsyncMock()
    cache = EmailCache(account)

    with pytest.MonkeyPatch.context() as mp:
        mock_headers = AsyncMock(return_value=("OK", [b"Header data"]))
        mp.setattr(
            "custom_components.mail_and_packages.utils.cache.email_fetch_headers",
            mock_headers,
        )

        # First fetch
        res = await cache.fetch("1", "(HEADER)")
        assert res == ("OK", [b"Header data"])
        assert mock_headers.call_count == 1
        assert cache._cache_headers["1"] == ("OK", [b"Header data"])

        # Second fetch (cached)
        res = await cache.fetch("1", "(HEADER)")
        assert res == ("OK", [b"Header data"])
        assert mock_headers.call_count == 1

        # Fallback to RFC822
        cache._cache_rfc822["2"] = ("OK", [b"Full data"])
        res = await cache.fetch("2", "(HEADER)")
        assert res == ("OK", [b"Full data"])
        assert mock_headers.call_count == 1


@pytest.mark.asyncio
async def test_cache_fetch_text():
    """Test fetching and caching TEXT."""
    account = AsyncMock()
    cache = EmailCache(account)

    with pytest.MonkeyPatch.context() as mp:
        mock_text = AsyncMock(return_value=("OK", [b"Text data"]))
        mp.setattr(
            "custom_components.mail_and_packages.utils.cache.email_fetch_text",
            mock_text,
        )

        # First fetch
        res = await cache.fetch("1", "(TEXT)")
        assert res == ("OK", [b"Text data"])
        assert mock_text.call_count == 1
        assert cache._cache_text["1"] == ("OK", [b"Text data"])

        # Second fetch (cached)
        res = await cache.fetch("1", "(BODY[1])")
        assert res == ("OK", [b"Text data"])
        assert mock_text.call_count == 1

        # Fallback to RFC822
        cache._cache_rfc822["2"] = ("OK", [b"Full data"])
        res = await cache.fetch("2", "(TEXT)")
        assert res == ("OK", [b"Full data"])
        assert mock_text.call_count == 1


@pytest.mark.asyncio
async def test_cache_fetch_unknown():
    """Test fetching unknown parts."""
    account = AsyncMock()
    cache = EmailCache(account)

    with pytest.MonkeyPatch.context() as mp:
        mock_fetch = AsyncMock(return_value=("OK", [b"Unknown part"]))
        mp.setattr(
            "custom_components.mail_and_packages.utils.cache.email_fetch", mock_fetch
        )

        res = await cache.fetch("1", "(UNKNOWN)")
        assert res == ("OK", [b"Unknown part"])
        assert mock_fetch.call_count == 1


@pytest.mark.asyncio
async def test_cache_fetch_batch():
    """Test fetch_batch."""
    account = AsyncMock()
    cache = EmailCache(account)

    with pytest.MonkeyPatch.context() as mp:
        mock_batch = AsyncMock(return_value=("OK", [b"Batch data"]))
        mp.setattr(
            "custom_components.mail_and_packages.utils.cache.email_fetch_batch",
            mock_batch,
        )

        # Simple pass-through for now
        res = await cache.fetch_batch(["1", "2"], "(RFC822)")
        assert res == ("OK", [b"Batch data"])
        assert mock_batch.call_count == 1

        # Variant checks
        await cache.fetch_batch(["3"], "(HEADER)")
        await cache.fetch_batch(["4"], "(TEXT)")
        await cache.fetch_batch(["5"], "(UNKNOWN)")


def test_cache_clear():
    """Test clearing the cache."""
    account = AsyncMock()
    cache = EmailCache(account)
    cache._cache_rfc822["1"] = ("OK", [b"data"])
    cache._cache_text["1"] = ("OK", [b"data"])
    cache._cache_headers["1"] = ("OK", [b"data"])

    cache.clear()
    assert not cache._cache_rfc822
    assert not cache._cache_text
    assert not cache._cache_headers
