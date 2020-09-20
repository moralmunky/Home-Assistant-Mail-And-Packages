""" Test Mail and Packages Sensor """
from custom_components.mail_and_packages import EmailData
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.async_mock import patch, PropertyMock
from tests.const import FAKE_UPDATE_DATA, FAKE_CONFIG_DATA
from custom_components.mail_and_packages.const import DOMAIN


async def test_sensor(hass):

    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch("custom_components.mail_and_packages.EmailData.update") as mock_update:

        e = EmailData(hass, FAKE_CONFIG_DATA)

        with patch.object(e, "_data", FAKE_UPDATE_DATA):
            assert "mail_and_packages" in hass.config.components

            state = hass.states.get("sensor.mail_updated")

            assert state
            assert state.state == "Sep-18-2020 06:29 PM"
