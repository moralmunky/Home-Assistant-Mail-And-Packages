""" Test Mail and Packages sensors."""
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

    # Make sure the rest of the sensors are importing our test data
    state = hass.states.get("sensor.mail_usps_mail")
    assert state
    assert state.state == "6"

    assert state.attributes["image"] == "mail_today.gif"

    state = hass.states.get("sensor.mail_usps_delivered")
    assert state
    assert state.state == "3"

    state = hass.states.get("sensor.mail_usps_delivering")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["92123456789012345"]

    state = hass.states.get("sensor.mail_usps_packages")
    assert state
    assert state.state == "3"

    state = hass.states.get("sensor.mail_ups_delivered")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_ups_delivering")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1Z123456789"]

    state = hass.states.get("sensor.mail_ups_packages")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_fedex_delivered")
    assert state
    assert state.state == "0"

    state = hass.states.get("sensor.mail_fedex_delivering")
    assert state
    assert state.state == "2"
    assert state.attributes["tracking_#"] == ["1234567890"]

    state = hass.states.get("sensor.mail_fedex_packages")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_fedex_packages")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_amazon_packages")
    assert state
    assert state.state == "7"
    assert state.attributes["order"] == ["#123-4567890"]

    state = hass.states.get("sensor.mail_amazon_packages_delivered")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_dhl_delivered")
    assert state
    assert state.state == "0"

    state = hass.states.get("sensor.mail_dhl_delivering")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1234567890"]

    state = hass.states.get("sensor.mail_dhl_packages")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_auspost_delivered")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_auspost_delivering")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_auspost_packages")
    assert state
    assert state.state == "3"

    state = hass.states.get("sensor.mail_poczta_polska_delivering")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_poczta_polska_packages")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_inpost_pl_delivered")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_inpost_pl_delivering")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_inpost_pl_packages")
    assert state
    assert state.state == "3"

    state = hass.states.get("sensor.mail_dpd_com_pl_delivered")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_dpd_com_pl_delivering")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_dpd_com_pl_packages")
    assert state
    assert state.state == "3"

    state = hass.states.get("sensor.mail_gls_delivered")
    assert state
    assert state.state == "2"

    state = hass.states.get("sensor.mail_gls_delivering")
    assert state
    assert state.state == "1"

    state = hass.states.get("sensor.mail_gls_packages")
    assert state
    assert state.state == "3"

    state = hass.states.get("sensor.mail_packages_delivered")
    assert state
    assert state.state == "7"
