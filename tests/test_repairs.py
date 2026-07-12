"""Test the Repairs platform and flow for Mail and Packages."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir

from custom_components.mail_and_packages.binary_sensor import PackagesBinarySensor
from custom_components.mail_and_packages.const import (
    BINARY_SENSORS,
    DOMAIN,
    IMAGE_SENSORS,
    SENSOR_TYPES,
)
from custom_components.mail_and_packages.coordinator import MailDataUpdateCoordinator
from custom_components.mail_and_packages.repairs import (
    AuthRepairFlow,
    async_create_fix_flow,
)
from custom_components.mail_and_packages.sensor import ImagePathSensors, PackagesSensor
from custom_components.mail_and_packages.utils.imap import InvalidAuth


@pytest.mark.asyncio
async def test_auth_repair_flow(hass: HomeAssistant):
    """Test the auth repair flow."""
    # Test async_create_fix_flow
    flow = await async_create_fix_flow(hass, "auth_failed", {"entry_id": "test_entry"})
    assert isinstance(flow, AuthRepairFlow)
    assert flow.entry_id == "test_entry"

    # Test unknown issue raises ValueError
    with pytest.raises(ValueError, match="Unknown issue unknown"):
        await async_create_fix_flow(hass, "unknown", {})

    # Set up flow on hass
    flow.hass = hass

    # Test step_init
    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # Test step_confirm show form
    result = await flow.async_step_confirm()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # Test step_confirm submit (with config entry)
    mock_entry = MagicMock()
    mock_entry.async_start_reauth = MagicMock()

    with patch.object(
        hass.config_entries, "async_get_entry", return_value=mock_entry
    ) as mock_get_entry:
        result = await flow.async_step_confirm(user_input={})
        assert result["type"] == "create_entry"
        mock_get_entry.assert_called_once_with("test_entry")
        mock_entry.async_start_reauth.assert_called_once_with(hass)

    # Test step_confirm submit (without entry_id, fall back to first entry found)
    flow_no_id = AuthRepairFlow(entry_id=None)
    flow_no_id.hass = hass

    mock_entry2 = MagicMock()
    mock_entry2.async_start_reauth = MagicMock()

    with (
        patch.object(hass.config_entries, "async_entries", return_value=[mock_entry2]),
        patch.object(hass.config_entries, "async_get_entry", return_value=None),
    ):
        result = await flow_no_id.async_step_confirm(user_input={})
        assert result["type"] == "create_entry"
        mock_entry2.async_start_reauth.assert_called_once_with(hass)


@pytest.mark.asyncio
async def test_auth_failure_creates_repairs_issue(hass: HomeAssistant):
    """Test that a repairs issue is created on authentication failure."""
    coordinator = MailDataUpdateCoordinator(hass, {"scan_interval": 5}, None)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            side_effect=InvalidAuth("Auth failed"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._get_imap_connection({})

    # Check that the repairs issue is created
    issue_registry = ir.async_get(hass)
    assert (DOMAIN, "auth_failed") in issue_registry.issues

    # Test that the issue is deleted on successful login
    with patch(
        "custom_components.mail_and_packages.coordinator.login",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_account = MagicMock()
        mock_account.select = AsyncMock()
        mock_login.return_value = mock_account
        await coordinator._get_imap_connection({})

    assert (DOMAIN, "auth_failed") not in issue_registry.issues


async def test_sensors_unpopulated_coordinator(hass: HomeAssistant):
    """Test sensors when coordinator data is None."""

    mock_coordinator = MagicMock()
    mock_coordinator.data = None

    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"

    # Test PackagesSensor
    sensor = PackagesSensor(mock_entry, SENSOR_TYPES["usps_mail"], mock_coordinator)
    assert sensor.native_value is None

    # Test ImagePathSensors
    image_sensor = ImagePathSensors(
        hass, mock_entry, IMAGE_SENSORS["usps_mail_image_system_path"], mock_coordinator
    )
    assert image_sensor.native_value is None

    # Test PackagesBinarySensor
    binary_sensor = PackagesBinarySensor(
        BINARY_SENSORS["post_de_update"], mock_coordinator, mock_entry
    )
    assert binary_sensor.is_on is False
