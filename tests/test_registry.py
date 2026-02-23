"""Tests for the PackageRegistry module."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.registry import (
    STATUS_RANK,
    PackageRegistry,
)


@pytest.fixture
def mock_store():
    """Mock the HA Store."""
    with patch("custom_components.mail_and_packages.registry.Store") as mock_store_cls:
        store_instance = MagicMock()
        store_instance.async_load = AsyncMock(return_value=None)
        store_instance.async_save = AsyncMock()
        store_instance.async_remove = AsyncMock()
        mock_store_cls.return_value = store_instance
        yield store_instance


@pytest.fixture
def hass():
    """Mock hass object."""
    return MagicMock()


@pytest.fixture
def registry(hass, mock_store):
    """Create a PackageRegistry instance with mocked store."""
    return PackageRegistry(hass, "test_entry_id")


@pytest.mark.asyncio
async def test_load_empty(registry, mock_store):
    """Test loading an empty registry."""
    await registry.async_load()
    assert registry.packages == {}
    assert registry.get_active_packages() == {}


@pytest.mark.asyncio
async def test_load_existing_data(registry, mock_store):
    """Test loading existing data from store."""
    mock_store.async_load.return_value = {
        "packages": {
            "1Z123": {
                "carrier": "ups",
                "status": "in_transit",
                "first_seen": "2026-02-20T10:00:00+00:00",
                "last_updated": "2026-02-20T10:00:00+00:00",
            }
        },
        "processed_uids": {"123": "2026-02-20T10:00:00+00:00"},
    }
    await registry.async_load()
    assert "1Z123" in registry.packages
    assert registry.packages["1Z123"]["carrier"] == "ups"


@pytest.mark.asyncio
async def test_register_new_package(registry, mock_store):
    """Test registering a new package."""
    await registry.async_load()
    result = registry.register_package(
        tracking_number="1Z999AA10123456784",
        carrier="ups",
        status="detected",
        source="universal_scan",
        source_from="orders@store.com",
        description="Your order has shipped",
    )
    assert result is True
    assert "1Z999AA10123456784" in registry.packages
    pkg = registry.packages["1Z999AA10123456784"]
    assert pkg["carrier"] == "ups"
    assert pkg["status"] == "detected"
    assert pkg["source"] == "universal_scan"
    assert pkg["source_from"] == "orders@store.com"
    assert pkg["carrier_confirmed"] is False


@pytest.mark.asyncio
async def test_forward_status_transition(registry, mock_store):
    """Test that status can only advance forward."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "detected")
    assert registry.packages["1Z123"]["status"] == "detected"

    # Forward transition works
    result = registry.register_package("1Z123", "ups", "in_transit")
    assert result is True
    assert registry.packages["1Z123"]["status"] == "in_transit"

    # Another forward transition
    result = registry.register_package("1Z123", "ups", "delivered")
    assert result is True
    assert registry.packages["1Z123"]["status"] == "delivered"


@pytest.mark.asyncio
async def test_backward_status_rejected(registry, mock_store):
    """Test that backward status transitions are rejected."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "delivered")

    # Backward transition rejected
    result = registry.register_package("1Z123", "ups", "in_transit")
    assert result is False
    assert registry.packages["1Z123"]["status"] == "delivered"


@pytest.mark.asyncio
async def test_same_status_rejected(registry, mock_store):
    """Test that same-status re-registration is rejected."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")

    result = registry.register_package("1Z123", "ups", "in_transit")
    assert result is False


@pytest.mark.asyncio
async def test_carrier_confirmed_on_carrier_email(registry, mock_store):
    """Test carrier_confirmed is set when source is carrier_email."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "detected", source="universal_scan")
    assert registry.packages["1Z123"]["carrier_confirmed"] is False

    # Carrier email confirms it
    registry.register_package("1Z123", "ups", "in_transit", source="carrier_email")
    assert registry.packages["1Z123"]["carrier_confirmed"] is True


@pytest.mark.asyncio
async def test_carrier_confirmed_without_status_advance(registry, mock_store):
    """Test carrier_confirmed is set even when status doesn't advance."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit", source="universal_scan")
    assert registry.packages["1Z123"]["carrier_confirmed"] is False

    # Same status but from carrier email - should still update carrier_confirmed
    result = registry.register_package(
        "1Z123", "ups", "in_transit", source="carrier_email"
    )
    assert result is True
    assert registry.packages["1Z123"]["carrier_confirmed"] is True


@pytest.mark.asyncio
async def test_cleared_package_not_re_added(registry, mock_store):
    """Test that cleared packages are not re-added."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "detected")
    registry.clear_package("1Z123")

    # Try to register again - should be rejected
    result = registry.register_package("1Z123", "ups", "detected")
    assert result is False
    assert registry.packages["1Z123"]["status"] == "cleared"


@pytest.mark.asyncio
async def test_clear_package(registry, mock_store):
    """Test clearing a package."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")

    result = registry.clear_package("1Z123")
    assert result is True
    assert registry.packages["1Z123"]["status"] == "cleared"

    # Clearing again returns False
    result = registry.clear_package("1Z123")
    assert result is False


@pytest.mark.asyncio
async def test_clear_nonexistent_package(registry, mock_store):
    """Test clearing a package that doesn't exist."""
    await registry.async_load()
    result = registry.clear_package("NONEXISTENT")
    assert result is False


@pytest.mark.asyncio
async def test_clear_all_delivered(registry, mock_store):
    """Test clearing all delivered packages."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "delivered")
    registry.register_package("PKG2", "fedex", "delivered")
    registry.register_package("PKG3", "usps", "in_transit")

    count = registry.clear_all_delivered()
    assert count == 2
    assert registry.packages["PKG1"]["status"] == "cleared"
    assert registry.packages["PKG2"]["status"] == "cleared"
    assert registry.packages["PKG3"]["status"] == "in_transit"


@pytest.mark.asyncio
async def test_mark_delivered(registry, mock_store):
    """Test manually marking a package as delivered."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")

    result = registry.mark_delivered("1Z123")
    assert result is True
    assert registry.packages["1Z123"]["status"] == "delivered"


@pytest.mark.asyncio
async def test_mark_delivered_already_delivered(registry, mock_store):
    """Test marking an already delivered package."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "delivered")

    result = registry.mark_delivered("1Z123")
    assert result is False


@pytest.mark.asyncio
async def test_mark_delivered_nonexistent(registry, mock_store):
    """Test marking a nonexistent package."""
    await registry.async_load()
    result = registry.mark_delivered("NONEXISTENT")
    assert result is False


@pytest.mark.asyncio
async def test_add_package_new(registry, mock_store):
    """Test manually adding a new package."""
    await registry.async_load()
    result = registry.add_package("1Z123", "ups")
    assert result is True
    assert registry.packages["1Z123"]["source"] == "manual"
    assert registry.packages["1Z123"]["status"] == "detected"


@pytest.mark.asyncio
async def test_add_package_already_tracked(registry, mock_store):
    """Test adding a package that's already tracked."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")

    result = registry.add_package("1Z123", "ups")
    assert result is False


@pytest.mark.asyncio
async def test_add_package_re_add_cleared(registry, mock_store):
    """Test re-adding a previously cleared package."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "delivered")
    registry.clear_package("1Z123")

    result = registry.add_package("1Z123", "ups")
    assert result is True
    assert registry.packages["1Z123"]["status"] == "detected"
    assert registry.packages["1Z123"]["source"] == "manual"


@pytest.mark.asyncio
async def test_exception_flag(registry, mock_store):
    """Test setting and clearing exception flag."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")

    result = registry.set_exception("1Z123", True)
    assert result is True
    assert registry.packages["1Z123"]["exception"] is True

    # Clear exception
    result = registry.set_exception("1Z123", False)
    assert result is True
    assert registry.packages["1Z123"]["exception"] is False


@pytest.mark.asyncio
async def test_exception_cleared_on_forward_progress(registry, mock_store):
    """Test that exception flag is cleared when status advances."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")
    registry.set_exception("1Z123", True)
    assert registry.packages["1Z123"]["exception"] is True

    # Forward progress clears exception
    registry.register_package("1Z123", "ups", "delivered")
    assert registry.packages["1Z123"]["exception"] is False


@pytest.mark.asyncio
async def test_exception_on_cleared_package(registry, mock_store):
    """Test setting exception on cleared package."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "delivered")
    registry.clear_package("1Z123")

    result = registry.set_exception("1Z123", True)
    assert result is False


@pytest.mark.asyncio
async def test_get_active_packages(registry, mock_store):
    """Test getting active (non-cleared) packages."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "in_transit")
    registry.register_package("PKG2", "fedex", "delivered")
    registry.register_package("PKG3", "usps", "detected")
    registry.register_package("PKG4", "dhl", "in_transit")
    registry.clear_package("PKG4")

    active = registry.get_active_packages()
    assert len(active) == 3
    assert "PKG1" in active
    assert "PKG2" in active
    assert "PKG3" in active
    assert "PKG4" not in active


@pytest.mark.asyncio
async def test_get_by_status(registry, mock_store):
    """Test filtering packages by status."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "in_transit")
    registry.register_package("PKG2", "fedex", "delivered")
    registry.register_package("PKG3", "usps", "in_transit")

    in_transit = registry.get_by_status("in_transit")
    assert len(in_transit) == 2
    assert "PKG1" in in_transit
    assert "PKG3" in in_transit


@pytest.mark.asyncio
async def test_get_counts(registry, mock_store):
    """Test getting summary counts."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "detected")
    registry.register_package("PKG2", "fedex", "in_transit")
    registry.register_package("PKG3", "usps", "out_for_delivery")
    registry.register_package("PKG4", "dhl", "delivered")
    registry.register_package("PKG5", "ups", "delivered")
    registry.clear_package("PKG5")

    counts = registry.get_counts()
    assert counts["tracked"] == 4
    assert counts["in_transit"] == 3  # detected + in_transit + out_for_delivery
    assert counts["delivered"] == 1  # only PKG4 (PKG5 is cleared)


@pytest.mark.asyncio
async def test_get_packages_list(registry, mock_store):
    """Test getting packages as a list of dicts."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "in_transit", source="carrier_email")
    registry.register_package("PKG2", "fedex", "delivered")

    result = registry.get_packages_list()
    assert len(result) == 2
    assert result[0]["tracking_number"] == "PKG1"
    assert result[0]["carrier"] == "ups"

    # Filter by status
    in_transit = registry.get_packages_list("in_transit")
    assert len(in_transit) == 1
    assert in_transit[0]["tracking_number"] == "PKG1"

    delivered = registry.get_packages_list("delivered")
    assert len(delivered) == 1
    assert delivered[0]["tracking_number"] == "PKG2"


@pytest.mark.asyncio
async def test_get_packages_list_excludes_cleared(registry, mock_store):
    """Test that cleared packages are excluded from the list."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "in_transit")
    registry.register_package("PKG2", "fedex", "delivered")
    registry.clear_package("PKG2")

    result = registry.get_packages_list()
    assert len(result) == 1
    assert result[0]["tracking_number"] == "PKG1"


@pytest.mark.asyncio
async def test_auto_expire_delivered(registry, mock_store):
    """Test auto-expiry of delivered packages."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "delivered")

    # Set last_updated to 5 days ago
    old_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    registry.packages["PKG1"]["last_updated"] = old_time

    removed = registry.auto_expire(delivered_days=3)
    assert removed == 1
    assert "PKG1" not in registry.packages


@pytest.mark.asyncio
async def test_auto_expire_detected_unconfirmed(registry, mock_store):
    """Test auto-expiry of detected packages that were never confirmed."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "detected")

    # Set last_updated to 15 days ago
    old_time = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    registry.packages["PKG1"]["last_updated"] = old_time

    removed = registry.auto_expire(detected_days=14)
    assert removed == 1
    assert "PKG1" not in registry.packages


@pytest.mark.asyncio
async def test_auto_expire_detected_confirmed_not_expired(registry, mock_store):
    """Test that confirmed detected packages are not expired."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "detected", source="carrier_email")

    # Set last_updated to 15 days ago
    old_time = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    registry.packages["PKG1"]["last_updated"] = old_time

    removed = registry.auto_expire(detected_days=14)
    assert removed == 0
    assert "PKG1" in registry.packages


@pytest.mark.asyncio
async def test_auto_expire_cleared(registry, mock_store):
    """Test auto-expiry of cleared packages."""
    await registry.async_load()
    registry.register_package("PKG1", "ups", "delivered")
    registry.clear_package("PKG1")

    old_time = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    registry.packages["PKG1"]["last_updated"] = old_time

    removed = registry.auto_expire(cleared_days=30)
    assert removed == 1
    assert "PKG1" not in registry.packages


@pytest.mark.asyncio
async def test_processed_uids(registry, mock_store):
    """Test tracking processed email UIDs."""
    await registry.async_load()

    assert not registry.is_uid_processed("123")
    registry.mark_uid_processed("123")
    assert registry.is_uid_processed("123")


@pytest.mark.asyncio
async def test_expire_processed_uids(registry, mock_store):
    """Test expiring old processed UIDs."""
    await registry.async_load()
    registry.mark_uid_processed("recent")

    # Add an old UID
    old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    registry._processed_uids["old"] = old_time

    registry.expire_processed_uids(max_age_days=7)

    assert registry.is_uid_processed("recent")
    assert not registry.is_uid_processed("old")


@pytest.mark.asyncio
async def test_async_save(registry, mock_store):
    """Test that save persists data."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")
    await registry.async_save()

    mock_store.async_save.assert_called_once()
    saved_data = mock_store.async_save.call_args[0][0]
    assert "1Z123" in saved_data["packages"]


@pytest.mark.asyncio
async def test_async_remove(registry, mock_store):
    """Test removing the storage file."""
    await registry.async_remove()
    mock_store.async_remove.assert_called_once()


@pytest.mark.asyncio
async def test_status_rank_ordering():
    """Test that STATUS_RANK has correct ordering."""
    assert STATUS_RANK["detected"] < STATUS_RANK["in_transit"]
    assert STATUS_RANK["in_transit"] < STATUS_RANK["out_for_delivery"]
    assert STATUS_RANK["out_for_delivery"] < STATUS_RANK["delivered"]
    assert STATUS_RANK["delivered"] < STATUS_RANK["cleared"]


@pytest.mark.asyncio
async def test_mark_delivered_clears_exception(registry, mock_store):
    """Test that mark_delivered clears the exception flag."""
    await registry.async_load()
    registry.register_package("1Z123", "ups", "in_transit")
    registry.set_exception("1Z123", True)

    registry.mark_delivered("1Z123")
    assert registry.packages["1Z123"]["exception"] is False
