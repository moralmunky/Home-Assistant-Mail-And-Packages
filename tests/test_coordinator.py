"""Tests for MailDataUpdateCoordinator sensor processing."""

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
    # amazon_delivered_by_others (10) is excluded
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
