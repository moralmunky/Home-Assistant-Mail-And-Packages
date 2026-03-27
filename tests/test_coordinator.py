"""Tests for MailDataUpdateCoordinator sensor processing."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.mail_and_packages.coordinator import MailDataUpdateCoordinator
from tests.const import FAKE_CONFIG_DATA

@pytest.mark.asyncio
async def test_process_sensor_dict_update(hass):
    """Test _process_sensor with a nested dictionary return."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.process.return_value = {"test_sensor": {"custom_attr": "custom_value"}}

    data = {}
    with patch(
        "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
        return_value=mock_shipper,
    ):
        await coordinator._process_sensor(
            None, "today", "test_sensor", data, hass, FAKE_CONFIG_DATA
        )

    assert data["custom_attr"] == "custom_value"


@pytest.mark.asyncio
async def test_process_sensor_exception(hass, caplog):
    """Test _process_sensor with an exception during processing."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.process.side_effect = Exception("Test error")

    data = {}
    with patch(
        "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
        return_value=mock_shipper,
    ):
        await coordinator._process_sensor(
            None, "today", "test_sensor", data, hass, FAKE_CONFIG_DATA
        )

    assert "Error processing sensor test_sensor: Test error" in caplog.text


@pytest.mark.asyncio
async def test_coordinator_login_error(hass, caplog):
    """Test coordinator IMAP login error (Lines 166-168)."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            side_effect=Exception("Login failed"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert "Error logging into IMAP: Login failed" in caplog.text
