"""Test the Mail and Packages diagnostics."""

from unittest.mock import patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from custom_components.mail_and_packages.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from tests.const import FAKE_CONFIG_DATA, FAKE_UPDATE_DATA, FAKE_UPDATE_DATA_REDACTED


@pytest.mark.asyncio
async def test_config_entry_diagnostics(hass):
    """Test the config entry level diagnostics data dump."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    result = await async_get_config_entry_diagnostics(hass, entry)

    assert isinstance(result, dict)
    assert result["config"]["data"][CONF_HOST] == "imap.test.email"
    assert result["config"]["data"][CONF_PORT] == 993
    assert result["config"]["data"][CONF_PASSWORD] == "**REDACTED**"
    assert result["config"]["data"][CONF_USERNAME] == "**REDACTED**"


@pytest.mark.asyncio
async def test_device_diagnostics(hass, mock_update):
    """Test the device level diagnostics data dump."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_device_diagnostics(hass, entry, None)

    assert result == FAKE_UPDATE_DATA_REDACTED
