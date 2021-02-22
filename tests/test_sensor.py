""" Test Mail and Packages Sensor """
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from tests.const import FAKE_CONFIG_DATA_NO_RND


async def test_sensor(hass, mock_update):

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_NO_RND,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "mail_and_packages" in hass.config.components

    # Check for mail_updated sensor reporting value from test data
    state = hass.states.get("sensor.mail_updated")
    assert state
    assert state.state == "Sep-18-2020 06:29 PM"

    # Make sure the rest of the sensors are importing our test data
    state = hass.states.get("sensor.mail_usps_mail")
    assert state
    assert state.state == "6"
    assert state.attributes["server"] == "imap.test.email"
    assert state.attributes["image"] == "mail_today.gif"

    state = hass.states.get("sensor.mail_usps_delivered")
    assert state
    assert state.state == "3"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_usps_delivering")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["92123456789012345"]
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_usps_packages")
    assert state
    assert state.state == "3"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_ups_delivered")
    assert state
    assert state.state == "1"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_ups_delivering")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1Z123456789"]
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_ups_packages")
    assert state
    assert state.state == "1"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_fedex_delivered")
    assert state
    assert state.state == "0"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_fedex_delivering")
    assert state
    assert state.state == "2"
    assert state.attributes["tracking_#"] == ["1234567890"]
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_fedex_packages")
    assert state
    assert state.state == "2"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_fedex_packages")
    assert state
    assert state.state == "2"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_amazon_packages")
    assert state
    assert state.state == "7"
    assert state.attributes["order"] == ["#123-4567890"]
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_amazon_packages_delivered")
    assert state
    assert state.state == "2"
    assert state.attributes["server"] == "imap.test.email"

    # state = hass.states.get("sensor.mail_amazon_hub")
    # assert state
    # assert state.state == "2"
    # assert state.attributes["code"] == ["1234567890"]

    # state = hass.states.get("sensor.mail_capost_delivered")
    # assert state
    # assert state.state == "1"

    # state = hass.states.get("sensor.mail_capost_delivering")
    # assert state
    # assert state.state == "1"

    # state = hass.states.get("sensor.mail_capost_packages")
    # assert state
    # assert state.state == "2"

    state = hass.states.get("sensor.mail_dhl_delivered")
    assert state
    assert state.state == "0"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_dhl_delivering")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1234567890"]
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_dhl_packages")
    assert state
    assert state.state == "2"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_packages_delivered")
    assert state
    assert state.state == "7"
    assert state.attributes["server"] == "imap.test.email"

    state = hass.states.get("sensor.mail_packages_in_transit")
    assert state
    assert state.state == "8"
    assert state.attributes["server"] == "imap.test.email"
