"""Tests for IMAP timeout resilience.

Verifies that sensors retain their last known values when the IMAP
server times out, instead of all going unavailable.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.mail_and_packages import MailDataUpdateCoordinator


def _make_coordinator(hass_mock, timeout=30):
    """Create a coordinator with a mocked hass instance."""
    config = {
        "host": "imap.test.email",
        "port": 993,
        "username": "test@test.com",
        "password": "password",
        "folder": '"INBOX"',
        "scan_interval": 5,
        "imap_timeout": timeout,
    }
    return MailDataUpdateCoordinator(
        hass_mock, "imap.test.email", timeout, 5, config
    )


async def test_timeout_returns_previous_data(hass, mock_copy_overlays):
    """Test that timeout returns previous data instead of raising."""
    previous_data = {"usps_delivered": 2, "ups_delivering": 1}

    coordinator = _make_coordinator(hass)
    coordinator.data = previous_data

    with patch(
        "custom_components.mail_and_packages.process_emails",
        side_effect=asyncio.TimeoutError,
    ):
        result = await coordinator._async_update_data()

    assert result == previous_data
    assert result["usps_delivered"] == 2
    assert result["ups_delivering"] == 1


async def test_timeout_raises_when_no_previous_data(hass, mock_copy_overlays):
    """Test that timeout raises UpdateFailed when there is no prior data."""
    coordinator = _make_coordinator(hass)
    coordinator.data = None

    with patch(
        "custom_components.mail_and_packages.process_emails",
        side_effect=asyncio.TimeoutError,
    ):
        with pytest.raises(UpdateFailed, match="Timeout communicating"):
            await coordinator._async_update_data()


async def test_non_timeout_error_still_raises(hass, mock_copy_overlays):
    """Test that non-timeout errors still raise UpdateFailed."""
    coordinator = _make_coordinator(hass)
    coordinator.data = {"usps_delivered": 2}

    with patch(
        "custom_components.mail_and_packages.process_emails",
        side_effect=ConnectionError("Connection refused"),
    ):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
