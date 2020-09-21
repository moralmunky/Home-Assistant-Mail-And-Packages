""" Test Mail and Packages Sensor """
from homeassistant import config_entries
from homeassistant.components import sensor
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from tests.const import FAKE_UPDATE_DATA, FAKE_CONFIG_DATA
from custom_components.mail_and_packages.const import DOMAIN
from unittest.mock import Mock


async def test_sensor(hass, mock_update):

    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "mail_and_packages" in hass.config.components

    state = hass.states.get("sensor.mail_updated")

    assert state
    assert state.state == "Sep-18-2020 06:29 PM"
