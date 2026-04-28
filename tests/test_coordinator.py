"""Tests for MailDataUpdateCoordinator sensor processing."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.mail_and_packages.coordinator import MailDataUpdateCoordinator
from custom_components.mail_and_packages.utils.imap import InvalidAuth
from tests.const import FAKE_CONFIG_DATA


@pytest.mark.asyncio
async def test_process_emails_batch_success(hass):
    """Test process_emails processes sensors in batch successfully."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = {
        "test_sensor": 5,
        "test_attribute": "value",
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert data["test_sensor"] == 5
    assert data["test_attribute"] == "value"


@pytest.mark.asyncio
async def test_process_emails_batch_exception(hass, caplog):
    """Test process_emails handles exception during batch processing."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.side_effect = Exception("Test error")

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert "Error processing shipper test_shipper: Test error" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_invalid_return(hass):
    """Test process_emails gracefully handles non-dict return."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = "invalid data"

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    # Should just not crash, missing data ok
    assert "test_sensor" not in data


@pytest.mark.asyncio
async def test_get_imap_connection_invalid_auth(hass):
    """Test _get_imap_connection handles InvalidAuth."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            side_effect=InvalidAuth("Invalid credentials"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._get_imap_connection(FAKE_CONFIG_DATA)


@pytest.mark.asyncio
async def test_get_imap_connection_exception(hass):
    """Test _get_imap_connection handles generic Exception."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            side_effect=Exception("Connection refused"),
        ),
        pytest.raises(UpdateFailed, match="Login failed"),
    ):
        await coordinator._get_imap_connection(FAKE_CONFIG_DATA)


@pytest.mark.asyncio
async def test_process_emails_no_shipper(hass):
    """Test process_emails skips if no shipper is found."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=None,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    # Dictionary returned with nothing added since no shipper available
    assert "test_sensor" not in data


@pytest.mark.asyncio
async def test_aggregate_package_counts(hass):
    """Test that package counts are correctly aggregated."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Mock data to be aggregated
    test_data = {
        "zpackages_transit": 0,
        "zpackages_delivered": 0,
        "usps_delivering": 1,
        "usps_delivered": 1,
        "ups_delivering": 2,
        "ups_delivered": 0,
        "fedex_packages": 3,
        "fedex_delivered": 2,
        "amazon_packages": 5,
        "amazon_delivered": 1,
        "amazon_exception": 1,
        "dhl_exception": 1,
        "unknown_sensor": 99,
        "amazon_delivered_by_others": 10,  # Should be excluded from zpackages_delivered
        "usps_mail_delivered": 3,  # Should be excluded — these are mail pieces, not packages
    }

    coordinator._aggregate_package_counts(test_data)

    # Expected Transit:
    # usps_delivering (1) + ups_delivering (2) + fedex_packages (3) + amazon_packages (5)
    # + amazon_exception (1) + dhl_exception (1)
    # = 1 + 2 + 3 + 5 + 1 + 1 = 13
    assert test_data["zpackages_transit"] == 13

    # Expected Delivered:
    # usps_delivered (1) + fedex_delivered (2) + amazon_delivered (1)
    # ups_delivered (0) is ignored as it is <= 0
    # amazon_delivered_by_others (10) and usps_mail_delivered (3) are excluded
    # = 1 + 2 + 1 = 4
    assert test_data["zpackages_delivered"] == 4


@pytest.mark.asyncio
async def test_aggregate_package_counts_no_resource(hass):
    """Test that aggregation doesn't add sensors not in initialize_data."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    test_data = {
        "usps_delivering": 1,
    }

    coordinator._aggregate_package_counts(test_data)

    assert "zpackages_transit" not in test_data
    assert "zpackages_delivered" not in test_data


@pytest.mark.asyncio
async def test_get_imap_connection_selectfolder_exception(hass):
    """Test _get_imap_connection handles exception from selectfolder (lines 229-231)."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            side_effect=Exception("Folder error"),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.logout",
        ) as mock_logout,
        pytest.raises(UpdateFailed, match="Folder selection failed"),
    ):
        await coordinator._get_imap_connection(FAKE_CONFIG_DATA)

    mock_logout.assert_called_once_with(mock_account)


# ---------------------------------------------------------------------------
# Tracking persistence tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tracking_adds_new_delivering(hass):
    """New delivering tracking numbers are added with today's date."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    today = "2026-04-22"
    coordinator._update_tracking_for_prefix("ups", ["1Z123", "1Z456"], [], today, 14)

    assert coordinator._in_transit_tracking["ups"] == {
        "1Z123": today,
        "1Z456": today,
    }


@pytest.mark.asyncio
async def test_update_tracking_removes_delivered(hass):
    """Delivering tracking numbers that appear in delivered are removed."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["ups"] = {
        "1Z123": "2026-04-20",
        "1Z456": "2026-04-21",
    }
    coordinator._update_tracking_for_prefix("ups", [], ["1Z123"], "2026-04-22", 14)

    assert "1Z123" not in coordinator._in_transit_tracking["ups"]
    assert "1Z456" in coordinator._in_transit_tracking["ups"]


@pytest.mark.asyncio
async def test_update_tracking_expires_old_entries(hass):
    """Tracking numbers older than TTL are expired."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["ups"] = {
        "1ZOLD": "2026-04-01",  # 21 days old — beyond 14-day TTL
        "1ZNEW": "2026-04-20",  # 2 days old — within TTL
    }
    coordinator._update_tracking_for_prefix("ups", [], [], "2026-04-22", 14)

    assert "1ZOLD" not in coordinator._in_transit_tracking["ups"]
    assert "1ZNEW" in coordinator._in_transit_tracking["ups"]


@pytest.mark.asyncio
async def test_update_tracking_no_duplicate_add(hass):
    """Already-known tracking numbers keep their original first-seen date."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    original_date = "2026-04-20"
    coordinator._in_transit_tracking["ups"] = {"1Z123": original_date}
    coordinator._update_tracking_for_prefix("ups", ["1Z123"], [], "2026-04-22", 14)

    assert coordinator._in_transit_tracking["ups"]["1Z123"] == original_date


@pytest.mark.asyncio
async def test_apply_tracking_state_overrides_delivering(hass):
    """_apply_tracking_state replaces IMAP-reported count with persisted count."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Pre-populate two tracking numbers in transit
    coordinator._in_transit_tracking["ups"] = {
        "1Z111": "2026-04-20",
        "1Z222": "2026-04-21",
    }

    data = {"ups_delivering": 1, "ups_delivered": 0, "ups_packages": 1}
    tracking_details = {
        "ups_delivering": ["1Z333"],  # new one found today
        "ups_delivered": [],
    }
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    # 1Z111, 1Z222 carried over + 1Z333 newly added = 3
    assert data["ups_delivering"] == 3
    assert data["ups_packages"] == 3
    assert set(data["ups_tracking"]) == {"1Z111", "1Z222", "1Z333"}


@pytest.mark.asyncio
async def test_apply_tracking_state_removes_delivered(hass):
    """Packages marked delivered are removed from in-transit tracking."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["fedex"] = {
        "9261290": "2026-04-20",
        "9261999": "2026-04-21",
    }

    data = {"fedex_delivering": 2, "fedex_delivered": 1, "fedex_packages": 3}
    tracking_details = {
        "fedex_delivering": [],
        "fedex_delivered": ["9261290"],
    }
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    assert "9261290" not in coordinator._in_transit_tracking["fedex"]
    assert data["fedex_delivering"] == 1
    assert data["fedex_packages"] == 2  # 1 delivering + 1 delivered


@pytest.mark.asyncio
async def test_apply_tracking_state_no_tracking_details(hass):
    """With empty tracking_details, data is unchanged."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    data = {"ups_delivering": 2, "ups_delivered": 1}
    coordinator._apply_tracking_state(data, {}, "2026-04-22")

    assert data["ups_delivering"] == 2
    assert data["ups_delivered"] == 1


@pytest.mark.asyncio
async def test_process_emails_passes_since_date(hass):
    """process_emails passes since_date to shippers based on CONF_CUSTOM_DAYS."""
    config = {**FAKE_CONFIG_DATA, "custom_days": 3}
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = {}

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
        patch("custom_components.mail_and_packages.coordinator.datetime") as mock_dt,
    ):
        fixed_now = datetime.datetime(2026, 4, 22, 12, 0, 0)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.timedelta = datetime.timedelta
        mock_dt.date = datetime.date
        mock_dt.UTC = datetime.UTC
        await coordinator.process_emails(hass, config)

    call_kwargs = mock_shipper.process_batch.call_args
    since_date_passed = call_kwargs.kwargs.get("since_date")
    assert since_date_passed == "19-Apr-2026"


@pytest.mark.asyncio
async def test_process_emails_strips_tracking_details_from_output(hass):
    """_tracking_details key is consumed and not exposed in coordinator data."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = {
        "ups_delivering": 1,
        "_tracking_details": {"ups_delivering": ["1Z999"]},
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert "_tracking_details" not in data
