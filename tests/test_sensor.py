"""Test Mail and Packages sensors."""

import datetime
from datetime import timezone
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from custom_components.mail_and_packages.sensor import ImagePathSensors, PackagesSensor
from tests.const import FAKE_CONFIG_DATA_NO_RND


@pytest.mark.asyncio
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
    assert state.attributes["tracking_#"] == ["92123456789012345"]

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
    assert state.attributes["order"] == ["#123-4567890"]

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


async def test_image_path_sensor_urls(hass):
    """Test ImagePathSensors URL generation logic."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "imap.test.email",
            CONF_PORT: 993,
            CONF_USERNAME: "test@test.com",
            CONF_PASSWORD: "password",
        },
    )

    # Mock coordinator data
    coordinator = MagicMock()
    coordinator.data = {"image_name": "test_image.gif", "image_path": "images/"}

    # 1. Test with External URL
    hass.config.external_url = "https://external.hass.url"
    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )
    assert (
        sensor.native_value
        == "https://external.hass.url/local/mail_and_packages/test_image.gif"
    )

    # 2. Test with Internal URL only
    hass.config.external_url = None
    hass.config.internal_url = "http://internal.hass.url"
    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )
    assert (
        sensor.native_value
        == "http://internal.hass.url/local/mail_and_packages/test_image.gif"
    )

    # 3. Test with NO URL set
    hass.config.external_url = None
    hass.config.internal_url = None
    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )
    assert sensor.native_value is None


async def test_mail_updated_sensor_string_conversion(hass):
    """Test that the mail_updated sensor handles string values correctly."""
    # This covers the fix we applied to sensor.py
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()

    # Simulate data stored as a string (e.g. from restore state)
    coordinator.data = {"mail_updated": "2023-10-27T10:00:00+00:00"}

    sensor = PackagesSensor(
        entry, MagicMock(key="mail_updated", name="Mail Updated"), coordinator
    )

    # Value should be converted to datetime object
    val = sensor.native_value
    assert isinstance(val, datetime.datetime)
    assert val.year == 2023


async def test_mail_updated_sensor_invalid_date_string(hass):
    """Test that the mail_updated sensor handles invalid date strings gracefully."""
    from datetime import datetime
    from unittest.mock import MagicMock

    from custom_components.mail_and_packages.sensor import PackagesSensor

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()

    # Simulate invalid date string in data (e.g. corrupted cache)
    coordinator.data = {"mail_updated": "NOT_A_VALID_DATE_STRING"}

    sensor = PackagesSensor(
        entry, MagicMock(key="mail_updated", name="Mail Updated"), coordinator
    )

    # Should trigger ValueError handler and return current time
    val = sensor.native_value
    assert isinstance(val, datetime)
    # Verify it returned 'now' (roughly)
    assert (datetime.now(timezone.utc) - val).total_seconds() < 5
