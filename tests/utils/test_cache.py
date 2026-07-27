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

        # Seed entries
        cache._persistent_store = {
            "usps_yesterday": {
                "fetched_at": yesterday.isoformat(),
                "shipper": "usps",
                "data": ["OK", [b"usps mail"]],
            },
            "amazon_old": {
                "fetched_at": four_days_ago.isoformat(),
                "shipper": "amazon",
                "data": ["OK", [b"amazon old"]],
            },
            "amazon_recent": {
                "fetched_at": yesterday.isoformat(),
                "shipper": "amazon",
                "data": ["OK", [b"amazon recent"]],
            },
        }

        # Non-amazon (usps_yesterday) expires at midnight, amazon_old exceeds custom_days (3)
        await cache.async_purge_expired(custom_days=3)

        assert "usps_yesterday" not in cache._persistent_store
        assert "amazon_old" not in cache._persistent_store
        assert "amazon_recent" in cache._persistent_store
