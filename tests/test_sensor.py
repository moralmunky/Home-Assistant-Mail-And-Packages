"""Test Mail and Packages sensors."""

import datetime as dt
import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.http.auth import STORAGE_KEY
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import (
    AMAZON_EXCEPTION,
    AMAZON_ORDER,
    AMAZON_ORDER_DETAILS,
    ATTR_HAS_MAIL_IMAGES,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_ORDER_DETAILS,
    ATTR_SCANNED_IMAGES,
    ATTR_TRACKING_NUM,
    ATTR_UNSCANNED_PIECES,
    CONF_ALLOW_EXTERNAL,
    DOMAIN,
    SENSOR_TYPES,
)
from custom_components.mail_and_packages.sensor import ImagePathSensors, PackagesSensor
from tests.conftest import resolve_entity_id
from tests.const import FAKE_CONFIG_DATA_NO_RND


@pytest.mark.asyncio
async def test_sensor(hass, mock_update, entity_registry: er.EntityRegistry):
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

    def s(type_slug):
        eid = resolve_entity_id(entity_registry, entry.entry_id, "sensor", type_slug)
        return hass.states.get(eid)

    # Check for mail_updated sensor reporting value from test data
    state = s("mail_updated")
    assert state

    # Make sure the rest of the sensors are importing our test data
    state = s("mail_usps_mail")
    assert state
    assert state.state == "6"

    assert state.attributes["image"] == "mail_today.gif"
    assert state.attributes[ATTR_SCANNED_IMAGES] == 5
    assert state.attributes[ATTR_UNSCANNED_PIECES] == 1
    assert state.attributes[ATTR_HAS_MAIL_IMAGES] is True

    state = s("mail_usps_delivered")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["92123456789012345"]

    state = s("mail_usps_delivering")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["92123456789012345"]

    state = s("mail_usps_packages")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["92123456789012345"]

    state = s("mail_ups_delivered")
    assert state
    assert state.state == "1"

    state = s("mail_ups_delivering")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1Z123456789"]

    state = s("mail_ups_packages")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1Z123456789"]

    state = s("mail_fedex_delivered")
    assert state
    assert state.state == "0"

    state = s("mail_fedex_delivering")
    assert state
    assert state.state == "2"
    assert state.attributes["tracking_#"] == ["1234567890"]

    state = s("mail_fedex_packages")
    assert state
    assert state.state == "2"
    assert state.attributes["tracking_#"] == ["1234567890"]

    state = s("mail_amazon_packages")
    assert state
    assert state.state == "7"
    assert state.attributes["order"] == ["#123-4567890"]

    state = s("mail_amazon_delivered")
    assert state
    assert state.state == "2"
    assert state.attributes["order"] == ["#123-4567890"]

    state = s("mail_dhl_delivered")
    assert state
    assert state.state == "0"

    state = s("mail_dhl_delivering")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1234567890"]

    state = s("mail_dhl_packages")
    assert state
    assert state.state == "1"
    assert state.attributes["tracking_#"] == ["1234567890"]

    state = s("mail_auspost_delivered")
    assert state
    assert state.state == "2"

    state = s("mail_auspost_delivering")
    assert state
    assert state.state == "1"

    state = s("mail_auspost_packages")
    assert state
    assert state.state == "3"

    state = s("mail_poczta_polska_delivering")
    assert state
    assert state.state == "1"

    state = s("mail_poczta_polska_packages")
    assert state
    assert state.state == "1"

    state = s("mail_inpost_pl_delivered")
    assert state
    assert state.state == "2"

    state = s("mail_inpost_pl_delivering")
    assert state
    assert state.state == "1"

    state = s("mail_inpost_pl_packages")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["520113017830399002575123"]

    state = s("mail_dpd_com_pl_delivered")
    assert state
    assert state.state == "2"

    state = s("mail_dpd_com_pl_delivering")
    assert state
    assert state.state == "1"

    state = s("mail_dpd_com_pl_packages")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["13490015284111"]

    state = s("mail_gls_delivered")
    assert state
    assert state.state == "2"

    state = s("mail_gls_delivering")
    assert state
    assert state.state == "1"

    state = s("mail_gls_packages")
    assert state
    assert state.state == "3"
    assert state.attributes["tracking_#"] == ["51687952111"]

    state = s("packages_delivered")
    assert state
    assert state.state == "7"

    state = s("mail_image_system_path")
    assert state
    assert state.state.endswith("mail_today.gif")

    state = s("mail_image_url")
    assert state
    assert state.state == "mail_today.gif"
    assert "image_url" in state.attributes
    assert "/api/mail_and_packages/image/" in state.attributes["image_url"]


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
async def test_image_path_sensor_urls_legacy_external(
    hass, external_url, internal_url, expected_url
):
    """Test ImagePathSensors URL generation logic when allow_external is True."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "imap.test.email",
            CONF_PORT: 993,
            CONF_USERNAME: "test@test.com",
            CONF_PASSWORD: "password",
        },
    )

    # Mock coordinator data with CONF_ALLOW_EXTERNAL: True
    coordinator = MagicMock()
    coordinator.config = {CONF_ALLOW_EXTERNAL: True}
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
    attrs = sensor.extra_state_attributes
    if expected_url:
        assert attrs["image_url"] == expected_url
    else:
        assert attrs == {}


async def test_image_path_sensor_signed_url(hass):
    """Test ImagePathSensors signed URL generation when allow_external is False."""
    hass.data[STORAGE_KEY] = "test_refresh_token"
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_123",
        data={
            CONF_HOST: "imap.test.email",
            CONF_PORT: 993,
            CONF_USERNAME: "test@test.com",
            CONF_PASSWORD: "password",
        },
    )

    coordinator = MagicMock()
    coordinator.config = {CONF_ALLOW_EXTERNAL: False}
    coordinator.data = {"usps_image": "test_image.gif", "image_path": "images/"}

    hass.config.external_url = "https://external.hass.url"
    hass.config.internal_url = None

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )
    value = sensor.native_value
    assert value == "test_image.gif"
    assert len(value) <= 255
    attrs = sensor.extra_state_attributes
    assert "image_url" in attrs
    assert attrs["image_url"].startswith(
        "https://external.hass.url/api/mail_and_packages/image/test_entry_123/test_image.gif?authSig="
    )


async def test_image_path_sensor_url_ha_cloud(hass):
    """Test ImagePathSensors falls back to HA Cloud remote URL when external_url is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "imap.test.email",
            CONF_PORT: 993,
            CONF_USERNAME: "test@test.com",
            CONF_PASSWORD: "password",
        },
    )
    coordinator = MagicMock()
    coordinator.data = {"usps_image": "test_image.gif", "image_path": "images/"}
    hass.config.external_url = None
    hass.config.internal_url = None
    # Enable cloud component so get_url() can resolve Nabu Casa's remote UI URL
    hass.config.components.add("cloud")

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )

    cloud_url = "https://cloud.example.nabu.casa"
    mock_cloud = types.ModuleType("homeassistant.components.cloud")
    mock_cloud.CloudNotAvailable = Exception
    mock_cloud.async_remote_ui_url = MagicMock(return_value=cloud_url)

    with patch.dict(sys.modules, {"homeassistant.components.cloud": mock_cloud}):
        result = sensor._get_base_url()

    assert result == cloud_url


async def test_image_path_sensor_url_ha_cloud_unavailable(hass):
    """Test _get_base_url falls back to internal_url when HA Cloud raises CloudNotAvailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "imap.test.email",
            CONF_PORT: 993,
            CONF_USERNAME: "test@test.com",
            CONF_PASSWORD: "password",
        },
    )
    coordinator = MagicMock()
    coordinator.data = {"usps_image": "test_image.gif", "image_path": "images/"}
    hass.config.external_url = None
    hass.config.internal_url = "http://internal.hass.url"
    # Enable cloud component so get_url() can resolve Nabu Casa's remote UI URL
    hass.config.components.add("cloud")

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(key="usps_mail_image_url", name="Mail Image URL"),
        coordinator,
    )

    class _CloudNotAvailable(Exception):
        pass

    mock_cloud = types.ModuleType("homeassistant.components.cloud")
    mock_cloud.CloudNotAvailable = _CloudNotAvailable
    mock_cloud.async_remote_ui_url = MagicMock(side_effect=_CloudNotAvailable())

    with patch.dict(sys.modules, {"homeassistant.components.cloud": mock_cloud}):
        result = sensor._get_base_url()

    assert result == "http://internal.hass.url"


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
    assert isinstance(val, dt.datetime)
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
    assert isinstance(val, dt.datetime)
    # Verify it returned 'now' (roughly)
    assert (dt.datetime.now(dt.UTC) - val).total_seconds() < 5


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
    assert isinstance(val, dt.datetime)


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
    assert isinstance(sensor_updated.native_value, dt.datetime)

    # Verify extra_state_attributes returns empty dict when coordinator data is None
    coord_none = MagicMock()
    coord_none.data = None
    sensor_none = PackagesSensor(
        entry,
        MagicMock(key="packages", name="Packages"),
        coord_none,
    )
    assert sensor_none.extra_state_attributes == {}

    # Test attributes for generic exception sensors: tracking_# must be the
    # exception sensor's own retained numbers, not the in-transit list.
    coord_exc = MagicMock()
    coord_exc.data = {
        "usps_exception_tracking": ["92748902410637553123456789"],
        "usps_tracking": ["9400111899223397712345"],
    }
    sensor_exc_desc = MagicMock(key="usps_exception")
    sensor_exc_desc.name = "Mail USPS Exception"
    sensor_exc = PackagesSensor(
        entry,
        sensor_exc_desc,
        coord_exc,
    )
    assert sensor_exc._tracking_key == "usps_exception_tracking"
    attrs_exc = sensor_exc.extra_state_attributes
    assert attrs_exc[ATTR_TRACKING_NUM] == ["92748902410637553123456789"]

    # With no exception numbers retained, the attribute is absent rather
    # than falling back to the in-transit list.
    coord_exc_empty = MagicMock()
    coord_exc_empty.data = {"usps_tracking": ["9400111899223397712345"]}
    sensor_exc_empty = PackagesSensor(
        entry,
        sensor_exc_desc,
        coord_exc_empty,
    )
    assert ATTR_TRACKING_NUM not in sensor_exc_empty.extra_state_attributes

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

    # Test attributes for Amazon Hub
    coord_hub = MagicMock()
    coord_hub.data = {"amazon_hub_code": ["123456"]}
    sensor_hub_desc = MagicMock(key="amazon_hub")
    sensor_hub_desc.name = "Mail Amazon Hub"
    sensor_hub = PackagesSensor(
        entry,
        sensor_hub_desc,
        coord_hub,
    )
    attrs_hub = sensor_hub.extra_state_attributes
    assert attrs_hub["code"] == ["123456"]

    # Test attributes for Amazon OTP
    coord_otp = MagicMock()
    coord_otp.data = {
        AMAZON_ORDER: ["123-1234567-1234567"],
        "amazon_otp_code": ["654321"],
    }
    sensor_otp_desc = MagicMock(key="amazon_otp")
    sensor_otp_desc.name = "Mail Amazon OTP"
    sensor_otp = PackagesSensor(
        entry,
        sensor_otp_desc,
        coord_otp,
    )
    attrs_otp = sensor_otp.extra_state_attributes
    assert attrs_otp["code"] == ["654321"]
    assert ATTR_ORDER not in attrs_otp

    # Test delivery date/window attributes for Amazon OTP
    coord_otp_delivery = MagicMock()
    coord_otp_delivery.data = {
        "amazon_otp_code": ["123456"],
        "amazon_otp_order": ["111-1234567-1234567"],
        "amazon_otp_delivery_date": ["2026-11-06"],
        "amazon_otp_delivery_window": ["1 PM - 4 PM"],
        "amazon_otp_delivery_window_start": ["13:00"],
        "amazon_otp_delivery_window_end": ["16:00"],
    }
    sensor_otp_delivery = PackagesSensor(
        entry,
        sensor_otp_desc,
        coord_otp_delivery,
    )
    attrs_delivery = sensor_otp_delivery.extra_state_attributes
    assert attrs_delivery["code"] == ["123456"]
    assert attrs_delivery[ATTR_ORDER] == ["111-1234567-1234567"]
    assert attrs_delivery["delivery_date"] == "2026-11-06"
    assert attrs_delivery["delivery_window"] == "1 PM - 4 PM"
    assert attrs_delivery["delivery_window_start"] == "13:00"
    assert attrs_delivery["delivery_window_end"] == "16:00"

    # Delivery attributes also accept plain string values
    coord_otp_str = MagicMock()
    coord_otp_str.data = {
        "amazon_otp_delivery_date": "2026-11-06",
        "amazon_otp_delivery_window_start": "13:00",
    }
    sensor_otp_str = PackagesSensor(
        entry,
        sensor_otp_desc,
        coord_otp_str,
    )
    attrs_str = sensor_otp_str.extra_state_attributes
    assert attrs_str["delivery_date"] == "2026-11-06"
    assert attrs_str["delivery_window_start"] == "13:00"

    # Test attributes for Amazon Delivering
    coord_delivering = MagicMock()
    coord_delivering.data = {"amazon_delivering_order": ["303-1873062-3277126"]}
    sensor_delivering_desc = MagicMock(key="amazon_delivering")
    sensor_delivering_desc.name = "Mail Amazon Packages Delivering"
    sensor_delivering = PackagesSensor(
        entry,
        sensor_delivering_desc,
        coord_delivering,
    )
    attrs_delivering = sensor_delivering.extra_state_attributes
    assert attrs_delivering[ATTR_ORDER] == ["303-1873062-3277126"]


@pytest.mark.asyncio
async def test_amazon_otp_window_and_code_sensors(hass):
    """Window start/end are timestamps and the code sensor is a scalar.

    The window sensors combine the delivery date and window bounds from
    the OTP email (coordinator values may be lists or plain strings) so a
    plain ``time`` trigger can fire on them; all three sensors are
    unknown when there is no OTP code today.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    tz = dt_util.get_default_time_zone()

    def make_sensor(key, data):
        coordinator = MagicMock()
        coordinator.data = data
        return PackagesSensor(entry, SENSOR_TYPES[key], coordinator)

    # Sensor definitions: names and device classes
    start_desc = SENSOR_TYPES["amazon_otp_window_start"]
    end_desc = SENSOR_TYPES["amazon_otp_window_end"]
    code_desc = SENSOR_TYPES["amazon_otp_delivery_code"]
    assert start_desc.name == "Mail Amazon Delivery Window Start"
    assert end_desc.name == "Mail Amazon Delivery Window End"
    assert code_desc.name == "Mail Amazon Delivery Code"
    assert start_desc.device_class == SensorDeviceClass.TIMESTAMP
    assert end_desc.device_class == SensorDeviceClass.TIMESTAMP
    assert code_desc.device_class is None

    full_data = {
        "amazon_otp_code": ["123456", "999999"],
        "amazon_otp_delivery_date": ["2026-11-06"],
        "amazon_otp_delivery_window_start": ["13:00"],
        "amazon_otp_delivery_window_end": ["16:00"],
        AMAZON_ORDER: ["111-1234567-1234567"],
    }
    start = make_sensor("amazon_otp_window_start", full_data)
    end = make_sensor("amazon_otp_window_end", full_data)
    code = make_sensor("amazon_otp_delivery_code", full_data)
    assert start.native_value == dt.datetime(2026, 11, 6, 13, 0, tzinfo=tz)
    assert end.native_value == dt.datetime(2026, 11, 6, 16, 0, tzinfo=tz)
    assert start.native_value.tzinfo is not None
    # The code sensor exposes the first code as a plain string
    assert code.native_value == "123456"
    # No Amazon order attributes leak onto the new sensors
    assert start.extra_state_attributes == {}
    assert code.extra_state_attributes == {}

    # Coordinator values as plain strings work the same way
    string_data = {
        "amazon_otp_code": "123456",
        "amazon_otp_delivery_date": "2026-11-06",
        "amazon_otp_delivery_window_start": "13:00",
        "amazon_otp_delivery_window_end": "16:00",
    }
    assert make_sensor(
        "amazon_otp_window_start", string_data
    ).native_value == dt.datetime(2026, 11, 6, 13, 0, tzinfo=tz)
    assert make_sensor("amazon_otp_delivery_code", string_data).native_value == "123456"

    # A code without a window: window sensors unknown, code still set
    code_only = {"amazon_otp_code": ["123456"]}
    assert make_sensor("amazon_otp_window_start", code_only).native_value is None
    assert make_sensor("amazon_otp_window_end", code_only).native_value is None
    assert make_sensor("amazon_otp_delivery_code", code_only).native_value == "123456"

    # Malformed date or time values are unknown, never an exception
    bad_data = {
        "amazon_otp_code": ["123456"],
        "amazon_otp_delivery_date": ["not-a-date"],
        "amazon_otp_delivery_window_start": ["1 PM"],
        "amazon_otp_delivery_window_end": ["25:99"],
    }
    assert make_sensor("amazon_otp_window_start", bad_data).native_value is None
    assert make_sensor("amazon_otp_window_end", bad_data).native_value is None

    # A window bound without its pair is unknown too
    date_only = {
        "amazon_otp_code": ["123456"],
        "amazon_otp_delivery_date": ["2026-11-06"],
    }
    assert make_sensor("amazon_otp_window_start", date_only).native_value is None
    time_only = {
        "amazon_otp_code": ["123456"],
        "amazon_otp_delivery_window_end": ["16:00"],
    }
    assert make_sensor("amazon_otp_window_end", time_only).native_value is None

    # Empty or non-string coordinator values never produce a state
    weird_data = {"amazon_otp_code": [""], "amazon_otp_delivery_date": [20261106]}
    assert make_sensor("amazon_otp_delivery_code", weird_data).native_value is None
    assert make_sensor("amazon_otp_window_start", weird_data).native_value is None
    assert (
        make_sensor(
            "amazon_otp_delivery_code", {"amazon_otp_code": 123456}
        ).native_value
        is None
    )

    # No OTP email today: all three sensors unknown
    empty_data = {"amazon_otp": 0, "amazon_otp_code": []}
    assert make_sensor("amazon_otp_window_start", empty_data).native_value is None
    assert make_sensor("amazon_otp_window_end", empty_data).native_value is None
    assert make_sensor("amazon_otp_delivery_code", empty_data).native_value is None
    assert make_sensor("amazon_otp_delivery_code", {}).native_value is None


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
    assert sensor.extra_state_attributes == {ATTR_IMAGE_PATH: expected}


@pytest.mark.asyncio
async def test_image_path_sensor_state_retention(hass):
    """Test that ImagePathSensors retains last known good state when image is missing."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()
    coordinator.data = {
        "usps_image": "test.gif",
        "image_path": "images/",
    }

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(
            key="usps_mail_image_system_path", name="USPS Mail Image System Path"
        ),
        coordinator,
    )
    expected = f"{hass.config.path()}/images/test.gif"
    assert sensor.native_value == expected
    assert sensor.extra_state_attributes == {ATTR_IMAGE_PATH: expected}

    # Simulate next update having no new usps_image data
    coordinator.data = {"image_path": "images/"}
    assert sensor.native_value == expected
    assert sensor.extra_state_attributes == {ATTR_IMAGE_PATH: expected}


@pytest.mark.asyncio
async def test_image_path_sensor_exceeds_max_length(hass):
    """Test ImagePathSensors when path exceeds MAX_LENGTH_STATE_STATE (255 chars)."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()
    # Create a path that will exceed 255 chars
    long_dir = "a" * 260
    coordinator.data = {
        "usps_image": "mail_today.jpg",
        "image_path": f"{long_dir}/",
    }

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(
            key="usps_mail_image_system_path", name="USPS Mail Image System Path"
        ),
        coordinator,
    )
    full_path = f"{hass.config.path()}/{long_dir}/mail_today.jpg"
    assert len(full_path) > 255
    # State falls back to image filename so state does not error out on HA's 255 limit
    assert sensor.native_value == "mail_today.jpg"
    # Attribute holds the complete untruncated full path
    assert sensor.extra_state_attributes == {ATTR_IMAGE_PATH: full_path}


@pytest.mark.asyncio
async def test_image_path_sensor_attributes_uninitialized(hass):
    """Test ImagePathSensors extra_state_attributes when evaluated directly without native_value first."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "test"})
    coordinator = MagicMock()
    coordinator.data = {
        "usps_image": "mail_today.jpg",
        "image_path": "images/",
    }

    sensor = ImagePathSensors(
        hass,
        entry,
        MagicMock(
            key="usps_mail_image_system_path", name="USPS Mail Image System Path"
        ),
        coordinator,
    )
    expected = f"{hass.config.path()}/images/mail_today.jpg"
    # Access attributes directly without prior native_value call
    assert sensor.extra_state_attributes == {ATTR_IMAGE_PATH: expected}

    # Verify attributes update dynamically when coordinator image changes
    coordinator.data = {
        "usps_image": "mail_new.jpg",
        "image_path": "images/",
    }
    expected_new = f"{hass.config.path()}/images/mail_new.jpg"
    assert sensor.extra_state_attributes == {ATTR_IMAGE_PATH: expected_new}


@pytest.mark.asyncio
async def test_amazon_packages_order_details_attribute(hass):
    """The amazon_packages sensor exposes order_details only when present."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_NO_RND,
    )
    sensor_desc = MagicMock(key="amazon_packages")
    sensor_desc.name = "Mail Amazon Packages"

    details = {"123-4567890-1234567": {"name": "Widget", "image": "https://img/1"}}
    coord_with = MagicMock()
    coord_with.data = {
        AMAZON_ORDER: ["123-4567890-1234567"],
        AMAZON_ORDER_DETAILS: details,
    }
    attrs = PackagesSensor(entry, sensor_desc, coord_with).extra_state_attributes
    assert attrs[ATTR_ORDER] == ["123-4567890-1234567"]
    assert attrs[ATTR_ORDER_DETAILS] == details

    # No details collected: the attribute is omitted entirely.
    coord_without = MagicMock()
    coord_without.data = {AMAZON_ORDER: ["123-4567890-1234567"]}
    attrs_none = PackagesSensor(
        entry, sensor_desc, coord_without
    ).extra_state_attributes
    assert attrs_none[ATTR_ORDER] == ["123-4567890-1234567"]
    assert ATTR_ORDER_DETAILS not in attrs_none
