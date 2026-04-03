"""Test Mail and Packages sensors."""

import datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import (
    AMAZON_EXCEPTION,
    AMAZON_ORDER,
    ATTR_ORDER,
    DOMAIN,
)
from custom_components.mail_and_packages.sensor import ImagePathSensors, PackagesSensor
from tests.const import FAKE_CONFIG_DATA_NO_RND


@pytest.mark.asyncio
async def test_sensor(hass, mock_update):
    """Test the setup and state of standard sensors."""
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


@pytest.mark.parametrize(
    ("external_url", "internal_url", "expected_url"),
    [
        (
            "https://external.hass.url",
            None,
            "https://external.hass.url/local/mail_and_packages/test_image.gif",
        ),
        (
            None,
            "http://internal.hass.url",
            "http://internal.hass.url/local/mail_and_packages/test_image.gif",
        ),
        (None, None, None),
    ],
)
async def test_image_path_sensor_urls(hass, external_url, internal_url, expected_url):
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
    coordinator.data = {"usps_image": "test_image.gif", "image_path": "images/"}

    hass.config.external_url = external_url
    hass.config.internal_url = internal_url

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )
    assert sensor.native_value == expected_url


async def test_mail_updated_sensor_string_conversion(hass):
    """Test that the mail_updated sensor handles string values correctly."""
    # This covers the fix we applied to sensor.py
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()

    # Simulate data stored as a string (e.g. from restore state)
    coordinator.data = {"mail_updated": "2023-10-27T10:00:00+00:00"}

    sensor = PackagesSensor(
        entry,
        MagicMock(key="mail_updated", name="Mail Updated"),
        coordinator,
    )

    # Value should be converted to datetime object
    val = sensor.native_value
    assert isinstance(val, datetime.datetime)
    assert val.year == 2023


async def test_mail_updated_sensor_invalid_date_string(hass):
    """Test that the mail_updated sensor handles invalid date strings gracefully."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()

    # Simulate invalid date string in data (e.g. corrupted cache)
    coordinator.data = {"mail_updated": "NOT_A_VALID_DATE_STRING"}

    sensor = PackagesSensor(
        entry,
        MagicMock(key="mail_updated", name="Mail Updated"),
        coordinator,
    )

    # Should trigger ValueError handler and return current time
    val = sensor.native_value
    assert isinstance(val, datetime.datetime)
    # Verify it returned 'now' (roughly)
    assert (datetime.datetime.now(datetime.UTC) - val).total_seconds() < 5


@pytest.mark.asyncio
async def test_mail_updated_sensor_totally_invalid_date(hass):
    """Test mail_updated sensor with a string that definitely raises ValueError."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()

    # Use a string guaranteed to fail fromisoformat
    coordinator.data = {"mail_updated": "this is not a date"}

    sensor = PackagesSensor(
        entry,
        MagicMock(key="mail_updated", name="Mail Updated"),
        coordinator,
    )

    # This calls native_value, triggering the exception handler
    val = sensor.native_value

    # Should return current time (roughly)
    assert isinstance(val, datetime.datetime)


@pytest.mark.asyncio
async def test_packages_sensor_attributes_edge_cases(hass):
    """Test PackagesSensor attributes and native_value edge cases."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()

    # Test tracking key derivation for single word sensor types
    sensor = PackagesSensor(
        entry,
        MagicMock(key="packages", name="Packages"),
        coordinator,
    )
    assert sensor._tracking_key == "packages_tracking"

    # Verify that mail_updated sensor returns current time if data is missing
    coordinator.data = {}
    sensor_updated = PackagesSensor(
        entry,
        MagicMock(key="mail_updated", name="Mail Updated"),
        coordinator,
    )
    assert isinstance(sensor_updated.native_value, datetime.datetime)

    # Verify extra_state_attributes returns empty dict when coordinator data is None
    coord_none = MagicMock()
    coord_none.data = None
    sensor_none = PackagesSensor(
        entry,
        MagicMock(key="packages", name="Packages"),
        coord_none,
    )
    assert sensor_none.extra_state_attributes == {}

    # Test attributes for Amazon Exception sensors

    coord_ex = MagicMock()
    coord_ex.data = {
        ATTR_ORDER: ["Error #1"],
        AMAZON_ORDER: ["Order #123"],
    }

    sensor_ex_desc = MagicMock(key=AMAZON_EXCEPTION)
    sensor_ex_desc.name = "Mail Amazon Exception"
    sensor_ex = PackagesSensor(
        entry,
        sensor_ex_desc,
        coord_ex,
    )
    attrs_ex = sensor_ex.extra_state_attributes
    assert attrs_ex[ATTR_ORDER] == ["Error #1"]

    # Test attributes for regular Amazon packages sensor
    sensor_desc = MagicMock(key="amazon_packages")
    sensor_desc.name = "Mail Amazon Packages"
    sensor_regular = PackagesSensor(
        entry,
        sensor_desc,
        coord_ex,
    )
    attrs = sensor_regular.extra_state_attributes
    assert attrs[ATTR_ORDER] == ["Order #123"]


@pytest.mark.asyncio
async def test_image_path_sensor_grid(hass):
    """Test ImagePathSensors URL generation logic for grid image paths."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()
    coordinator.data = {
        "usps_image": "test.gif",
        "grid_image": "test_grid.png",
        "image_path": "images/",
    }

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_grid_image_path", name="USPS Grid Path"),
        coordinator,
    )
    expected = f"{hass.config.path()}/images/test_grid.png"
    assert sensor.native_value == expected
