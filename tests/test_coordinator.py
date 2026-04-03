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
