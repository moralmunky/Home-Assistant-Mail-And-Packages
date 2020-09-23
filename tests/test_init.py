"""Tests for init module."""
import datetime
from tests.conftest import mock_aiohttp
from custom_components.mail_and_packages.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.async_mock import patch, call
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.mail_and_packages import (
    get_formatted_date,
    update_time,
    cleanup_images,
    email_search,
    get_mails,
    _generate_mp4,
    download_img,
)

from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_BAD


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


async def test_process_emails(hass, mock_imap_no_email):
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_process_emails_bad(hass, mock_imap):
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA_BAD,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# async def test_email_search(hass, mock_imap_no_email):
#     result = email_search(mock_imap_no_email, "fake@eamil.address", "01-Jan-20")
#     assert result

#     result = email_search(
#         mock_imap_no_email, "fake@eamil.address", "01-Jan-20", "Fake Subject"
#     )
#     assert result


# async def test_get_mails(hass, mock_imap_no_email):
#     result = get_mails(mock_imap_no_email, "./", "5", "mail_today.gif", False)
#     assert result


async def test_generate_mp4():
    with patch("os.path.join") as mock_path_join, patch(
        "os.remove"
    ) as mock_remove, patch("subprocess.call") as mock_subprocess:
        _generate_mp4("./", "testfile.gif")

        mock_path_join.called_with("./", "testfile.gif")
        mock_remove.called_with("testfile.mp4")
        mock_subprocess.called_with(
            "ffmpeg",
            "-f",
            "gif",
            "-i",
            "testfile.gif",
            "-pix_fmt",
            "yuv420p",
            "-filter:v",
            "crop='floor(in_w/2)*2:floor(in_h/2)*2'",
            "testfile.mp4",
        )


# async def test_download_img(mock_aiohttp):
#     with patch("open.write") as mock_open, patch(
#         "custom_components.mail_and_packages.aiohttp.ClientSession.get",
#         return_value=200,
#     ) as mock_get, patch(
#         "custom_components.mail_and_packages.aiohttp.ClientSession.get.headers",
#         return_value="content-type: image/jpeg",
#     ) as mock_headers, patch(
#         "custom_components.mail_and_packages.aiohttp.ClientSession.get.read",
#         return_value="123456",
#     ) as mock_read:
#         download_img("http://fake.website.com", "/not/a/real/website/image.jpg")

#         mock_open.assert_called()
