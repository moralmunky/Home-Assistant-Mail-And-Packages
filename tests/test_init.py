"""Tests for init module."""
import datetime
from datetime import date
from tests.conftest import mock_imap_amazon_shipped, mock_imap_ups_out_for_delivery
from custom_components.mail_and_packages.const import DOMAIN, DOMAIN_DATA, DATA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.async_mock import patch, call
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.mail_and_packages import (
    get_formatted_date,
    process_emails,
    update_time,
    cleanup_images,
    email_search,
    get_mails,
    _generate_mp4,
    download_img,
    amazon_search,
    get_count,
    get_items,
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

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 21
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0


async def test_setup_entry(hass, mock_imap_no_email):
    """Test settting up entities. """
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_get_formatted_date():
    assert get_formatted_date() == datetime.datetime.today().strftime("%d-%b-%Y")


async def test_update_time():
    assert update_time() == datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")


async def test_cleanup_images():
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove") as mock_osremove:
        cleanup_images("/tests/fakedir/")
        calls = [
            call("/tests/fakedir/testfile.gif"),
            call("/tests/fakedir/anotherfakefile.mp4"),
        ]
        mock_osremove.assert_has_calls(calls)


async def test_process_emails(hass, mock_imap_no_email):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove") as mock_osremove, patch(
        "os.makedirs"
    ) as mock_osmakedir, patch(
        "custom_components.mail_and_packages.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ):

        entry = MockConfigEntry(
            domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
        )

        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        config = entry.data
        result = process_emails(hass, config)
        assert result == {
            "amazon_delivered": 0,
            "amazon_order": [],
            "amazon_packages": 0,
            "capost_delivered": 0,
            "capost_delivering": 0,
            "capost_packages": 0,
            "capost_tracking": "",
            "dhl_delivered": 0,
            "dhl_delivering": 0,
            "dhl_packages": 0,
            "dhl_tracking": [],
            "fedex_delivered": 0,
            "fedex_delivering": 0,
            "fedex_packages": 0,
            "fedex_tracking": [],
            "mail_updated": "Sep-23-2020 10:28 AM",
            "ups_delivered": 0,
            "ups_delivering": 0,
            "ups_packages": 0,
            "ups_tracking": [],
            "usps_delivered": 0,
            "usps_delivering": 0,
            "usps_mail": 0,
            "usps_packages": 0,
            "usps_tracking": [],
            "zpackages_delivered": 0,
            "zpackages_transit": 0,
        }


async def test_process_emails_bad(hass, mock_imap_no_email):
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA_BAD,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_email_search(hass, mock_imap_no_email):
    result = email_search(mock_imap_no_email, "fake@eamil.address", "01-Jan-20")
    assert result == ("BAD", [])

    result = email_search(
        mock_imap_no_email, "fake@eamil.address", "01-Jan-20", "Fake Subject"
    )
    assert result == ("BAD", [])


async def test_get_mails(hass, mock_imap_no_email):
    result = get_mails(mock_imap_no_email, "./", "5", "mail_today.gif", False)
    assert result == 0


async def test_informed_delivery_emails(hass, mock_imap_usps_informed_digest):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove") as mock_osremove, patch(
        "os.makedirs"
    ) as mock_osmakedir, patch(
        "custom_components.mail_and_packages.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "builtins.open"
    ), patch(
        "custom_components.mail_and_packages.Image"
    ), patch(
        "custom_components.mail_and_packages.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
    ), patch(
        "custom_components.mail_and_packages.io"
    ):
        result = get_mails(
            mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
        )
        assert result == 3


async def test_ups_out_for_delivery(hass, mock_imap_ups_out_for_delivery):
    result = get_count(
        mock_imap_ups_out_for_delivery, "ups_delivering", True, "./", hass
    )
    assert result["count"] == 2
    # assert result["tracking"] == ["1Z2345YY0678901234"]


async def test_usps_out_for_delivery(hass, mock_imap_usps_out_for_delivery):
    result = get_count(
        mock_imap_usps_out_for_delivery, "usps_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["921234565085773077766900"]


async def test_amazon_shipped_count(hass, mock_imap_amazon_shipped):
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2020, 9, 11)

        result = get_items(mock_imap_amazon_shipped, "count")
        assert result == 4


async def test_amazon_shipped_order(hass, mock_imap_amazon_shipped):
    result = get_items(mock_imap_amazon_shipped, "order")
    assert result == ["#123-1234567-1234567"]


async def test_amazon_search(hass, mock_imap_no_email):
    result = amazon_search(mock_imap_no_email, "test/path", hass)
    assert result == 0


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
