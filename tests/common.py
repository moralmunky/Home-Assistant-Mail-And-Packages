"""Helpers for tests."""
from custom_components.mail_and_packages.const import DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.async_mock import Mock, patch
from tests.const import (
    FAKE_CONFIG_DATA,
    FAKE_UPDATE_DATA,
)


async def setup_mnp(hass, fixture=None):
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    with patch(
        "custom_components.mail_and_packages.sensor.EmailData.update"
    ) as mock_update:
        mock_update.return_value = Mock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "mail_and_packages" in hass.config.components

    email_data = mock_update(return_value=FAKE_UPDATE_DATA)

    return email_data
