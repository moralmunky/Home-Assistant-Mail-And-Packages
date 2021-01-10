"""Tests for init module."""
import datetime
from datetime import date
from unittest import mock
from unittest.mock import call, patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from custom_components.mail_and_packages.helpers import (
    _generate_mp4,
    amazon_hub,
    amazon_search,
    cleanup_images,
    email_fetch,
    email_search,
    get_count,
    get_formatted_date,
    get_items,
    get_mails,
    login,
    process_emails,
    resize_images,
    selectfolder,
    update_time,
)
from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_BAD, FAKE_CONFIG_DATA_NO_RND


async def test_unload_entry(hass, mock_update):
    """Test unloading entities. """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 22
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0


async def test_setup_entry(
    hass,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
):
    """Test settting up entities. """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 26
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_get_formatted_date():
    assert get_formatted_date() == datetime.datetime.today().strftime("%d-%b-%Y")


async def test_update_time():
    assert update_time() == datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")


async def test_cleanup_images(mock_listdir, mock_osremove):
    cleanup_images("/tests/fakedir/")
    calls = [
        call("/tests/fakedir/testfile.gif"),
        call("/tests/fakedir/anotherfakefile.mp4"),
    ]
    mock_osremove.assert_has_calls(calls)


async def test_cleanup_found_images_remove_err(
    mock_listdir, mock_osremove_exception, caplog
):
    cleanup_images("/tests/fakedir/")

    assert mock_osremove_exception.called_with("/tests/fakedir/")
    assert "Error attempting to remove found image:" in caplog.text


async def test_cleanup_images_remove_err(mock_listdir, mock_osremove_exception, caplog):
    cleanup_images("/tests/fakedir/", "testimage.jpg")

    assert mock_osremove_exception.called_with("/tests/fakedir/")
    assert "Error attempting to remove image:" in caplog.text


async def test_process_emails(
    hass,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copyfile,
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_NO_RND,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config = entry.data
    assert config == FAKE_CONFIG_DATA_NO_RND
    result = process_emails(hass, config)
    assert result == {
        "amazon_delivered": 0,
        "amazon_hub": 0,
        "amazon_hub_code": [],
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
        "image_name": "mail_today.gif",
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
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_BAD,
    )

    entry.version = 2
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_process_emails_random(
    hass,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copyfile,
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config = entry.data
    result = process_emails(hass, config)
    assert ".gif" in result["image_name"]


async def test_email_search(mock_imap_search_error, caplog):
    result = email_search(mock_imap_search_error, "fake@eamil.address", "01-Jan-20")
    assert result == ("BAD", "Invalid SEARCH format")
    assert "Error searching emails:" in caplog.text

    result = email_search(
        mock_imap_search_error, "fake@eamil.address", "01-Jan-20", "Fake Subject"
    )
    assert result == ("BAD", "Invalid SEARCH format")
    assert "Error searching emails:" in caplog.text


async def test_email_fetch(mock_imap_fetch_error, caplog):
    result = email_fetch(mock_imap_fetch_error, 1, "(RFC822)")
    assert result == ("BAD", "Invalid Email")
    assert "Error fetching emails:" in caplog.text


async def test_get_mails(mock_imap_no_email, mock_copyfile):
    result = get_mails(mock_imap_no_email, "./", "5", "mail_today.gif", False)
    assert result == 0


async def test_get_mails_copyfile_error(
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    result = get_mails(
        mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
    )
    assert "File not found" in caplog.text


async def test_informed_delivery_emails(
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_open,
    mock_os_path_splitext,
    mock_update_time,
    mock_image,
    mock_io,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    result = get_mails(
        mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
    )
    assert result == 3
    assert "USPSInformedDelivery@usps.gov" in caplog.text
    assert "USPSInformeddelivery@informeddelivery.usps.com" in caplog.text


async def test_get_mails_imageio_error(
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_open,
    mock_os_path_splitext,
    mock_update_time,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    with patch("custom_components.mail_and_packages.helpers.io") as mock_imageio:
        mock_imageio.return_value = mock.Mock(autospec=True)
        mock_imageio.mimwrite.side_effect = Exception("Processing Error")
        result = get_mails(
            mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
        )
        assert result == 3
        assert "Error attempting to generate image:" in caplog.text


async def test_informed_delivery_emails_mp4(
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_open,
    mock_os_path_splitext,
    mock_update_time,
    mock_image,
    mock_io,
    mock_resizeimage,
    mock_copyfile,
):
    with patch(
        "custom_components.mail_and_packages.helpers._generate_mp4"
    ) as mock_generate_mp4:
        result = get_mails(
            mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", True
        )
        assert result == 3
        assert mock_generate_mp4.called_with("./", "mail_today.gif")


async def test_informed_delivery_emails_open_err(
    mock_imap_usps_informed_digest,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_update_time,
    mock_image,
    mock_io,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    get_mails(
        mock_imap_usps_informed_digest,
        "/totally/fake/path/",
        "5",
        "mail_today.gif",
        False,
    )
    assert (
        "Error opening filepath: [Errno 2] No such file or directory: '/totally/fake/path/1040327780-101.jpg'"
        in caplog.text
    )


async def test_informed_delivery_emails_io_err(
    mock_imap_usps_informed_digest,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_open,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
):
    with pytest.raises(FileNotFoundError) as exc_info:
        get_mails(
            mock_imap_usps_informed_digest,
            "/totally/fake/path/",
            "5",
            "mail_today.gif",
            False,
        )
    assert type(exc_info.value) is FileNotFoundError


async def test_informed_delivery_missing_mailpiece(
    mock_imap_usps_informed_digest_missing,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_open,
    mock_os_path_splitext,
    mock_image,
    mock_io,
    mock_resizeimage,
    mock_copyfile,
):
    result = get_mails(
        mock_imap_usps_informed_digest_missing, "./", "5", "mail_today.gif", False
    )
    assert result == 5


async def test_informed_delivery_no_mail(
    mock_imap_usps_informed_digest_no_mail,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_open,
    mock_os_path_splitext,
    mock_image,
    mock_io,
    mock_resizeimage,
    mock_os_path_isfile,
    mock_copyfile,
):
    result = get_mails(
        mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
    )
    assert result == 0


async def test_informed_delivery_no_mail_copy_error(
    mock_imap_usps_informed_digest_no_mail,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_update_time,
    mock_open,
    mock_os_path_splitext,
    mock_image,
    mock_io,
    mock_resizeimage,
    mock_os_path_isfile,
    mock_copy_overlays,
    mock_copyfile_exception,
    caplog,
):
    get_mails(
        mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
    )
    assert mock_copyfile_exception.called_with("./mail_today.gif")
    assert "File not found" in caplog.text


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


async def test_dhl_out_for_delivery(hass, mock_imap_dhl_out_for_delivery):
    result = get_count(
        mock_imap_dhl_out_for_delivery, "dhl_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["4212345678"]


async def test_hermes_out_for_delivery(hass, mock_imap_hermes_out_for_delivery):
    result = get_count(
        mock_imap_hermes_out_for_delivery, "hermes_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["8888888888888888"]


async def test_royal_out_for_delivery(hass, mock_imap_royal_out_for_delivery):
    result = get_count(
        mock_imap_royal_out_for_delivery, "royal_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["MA038501234GB"]


async def test_amazon_fwds(
    hass,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    caplog,
):
    """Test settting up entities. """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "Amazon email adding fakeuser@fake.email to list" in caplog.text
    assert "Amazon email adding fakeuser2@fake.email to list" in caplog.text


async def test_amazon_shipped_count(hass, mock_imap_amazon_shipped):
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2020, 9, 11)

        result = get_items(mock_imap_amazon_shipped, "count")
        assert result == 6


async def test_amazon_shipped_order(hass, mock_imap_amazon_shipped):
    result = get_items(mock_imap_amazon_shipped, "order")
    assert result == ["123-1234567-1234567"]


async def test_amazon_shipped_order_alt(hass, mock_imap_amazon_shipped_alt):
    result = get_items(mock_imap_amazon_shipped_alt, "order")
    assert result == ["123-1234567-1234567"]


async def test_amazon_shipped_order_uk(hass, mock_imap_amazon_shipped_uk):
    result = get_items(mock_imap_amazon_shipped_uk, "order")
    assert result == ["123-4567890-1234567"]


async def test_amazon_shipped_order_it(hass, mock_imap_amazon_shipped_it):
    result = get_items(mock_imap_amazon_shipped_it, "order")
    assert result == ["405-5236882-9395563"]


async def test_amazon_search(hass, mock_imap_no_email):
    result = amazon_search(mock_imap_no_email, "test/path", hass)
    assert result == 0


async def test_amazon_search_results(hass, mock_imap_amazon_shipped):
    result = amazon_search(mock_imap_amazon_shipped, "test/path", hass)
    assert result == 12


async def test_amazon_search_delivered(
    hass, mock_imap_amazon_delivered, mock_download_img
):
    result = amazon_search(mock_imap_amazon_delivered, "test/path", hass)
    assert result == 12


async def test_amazon_search_delivered_it(
    hass, mock_imap_amazon_delivered_it, mock_download_img
):
    result = amazon_search(mock_imap_amazon_delivered_it, "test/path", hass)
    assert result == 12


async def test_amazon_hub(hass, mock_imap_amazon_the_hub):
    result = amazon_hub(mock_imap_amazon_the_hub)
    assert result["count"] == 1
    assert result["code"] == ["123456"]


async def test_generate_mp4(
    mock_osremove, mock_os_path_join, mock_subprocess_call, mock_os_path_split
):
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        _generate_mp4("./", "testfile.gif")

        mock_os_path_join.called_with("./", "testfile.gif")
        mock_osremove.called_with("./", "testfile.mp4")
        mock_subprocess_call.called_with(
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


async def test_connection_error(caplog):
    result = login("localhost", 993, "fakeuser", "suchfakemuchpassword")
    assert not result
    assert (
        "Network error while connecting to server: [Errno 111] Connection refused"
        in caplog.text
    )


async def test_login_error(mock_imap_login_error, caplog):
    login("localhost", 993, "fakeuser", "suchfakemuchpassword")
    assert "Error logging into IMAP Server:" in caplog.text


async def test_selectfolder_list_error(mock_imap_list_error, caplog):
    selectfolder(mock_imap_list_error, "somefolder")
    assert "Error listing folders:" in caplog.text


async def test_selectfolder_select_error(mock_imap_select_error, caplog):
    selectfolder(mock_imap_select_error, "somefolder")
    assert "Error selecting folder:" in caplog.text


async def test_resize_images_open_err(mock_open_excpetion, caplog):
    resize_images(["testimage.jpg", "anothertest.jpg"], 724, 320)
    assert "Error attempting to open image" in caplog.text


async def test_resize_images_read_err(mock_open, mock_image_excpetion, caplog):
    resize_images(["testimage.jpg", "anothertest.jpg"], 724, 320)
    assert "Error attempting to read image" in caplog.text


async def test_process_emails_random_image(hass, mock_imap_login_error, caplog):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_NO_RND,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    config = entry.data
    process_emails(hass, config)
    assert "Error logging into IMAP Server:" in caplog.text


# async def test_download_img(aioclient_mock):
#     with patch("aiohttp.ClientSession", return_value=aioclient_mock):
#         await download_img(
#             "http://fake.website.com/not/a/real/website/image.jpg", "/fake/directory/"
#         )
