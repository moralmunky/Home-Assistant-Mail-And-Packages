"""Tests for init module."""
import datetime
from custom_components.mail_and_packages.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.async_mock import patch, call
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.mail_and_packages import (
    get_formatted_date,
    update_time,
    cleanup_images,
)

from tests.const import FAKE_CONFIG_DATA


async def test_unload_entry(hass, mock_update):
    """Test unloading entities. """
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 18
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0


async def test_get_formatted_date():
    assert get_formatted_date() == datetime.datetime.today().strftime("%d-%b-%Y")


async def test_update_time():
    assert update_time() == datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")


async def test_cleanup_images():
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ) as mock_listdir, patch("os.remove") as mock_osremove:
        cleanup_images("/tests/fakedir/")
        calls = [
            call("/tests/fakedir/testfile.gif"),
            call("/tests/fakedir/anotherfakefile.mp4"),
        ]
        mock_osremove.assert_has_calls(calls)

