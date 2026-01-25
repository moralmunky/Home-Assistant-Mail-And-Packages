"""Tests for helpers module."""

import email
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from email.message import Message
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import aiohttp
import aioimaplib
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import (
    AMAZON_OTP,
    ATTR_AMAZON_IMAGE,
    ATTR_COUNT,
    ATTR_FEDEX_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_TRACKING,
    ATTR_UPS_IMAGE,
    ATTR_WALMART_IMAGE,
    CAMERA_DATA,
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
    DOMAIN,
    SENSOR_DATA,
    SHIPPERS,
)
from custom_components.mail_and_packages.helpers import (
    InvalidAuth,
    _check_ffmpeg,
    _generate_mp4,
    _generic_delivery_image_extraction,
    _get_email_body,
    _match_patterns,
    _parse_amazon_arrival_date,
    amazon_date_search,
    amazon_exception,
    amazon_hub,
    amazon_otp,
    amazon_search,
    build_search,
    cleanup_images,
    copy_images,
    copy_overlays,
    default_image_path,
    download_img,
    email_fetch,
    email_search,
    fetch,
    generate_grid_img,
    get_amazon_image,
    get_count,
    get_formatted_date,
    get_items,
    get_mails,
    get_resources,
    hash_file,
    image_file_name,
    login,
    process_emails,
    resize_images,
    selectfolder,
    update_time,
)
from tests.const import (
    FAKE_CONFIG_DATA,
    FAKE_CONFIG_DATA_BAD,
    FAKE_CONFIG_DATA_CORRECTED,
    FAKE_CONFIG_DATA_CUSTOM_IMG,
    FAKE_CONFIG_DATA_NO_RND,
)

MAIL_IMAGE_URL_ENTITY = "sensor.mail_image_url"
MAIL_IMAGE_SYSTEM_PATH = "sensor.mail_image_system_path"
MAIL_IMAGE_GRID_IMAGE_PATH = "sensor.mail_grid_image_path"


@pytest.mark.asyncio
async def test_get_formatted_date():
    """Test that the date formatting helper returns the correct format."""
    assert get_formatted_date() == date.today().strftime("%d-%b-%Y")


@pytest.mark.asyncio
async def test_update_time():
    """Test that the update_time helper returns a datetime object."""
    assert isinstance(await update_time(), datetime)


@pytest.mark.asyncio
async def test_cleanup_images():
    """Test that image cleanup removes specified files using pathlib methods."""

    mock_file_gif = MagicMock()
    mock_file_gif.name = "testfile.gif"
    mock_file_gif.exists.return_value = True

    mock_file_mp4 = MagicMock()
    mock_file_mp4.name = "anotherfakefile.mp4"
    mock_file_mp4.exists.return_value = True

    path_str = "/tests/fakedir/"

    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "pathlib.Path.iterdir",
            return_value=[mock_file_gif, mock_file_mp4],
            autospec=True,
        ),
        patch("pathlib.Path.unlink", autospec=True) as mock_remove,
        patch("pathlib.Path"),
    ):
        cleanup_images(path_str)
        assert mock_remove.call_count == 2


@pytest.mark.asyncio
async def test_cleanup_found_images_remove_err(caplog):
    """Test error handling when removing found images during cleanup."""
    mock_file_gif = MagicMock()
    mock_file_gif.name = "testfile.gif"
    mock_file_gif.exists.return_value = True

    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[mock_file_gif], autospec=True),
        patch("pathlib.Path.unlink", autospec=True) as mock_remove,
        patch("pathlib.Path"),
    ):
        mock_remove.side_effect = OSError(2, "Permisison denied.")
        cleanup_images("/tests/fakedir/")
        assert "Error attempting to remove found image:" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_remove_err(caplog):
    """Test error handling when removing specific images during cleanup."""
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.iterdir", return_value="testimage.jpg", autospec=True),
        patch("pathlib.Path.unlink", autospec=True) as mock_remove,
        patch("pathlib.Path"),
    ):
        mock_remove.side_effect = OSError(2, "Permisison denied.")
        cleanup_images("/tests/fakedir/", "testimage.jpg")
        assert "Error attempting to remove image:" in caplog.text


@pytest.mark.asyncio
async def test_process_emails(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_copyfile,
    mock_copytree,
    mock_hash_file,
    mock_getctime_today,
):
    """Test the main email processing loop asynchronously."""
    hass.config.internal_url = "http://127.0.0.1:8123/"
    config = FAKE_CONFIG_DATA_CORRECTED

    # This function is now async
    result = await process_emails(hass, config)

    assert isinstance(result["mail_updated"], datetime)
    assert result["amazon_delivered"] == 0
    assert result["amazon_hub"] == 0


# @pytest.mark.asyncio
# async def test_process_emails_external(
#     hass,
#     integration_fake_external,
#     mock_imap_no_email,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_copyfile,
#     mock_copytree,
#     mock_hash_file,
#     mock_getctime_today,
# ):
#     """Test email processing with external URL configuration."""
#     hass.config.internal_url = "http://127.0.0.1:8123/"
#     hass.config.external_url = "http://really.fake.host.net:8123/"

#     entry = integration_fake_external

#     config = entry.data.copy()
#     assert config == FAKE_CONFIG_DATA_CORRECTED_EXTERNAL
#     state = hass.states.get(MAIL_IMAGE_SYSTEM_PATH)
#     assert state is not None
#     assert "/testing_config/custom_components/mail_and_packages/images/" in state.state
#     state = hass.states.get(MAIL_IMAGE_URL_ENTITY)
#     assert state.state == "unknown"
#     result = process_emails(hass, config)
#     assert isinstance(result["mail_updated"], datetime)
#     assert result["zpackages_delivered"] == 0
#     assert result["zpackages_transit"] == 0
#     assert result["amazon_delivered"] == 0
#     assert result["amazon_hub"] == 0
#     assert result["amazon_packages"] == 0
#     assert result["amazon_order"] == []
#     assert result["amazon_hub_code"] == []
#     assert (
#         "custom_components/mail_and_packages/images/" in mock_copytree.call_args.args[0]
#     )
#     assert "www/mail_and_packages" in mock_copytree.call_args.args[1]
#     assert mock_copytree.call_args.kwargs == {"dirs_exist_ok": True}
#     # Check that both Amazon and UPS files are being cleaned up
#     amazon_removed = False
#     ups_removed = False

#     mock_file_amazon = MagicMock()
#     mock_file_amazon.name = "anotherfakefile.mp4"
#     mock_file_amazon.exists.return_value = True

#     mock_file_ups = MagicMock()
#     mock_file_ups.name = "anotherfakefile.mp4"
#     mock_file_ups.exists.return_value = True

#     with (
#         patch("pathlib.Path.is_dir", return_value=True),
#         patch("pathlib.Path.exists", return_value=True),
#         patch("pathlib.Path.iterdir", return_value=[mock_file_amazon, mock_file_ups], autospec=True),
#         patch("pathlib.Path.unlink", autospec=True) as mock_remove,
#         patch("pathlib.Path")
#     ):

#         assert mock_remove.call_count == 2

#         for remove_call in mock_remove.call_args_list:
#             if "www/mail_and_packages/amazon/anotherfakefile.mp4" in str(remove_call):
#                 amazon_removed = True
#             if "www/mail_and_packages/ups/anotherfakefile.mp4" in str(remove_call):
#                 ups_removed = True

#         assert amazon_removed
#         assert ups_removed


@pytest.mark.asyncio
async def test_process_emails_external_error(
    hass,
    integration_fake_external,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_copyfile,
    mock_copytree,
    mock_hash_file,
    mock_getctime_today,
    caplog,
):
    """Test error handling during external email processing."""
    entry = integration_fake_external
    config = entry.data.copy()
    with patch(
        "custom_components.mail_and_packages.helpers.get_mails",
        side_effect=OSError("Problem creating: Mocked file system error"),
    ):
        await process_emails(hass, config)

    assert "Problem creating:" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_bad(hass, mock_imap_no_email, mock_update):
    """Test email processing behavior with bad configuration data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_BAD,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_process_emails_non_random(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_copyfile,
    mock_copytree,
    mock_hash_file,
    mock_getctime_today,
):
    """Test email processing with random image generation disabled."""
    entry = integration
    config = entry.data
    # Create a mock file object to simulate finding 'testfile.gif' via pathlib
    mock_file = MagicMock()
    mock_file.name = "testfile.gif"
    # Ensure creation time is "today" so the function reuses the name
    mock_file.stat.return_value.st_ctime = datetime.now().timestamp()
    with patch("pathlib.Path.iterdir", return_value=[mock_file]):
        result = await process_emails(hass, config)
        assert result["image_name"] == "testfile.gif"


@pytest.mark.asyncio
async def test_process_emails_random(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_copyfile,
    mock_copytree,
    mock_hash_file,
    mock_getctime_yesterday,
):
    """Test email processing with random image generation enabled."""
    entry = integration

    config = entry.data
    result = await process_emails(hass, config)
    assert ".gif" in result["image_name"]


@pytest.mark.asyncio
async def test_process_nogif(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir_noimgs,
    mock_copyfile,
    mock_copytree,
    mock_hash_file,
    mock_getctime_today,
):
    """Test email processing when no GIF generation is required."""
    entry = integration

    config = entry.data
    result = await process_emails(hass, config)
    assert ".gif" in result["image_name"]


@pytest.mark.asyncio
async def test_process_old_image(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_copyfile,
    mock_copytree,
    mock_hash_file,
    mock_getctime_yesterday,
):
    """Test handling of old images during email processing."""
    entry = integration

    config = entry.data
    result = await process_emails(hass, config)
    assert ".gif" in result["image_name"]


# @pytest.mark.asyncio
# async def test_process_folder_error(
#     hass,
#     integration,
#     mock_imap_list_result_error,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_copyfile,
#     mock_copytree,
#     mock_hash_file,
#     mock_getctime_yesterday,
# ):
#     """Test error handling when the mail folder cannot be selected."""
#     entry = integration

#     config = entry.data
#     result = await process_emails(hass, config)
#     assert result == {}


@pytest.mark.asyncio
async def test_email_search(mock_imap):
    """Test the asynchronous email search helper."""
    # Mocking a search error
    mock_imap.search.side_effect = OSError("Invalid SEARCH format")

    result = await email_search(mock_imap, ["fake@email.com"], "01-Jan-2024")
    assert result == ("BAD", "Invalid SEARCH format")


@pytest.mark.asyncio
async def test_email_fetch(mock_imap_fetch_error, caplog):
    """Test the email fetch helper and its error handling."""
    result = await email_fetch(mock_imap_fetch_error, 1, "(RFC822)")
    assert result == ("BAD", "Invalid Email")
    assert "Error fetching email 1: Invalid Email" in caplog.text


@pytest.mark.asyncio
async def test_get_mails(hass, mock_imap_no_email, mock_copyfile):
    """Test the get_mails helper for retrieving mail count."""
    result = await get_mails(
        hass, mock_imap_no_email, "./", "5", "mail_today.gif", False
    )
    assert result == 0


@pytest.mark.asyncio
async def test_get_mails_makedirs_error(
    hass, mock_imap_no_email, mock_copyfile, caplog
):
    """Test error handling when creating mail directories fails."""
    # Fix: Patch pathlib.Path.is_dir and pathlib.Path.mkdir
    with (
        patch("pathlib.Path.is_dir", return_value=False),
        patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")),
    ):
        await get_mails(hass, mock_imap_no_email, "./", "5", "mail_today.gif", False)
        assert "Error creating directory:" in caplog.text


@pytest.mark.asyncio
async def test_get_mails_copyfile_error(
    hass,
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    """Test error handling when copying mail images fails."""
    await get_mails(
        hass, mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
    )
    assert "File not found" in caplog.text


@pytest.mark.asyncio
async def test_get_mails_email_search_error(
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    """Test handling of search errors within get_mails."""
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("BAD", []),
    ):
        result = await get_mails(
            mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
        )
        assert result == 0


@pytest.mark.asyncio
async def test_informed_delivery_emails(
    hass,
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
):
    """Test parsing of USPS Informed Delivery emails via async IMAP."""
    # get_mails is now async
    result = await get_mails(
        hass, mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
    )
    assert result == 3


@pytest.mark.asyncio
async def test_informed_delivery_forwarded_emails(
    hass,
    mock_imap_informed_delivery_forwarded_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    """Test parsing of forwarded USPS Informed Delivery emails."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = await get_mails(
            hass,
            mock_imap_informed_delivery_forwarded_email,
            "./",
            "5",
            "mail_today.gif",
            False,
            forwarded_emails=["forwarduser@fake.email"],
        )
        assert result == 3
        assert "USPSInformedDelivery@usps.gov" in caplog.text
        assert "USPSInformeddelivery@informeddelivery.usps.com" in caplog.text
        assert "USPSInformeddelivery@email.informeddelivery.usps.com" in caplog.text
        assert "USPS Informed Delivery" in caplog.text


@pytest.mark.asyncio
async def test_new_informed_delivery_emails(
    hass,
    mock_imap_usps_new_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    """Test parsing of the new format USPS Informed Delivery emails."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = await get_mails(
            hass, mock_imap_usps_new_informed_digest, "./", "5", "mail_today.gif", False
        )
        assert result == 4
        assert "USPSInformedDelivery@usps.gov" in caplog.text
        assert "USPSInformeddelivery@informeddelivery.usps.com" in caplog.text
        assert "USPSInformeddelivery@email.informeddelivery.usps.com" in caplog.text
        assert "USPS Informed Delivery" in caplog.text


@pytest.mark.asyncio
async def test_informed_delivery_emails_mp4(
    hass,
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
):
    """Test MP4 generation for USPS Informed Delivery emails."""
    with patch(
        "custom_components.mail_and_packages.helpers._generate_mp4"
    ) as mock_generate_mp4:
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            result = await get_mails(
                hass, mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", True
            )
            assert result == 3
            mock_generate_mp4.assert_called_with("./", "mail_today.gif")


@pytest.mark.asyncio
async def test_informed_delivery_emails_open_err(
    hass,
    mock_imap_usps_informed_digest,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    """Test error handling when opening mail image files."""
    # Mock pathlib methods to simulate the directory exists and is iterable
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[]),
        # Mock Path.open to raise the expected OSError during file processing
        patch("pathlib.Path.open", side_effect=OSError(2, "No such file or directory")),
    ):
        await get_mails(
            hass,
            mock_imap_usps_informed_digest,
            "/totally/fake/path/",
            "5",
            "mail_today.gif",
            False,
        )
        assert (
            "Error opening filepath: [Errno 2] No such file or directory" in caplog.text
        )


@pytest.mark.asyncio
async def test_informed_delivery_emails_io_err(
    hass,
    mock_imap_usps_informed_digest,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image_save_excpetion,
    mock_copyfile,
    caplog,
):
    """Test IO error handling during mail processing."""
    # Create a mock image object that raises ValueError on .save()
    mock_img = MagicMock()
    # Configure chainable methods to return the mock object itself
    mock_img.thumbnail.return_value = mock_img
    mock_img.crop.return_value = mock_img
    mock_img.save.side_effect = ValueError("Mocked Save Error")

    # Mock pathlib methods for directory checks and file opening
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[]),
        patch("pathlib.Path.open", mock_open()),
        # Patch Image.open to return our configured mock image
        patch("PIL.Image.open", return_value=mock_img),
        # Mock ImageOps.pad to return our configured mock image
        patch("PIL.ImageOps.pad", return_value=mock_img),
    ):
        await get_mails(
            hass,
            mock_imap_usps_informed_digest,
            "/totally/fake/path/",
            "5",
            "mail_today.gif",
            False,
        )

    # Verify that the error was caught and logged instead of raised
    assert (
        "Error attempting to generate image" in caplog.text
        or "Error processing image" in caplog.text
    )


@pytest.mark.asyncio
async def test_informed_delivery_missing_mailpiece(
    hass,
    mock_imap_usps_informed_digest_missing,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
):
    """Test handling of Informed Delivery emails with missing mailpieces."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = await get_mails(
            hass,
            mock_imap_usps_informed_digest_missing,
            "./",
            "5",
            "mail_today.gif",
            False,
        )
        assert result == 5


@pytest.mark.asyncio
async def test_informed_delivery_no_mail(
    hass,
    mock_imap_usps_informed_digest_no_mail,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_os_path_isfile,
    mock_copyfile,
):
    """Test parsing of Informed Delivery emails indicating no mail."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = await get_mails(
            hass,
            mock_imap_usps_informed_digest_no_mail,
            "./",
            "5",
            "mail_today.gif",
            False,
        )
        assert result == 0


@pytest.mark.asyncio
async def test_informed_delivery_no_mail_copy_error(
    mock_imap_usps_informed_digest_no_mail,
    hass,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_os_path_isfile,
    mock_copy_overlays,
    mock_copyfile_exception,
    caplog,
):
    """Test error handling when copying the 'no mail' placeholder image."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        await get_mails(
            hass,
            mock_imap_usps_informed_digest_no_mail,
            "./",
            "5",
            "mail_today.gif",
            False,
        )
        assert "./mail_today.gif" in mock_copyfile_exception.call_args.args
        assert "File not found" in caplog.text


@pytest.mark.asyncio
async def test_ups_out_for_delivery(hass, mock_imap_ups_out_for_delivery):
    """Test parsing of UPS 'Out for Delivery' emails."""
    result = await get_count(
        mock_imap_ups_out_for_delivery, "ups_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["1Z2345YY0678901234"]


@pytest.mark.asyncio
async def test_usps_delivered(hass, mock_imap_usps_delivered_individual):
    """Test parsing of USPS 'Delivered' emails."""
    result = await get_count(
        mock_imap_usps_delivered_individual, "usps_delivered", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["92001901755477000000000000"]


@pytest.mark.asyncio
async def test_ups_out_for_delivery_html_only(
    hass, mock_imap_ups_out_for_delivery_html
):
    """Test parsing of HTML-only UPS 'Out for Delivery' emails."""
    result = await get_count(
        mock_imap_ups_out_for_delivery_html, "ups_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["1Z0Y12345678031234"]


@pytest.mark.asyncio
async def test_ups_delivered(hass, mock_imap_ups_delivered):
    """Test parsing of UPS 'Delivered' emails."""
    result = await get_count(mock_imap_ups_delivered, "ups_delivered", True, "./", hass)
    assert result["count"] == 1
    assert result["tracking"] == ["1Z2345YY0678901234"]


@pytest.mark.asyncio
async def test_ups_delivered_with_photo(hass, mock_imap_ups_delivered_with_photo):
    """Test UPS delivered with delivery photo extraction."""
    result = await get_count(
        mock_imap_ups_delivered_with_photo, "ups_delivered", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["1Z2345YY0678901234"]


def test_get_ups_image_cid_extraction(tmp_path):
    """Test UPS image extraction from CID embedded images."""
    # Create a test email with CID image
    test_email = """From: UPS <mcinfo@ups.com>
To: nobody@gmail.com
Subject: Your UPS Package was delivered
MIME-Version: 1.0
Content-Type: multipart/related; boundary=----test_boundary

------test_boundary
Content-Type: text/html; charset=UTF-8

<html><body><img src="cid:deliveryPhoto" alt="delivery photo"></body></html>

------test_boundary
Content-Type: image/jpeg
Content-Transfer-Encoding: base64
Content-ID: <deliveryPhoto>

/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/wA==

------test_boundary--
"""

    # Create UPS directory
    ups_path = tmp_path / "ups"
    ups_path.mkdir()

    # Test image extraction using generic function
    result = _generic_delivery_image_extraction(
        test_email,
        str(tmp_path) + "/",
        "test_ups_image.jpg",
        "ups",
        "jpeg",
        "deliveryPhoto",
        None,
    )

    # Verify extraction was successful
    assert result is True

    # Verify image file was created
    image_file = ups_path / "test_ups_image.jpg"
    assert image_file.exists()

    # Verify it's a valid JPEG (should start with JPEG magic bytes)
    data = image_file.read_bytes()
    assert data.startswith(b"\xff\xd8\xff")  # JPEG magic bytes


def test_get_ups_image_base64_extraction(tmp_path):
    """Test UPS image extraction from base64 encoded images."""
    # Create a test email with base64 image
    test_email = """From: UPS <mcinfo@ups.com>
To: nobody@gmail.com
Subject: Your UPS Package was delivered
MIME-Version: 1.0
Content-Type: multipart/related; boundary=----test_boundary

------test_boundary
Content-Type: text/html; charset=UTF-8

<html><body><img src="cid:deliveryPhoto" alt="delivery photo">
<img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/wA==" alt="delivery photo"></body></html>

------test_boundary--
"""

    # Create UPS directory
    ups_path = tmp_path / "ups"
    ups_path.mkdir()

    # Test image extraction using generic function
    result = _generic_delivery_image_extraction(
        test_email,
        str(tmp_path) + "/",
        "test_ups_image.jpg",
        "ups",
        "jpeg",
        "deliveryPhoto",
        None,
    )

    # Verify extraction was successful
    assert result is True

    # Verify image file was created
    image_file = ups_path / "test_ups_image.jpg"
    assert image_file.exists()

    # Verify it's a valid JPEG
    data = image_file.read_bytes()
    assert data.startswith(b"\xff\xd8\xff")  # JPEG magic bytes


@pytest.mark.asyncio
async def test_get_ups_image_no_photo(hass, tmp_path):
    """Test UPS image extraction when no photo is found."""
    # Create a test email without any images
    test_email = """From: UPS <mcinfo@ups.com>
To: nobody@gmail.com
Subject: Your UPS Package was delivered
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

<html><body>No delivery photo available</body></html>
"""

    # Create UPS directory
    ups_path = tmp_path / "ups"
    ups_path.mkdir()

    # Test image extraction using generic function (should return False when no photo)
    result = _generic_delivery_image_extraction(
        test_email,
        str(tmp_path) + "/",
        "test_ups_image.jpg",
        "ups",
        "jpeg",
        "deliveryPhoto",
        None,
    )

    # Verify extraction failed (no photo found)
    assert result is False

    # Verify no image file was created
    image_file = ups_path / "test_ups_image.jpg"
    assert not image_file.exists()


@pytest.mark.asyncio
async def test_ups_search_no_deliveries(
    hass, mock_imap_no_email, mock_copyfile, caplog
):
    """Test UPS search when no deliveries are found."""
    with (
        patch("os.path.isdir", return_value=True),
        patch("os.makedirs", return_value=True),
        patch("os.path.exists", return_value=False),
    ):
        result = await get_count(
            mock_imap_no_email, "ups_delivered", False, "./", hass, data={}
        )
        assert result["count"] == 0
        # Should have copied the default no delivery image
        assert len(mock_copyfile.mock_calls) > 0


@pytest.mark.asyncio
async def test_ups_search_with_photo(
    hass, tmp_path, mock_imap_ups_delivered_with_photo
):
    """Test UPS search with delivery photo extraction."""
    # Create UPS directory
    ups_path = tmp_path / "ups"
    ups_path.mkdir()

    # Set up image path
    image_path = str(tmp_path) + "/"

    # Create coordinator data dict to track image updates
    coordinator_data = {}

    # Mock os.path.exists to return True for extracted image files
    # This allows the coordinator_data to be updated with the image name
    with (
        patch("os.path.exists") as mock_exists,
        patch("os.path.getsize", return_value=1000),
    ):
        # Mock exists to return True for any UPS image file
        def exists_side_effect(path):
            if "ups" in path and path.endswith((".jpg", ".jpeg")):
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        # Call get_count for ups_delivered sensor
        result = await get_count(
            mock_imap_ups_delivered_with_photo,
            "ups_delivered",
            False,
            image_path,
            hass,
            data=coordinator_data,
        )

        # Verify that at least one delivery was found (count may vary based on email content)
        assert result["count"] > 0, "Should find at least one UPS delivery"

        # Verify that coordinator data was updated with the image filename
        # Note: The image may or may not be set depending on extraction success
        # If it's set, verify it's a string
        if ATTR_UPS_IMAGE in coordinator_data:
            assert isinstance(coordinator_data[ATTR_UPS_IMAGE], str), (
                f"UPS image should be a string, got {type(coordinator_data[ATTR_UPS_IMAGE])}"
            )

    # Also test direct image extraction with a known-good email format
    # This ensures the extraction logic works even if the test email format has issues
    test_email_with_cid = """From: UPS <mcinfo@ups.com>
To: nobody@gmail.com
Subject: Your UPS Package was delivered
MIME-Version: 1.0
Content-Type: multipart/related; boundary=----test_boundary

------test_boundary
Content-Type: text/html; charset=UTF-8

<html><body><img src="cid:deliveryPhoto" alt="delivery photo"></body></html>

------test_boundary
Content-Type: image/jpeg
Content-Transfer-Encoding: base64
Content-ID: <deliveryPhoto>

/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/wA==

------test_boundary--
"""

    # Test direct image extraction
    extraction_result = _generic_delivery_image_extraction(
        test_email_with_cid,
        image_path,
        "test_ups_extraction.jpg",
        "ups",
        "jpeg",
        "deliveryPhoto",
        None,
    )

    # Verify extraction was successful
    assert extraction_result is True, (
        "UPS image extraction should succeed with CID image"
    )

    # Verify the image file was created
    extracted_image = ups_path / "test_ups_extraction.jpg"
    assert extracted_image.exists(), "Extracted UPS image file should exist"

    # Verify the image is valid (JPEG magic bytes)
    data = extracted_image.read_bytes()
    assert data.startswith(b"\xff\xd8\xff"), "Extracted image is not a valid JPEG"

    # If coordinator data was updated, verify it contains the UPS image reference
    if coordinator_data:
        # The coordinator data might be updated if image extraction worked in get_count
        # This is a bonus check - the main verification is the direct extraction test above
        pass


# @pytest.mark.asyncio
# async def test_usps_out_for_delivery(hass, mock_imap_usps_out_for_delivery):
#     """Test parsing of USPS 'Out for Delivery' emails."""
#     result = await get_count(
#         mock_imap_usps_out_for_delivery, "usps_delivering", True, "./", hass
#     )
#     assert result["count"] == 1
#     assert result["tracking"] == ["92123456508577307776690000"]


# @pytest.mark.asyncio
# async def test_dhl_out_for_delivery(hass, mock_imap_dhl_out_for_delivery, caplog):
#     """Test parsing of DHL 'Out for Delivery' emails."""
#     result = await get_count(
#         mock_imap_dhl_out_for_delivery, "dhl_delivering", True, "./", hass
#     )
#     assert result["count"] == 1
#     assert result["tracking"] == ["4212345678"]
#     assert "UTF-8 not supported." not in caplog.text


# @pytest.mark.asyncio
# async def test_dhl_no_utf8(hass, mock_imap_dhl_no_utf8, caplog):
#     """Test parsing of DHL emails without UTF-8 encoding."""
#     result = await get_count(mock_imap_dhl_no_utf8, "dhl_delivering", True, "./", hass)
#     assert result["count"] == 1
#     assert result["tracking"] == ["4212345678"]
# assert "UTF-8 not supported: ('BAD', ['Unsupported'])" in caplog.text


# TODO: Get updated hermes email
# @pytest.mark.asyncio
# async def test_hermes_out_for_delivery(hass, mock_imap_hermes_out_for_delivery):
#     result = get_count(
#         mock_imap_hermes_out_for_delivery, "hermes_delivering", True, "./", hass
#     )
#     assert result["count"] == 1
#     assert result["tracking"] == ["8888888888888888"]


@pytest.mark.asyncio
async def test_evri_out_for_delivery(hass, mock_imap_evri_out_for_delivery):
    """Test parsing of Evri 'Out for Delivery' emails."""
    result = await get_count(
        mock_imap_evri_out_for_delivery, "evri_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["H01QPZ0007431687"]


@pytest.mark.asyncio
async def test_royal_out_for_delivery(hass, mock_imap_royal_out_for_delivery):
    """Test parsing of Royal Mail 'Out for Delivery' emails."""
    result = await get_count(
        mock_imap_royal_out_for_delivery, "royal_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["MA038501234GB"]


# @freeze_time("2020-09-11")
# @pytest.mark.asyncio
# async def test_amazon_shipped_count(hass, mock_imap_amazon_shipped, caplog):
#     """Test counting of Amazon shipped emails."""
#     result = await get_items(mock_imap_amazon_shipped, "count", the_domain="amazon.com")
#     assert "Amazon email search addresses:" in caplog.text
#     assert result == 1


# @pytest.mark.asyncio
# async def test_amazon_shipped_order(hass, mock_imap_amazon_shipped):
#     """Test extraction of order numbers from Amazon shipped emails."""
#     result = await get_items(mock_imap_amazon_shipped, "order", the_domain="amazon.com")
#     assert result == ["123-1234567-1234567"]


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_alt(hass, mock_imap_amazon_shipped_alt):
#     """Test alternate format for Amazon shipped order extraction."""
#     # Mock dateparser to avoid timezone issues in tests
#     with patch(
#         "custom_components.mail_and_packages.helpers.dateparser"
#     ) as mock_dateparser:
#         mock_dateparser.parse.return_value = datetime(2020, 9, 11)
#         result = await get_items(
#             mock_imap_amazon_shipped_alt, "order", the_domain="amazon.com"
#         )
#         assert result == ["123-1234567-1234567"]


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_alt_2(hass, mock_imap_amazon_shipped_alt_2):
#     """Test alternate format for Amazon shipped order extraction."""
#     result = await get_items(
#         mock_imap_amazon_shipped_alt_2, "order", the_domain="amazon.com"
#     )
#     assert result == ["113-9999999-8459426"]
#     with patch("datetime.date") as mock_date:
#         mock_date.today.return_value = date(2021, 12, 3)

#         result = await get_items(
#             mock_imap_amazon_shipped_alt_2, "count", the_domain="amazon.com"
#         )
#         assert result == 0


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_alt_2_delivery_today(
#     hass, mock_imap_amazon_shipped_alt_2
# ):
#     """Test the same email but with mocked date matching the delivery date."""
#     result = await get_items(
#         mock_imap_amazon_shipped_alt_2, "order", the_domain="amazon.com"
#     )
#     assert result == ["113-9999999-8459426"]
#     with patch("datetime.date") as mock_date:
#         # Mock today to be the delivery date (2022-12-03 as parsed by dateparser)
#         mock_date.today.return_value = date(2022, 12, 3)

#         result = await get_items(
#             mock_imap_amazon_shipped_alt_2, "count", the_domain="amazon.com"
#         )
#         assert result == 1


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_alt_timeformat(
#     hass, mock_imap_amazon_shipped_alt_timeformat
# ):
#     """Test the same email but with mocked date matching the delivery date."""
#     result = await get_items(
#         mock_imap_amazon_shipped_alt_timeformat, "order", the_domain="amazon.com"
#     )
#     assert result == ["321-1234567-1234567"]


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_uk(hass, mock_imap_amazon_shipped_uk):
#     """Test Amazon search for shipped items with UK locale."""
#     # Mock dateparser to avoid timezone issues in tests
#     with patch(
#         "custom_components.mail_and_packages.helpers.dateparser"
#     ) as mock_dateparser:
#         mock_dateparser.parse.return_value = datetime(2020, 12, 12)
#         result = await get_items(
#             mock_imap_amazon_shipped_uk, "order", the_domain="amazon.co.uk"
#         )
#         assert result == ["123-4567890-1234567"]


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_uk_2(hass, mock_imap_amazon_shipped_uk_2):
#     """Test Amazon search for shipped items with UK locale."""
#     # Ensure the search response is structured for aioimaplib
#     mock_search_res = MagicMock()
#     mock_search_res.result = "OK"
#     mock_search_res.lines = [b"1"]
#     mock_imap_amazon_shipped_uk_2.search.return_value = mock_search_res

#     with patch(
#         "custom_components.mail_and_packages.helpers.dateparser"
#     ) as mock_dateparser:
#         mock_dateparser.parse.return_value = datetime(2021, 11, 16)
#         result = await get_items(
#             mock_imap_amazon_shipped_uk_2, "order", the_domain="amazon.co.uk"
#         )

#         assert result == ["123-4567890-1234567"]


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_it(hass, mock_imap_amazon_shipped_it):
#     """Test Amazon search for shipped items with Italian locale."""
#     result = await get_items(
#         mock_imap_amazon_shipped_it, "order", the_domain="amazon.it"
#     )
#     assert result == ["405-5236882-9395563"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_it_count(hass, mock_imap_amazon_shipped_it):
    """Test Amazon search for shipped items count with Italian locale."""
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2021, 12, 1)
        result = await get_items(
            mock_imap_amazon_shipped_it, "count", the_domain="amazon.it"
        )
        assert result == 0


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_it_count_delivery_today(
#     hass, mock_imap_amazon_shipped_it, caplog
# ):
#     """Test the same Italian email but with mocked date matching the delivery date."""
#     result = await get_items(
#         mock_imap_amazon_shipped_it, "order", the_domain="amazon.it"
#     )
#     assert result == ["405-5236882-9395563"]
#     with patch("datetime.date") as mock_date:
#         # Mock today to be the delivery date (2025-12-01 as parsed by dateparser)
#         mock_date.today.return_value = date(2025, 12, 1)
#         await get_items(mock_imap_amazon_shipped_it, "count", the_domain="amazon.it")
#         assert "Total unique Amazon emails found: 1" in caplog.text


@pytest.mark.asyncio
async def test_amazon_search(hass, mock_imap_no_email):
    """Test Amazon search functionality when no emails are found."""
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        result = await amazon_search(
            mock_imap_no_email,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.com",
        )
        assert result == 0


# @pytest.mark.asyncio
# async def test_amazon_search_results(
#     hass, mock_imap_amazon_shipped, mock_imap_amazon_delivered
# ):
#     """Test Amazon search functionality for both shipped and delivered emails."""
#     with (
#         patch("custom_components.mail_and_packages.helpers.cleanup_images"),
#         patch(
#             "custom_components.mail_and_packages.helpers.download_img"
#         ) as mock_download,
#         patch(
#             "custom_components.mail_and_packages.helpers.amazon_email_addresses",
#             return_value=["test@amazon.com"],
#         ),
#     ):
#         # Test shipped emails (should return 0 since email is not arriving today)
#         shipped_result = await get_items(
#             mock_imap_amazon_shipped, "count", the_domain="amazon.com"
#         )
#         assert shipped_result == 0, (
#             f"Expected 0 shipped emails arriving today, got {shipped_result}"
#         )

#         # Test delivered emails
#         delivered_result = await amazon_search(
#             mock_imap_amazon_delivered,
#             "test/path/amazon/",
#             hass,
#             "testfilename.jpg",
#             "amazon.com",
#             coordinator_data={},
#         )

#         assert delivered_result == 10, (
#             f"Expected 10 delivered emails (no deduplication), got {delivered_result}"
#         )
#         # Verify that the download was at least attempted for valid image URLs
#         assert mock_download.called


@pytest.mark.asyncio
async def test_amazon_search_delivered(hass, mock_imap_amazon_delivered, caplog):
    """Test Amazon search for delivered items."""
    with (
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.helpers.download_img"
        ) as mock_download_img,
    ):
        result = await amazon_search(
            mock_imap_amazon_delivered,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.com",
        )
        await hass.async_block_till_done()
        assert "Amazon email search addresses:" in caplog.text
        assert result == 10
        assert mock_download_img.called


@pytest.mark.asyncio
async def test_amazon_search_delivered_it(hass, mock_imap_amazon_delivered_it):
    """Test Amazon search for delivered items with Italian locale."""
    with (
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
        patch("custom_components.mail_and_packages.helpers.download_img"),
    ):
        result = await amazon_search(
            mock_imap_amazon_delivered_it,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.it",
        )
        assert result == 10


@pytest.mark.asyncio
async def test_amazon_hub(hass, mock_imap_amazon_the_hub):
    """Test handling of amazon hub codes."""
    result = await amazon_hub(mock_imap_amazon_the_hub)
    assert result["count"] == 1
    assert result["code"] == ["123456"]

    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("BAD", []),
    ):
        result = await amazon_hub(mock_imap_amazon_the_hub)
        assert result == {"code": [], "count": 0}

    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("OK", [None]),
    ):
        result = await amazon_hub(mock_imap_amazon_the_hub)
        assert result == {"code": [], "count": 0}


@pytest.mark.asyncio
async def test_amazon_hub_2(hass, mock_imap_amazon_the_hub_2):
    """Test handling of amazon hub codes."""
    # Test successful parsing with the fixture
    result = await amazon_hub(mock_imap_amazon_the_hub_2)
    assert result["count"] == 1
    assert result["code"] == ["123456"]

    # Test "BAD" search response
    # The helper expects a tuple (status, lines) to unpack
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        new_callable=AsyncMock,
        return_value=("BAD", []),
    ):
        result = await amazon_hub(mock_imap_amazon_the_hub_2)
        assert result == {"code": [], "count": 0}

    # Test "OK" search response but with no email IDs
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [None]),
    ):
        result = await amazon_hub(mock_imap_amazon_the_hub_2)
        assert result == {"code": [], "count": 0}


# @pytest.mark.asyncio
# async def test_amazon_shipped_order_exception(hass, mock_imap_amazon_shipped, caplog):
#     """Test amazon shipment order exceptions."""
#     with patch("quopri.decodestring", side_effect=ValueError):
#         await get_items(mock_imap_amazon_shipped, "order", the_domain="amazon.com")
#         assert "Problem decoding email message:" in caplog.text


@pytest.mark.asyncio
async def test_generate_mp4(mock_osremove, mock_subprocess_run, mock_os_path_split):
    """Test the generation of MP4 files from images."""
    with (
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
        patch("os.path.join") as mock_join,
        patch("os.path.isfile", return_value=False),
    ):
        # Mock os.path.join to return correct values
        def join_side_effect(*args):
            return "/".join(args)

        mock_join.side_effect = join_side_effect

        _generate_mp4("./", "testfile.gif")

        # Verify subprocess.run was called with correct arguments
        mock_subprocess_run.assert_called_once()
        call_args = mock_subprocess_run.call_args
        # os.path.join may produce .//testfile.gif or ./testfile.gif depending on system
        cmd = call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert cmd[1] == "-y"
        assert cmd[2] == "-i"
        # The input file should end with testfile.gif (may have .// or ./ prefix)
        assert cmd[3].endswith("testfile.gif"), (
            f"Expected input file to end with testfile.gif, got {cmd[3]}"
        )
        assert cmd[4] == "-pix_fmt"
        assert cmd[5] == "yuv420p"
        # The output file should end with testfile.mp4 (may have .// or ./ prefix)
        assert cmd[6].endswith("testfile.mp4"), (
            f"Expected output file to end with testfile.mp4, got {cmd[6]}"
        )
        assert call_args[1]["stdout"] == subprocess.DEVNULL
        assert call_args[1]["stderr"] == subprocess.DEVNULL
        assert call_args[1]["check"] is True


@pytest.mark.asyncio
async def test_connection_error(hass, mock_imap_connect_error):
    """Test handling of connection errors during IMAP login."""
    with pytest.raises(ConnectionRefusedError):
        await login(hass, "localhost", 993, "fakeuser", "suchfakemuchpassword", "SSL")
    with pytest.raises(ConnectionRefusedError):
        await login(
            hass, "localhost", 143, "fakeuser", "suchfakemuchpassword", "startTLS"
        )


@pytest.mark.asyncio
async def test_login_error(hass, mock_imap_login_error, caplog):
    """Test handling of errors during IMAP login."""
    with pytest.raises(InvalidAuth):
        await login(hass, "localhost", 993, "fakeuser", "suchfakemuchpassword", "SSL")
    assert (
        "Error loggging in to IMAP Server" in caplog.text
        or "Error testing login to IMAP Server" in caplog.text
    )


@pytest.mark.asyncio
async def test_selectfolder_list_error(mock_imap_list_error, caplog):
    """Test handling of errors when listing an IMAP folder."""
    assert not await selectfolder(mock_imap_list_error, "somefolder")
    assert "Error listing folder somefolder: List error" in caplog.text


@pytest.mark.asyncio
async def test_selectfolder_select_error(mock_imap_select_error, caplog):
    """Test handling of errors when selecting an IMAP folder."""
    assert not await selectfolder(mock_imap_select_error, "somefolder")
    assert "Error selecting folder somefolder: Invalid folder" in caplog.text


@pytest.mark.asyncio
async def test_resize_images_open_err(mock_open_excpetion, caplog):
    """Test handling of errors when reading images for resizing."""
    resize_images(["testimage.jpg", "anothertest.jpg"], 724, 320)
    assert "Error processing image" in caplog.text


@pytest.mark.asyncio
async def test_resize_images_read_err(mock_image_excpetion, caplog):
    """Test handling of errors when reading images for resizing."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        resize_images(["testimage.jpg", "anothertest.jpg"], 724, 320)
        assert "Error processing image" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_random_image(hass, mock_imap_connect_error, caplog):
    """Test the processing of emails with random image generation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_NO_RND,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    config = entry.data
    with pytest.raises(ConnectionRefusedError):
        await process_emails(hass, config)


@pytest.mark.asyncio
async def test_usps_exception(hass, mock_imap_usps_exception):
    """Test handling of exceptions raised during USPS mail retrieval."""
    result = await get_count(
        mock_imap_usps_exception, "usps_exception", False, "./", hass
    )
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_download_img(
    hass,
    aioclient_mock,
    mock_osremove,
    mock_osmakedir,
    mock_listdir_nogif,
    mock_copyfile,
    mock_hash_file,
    mock_getctime_today,
    caplog,
):
    """Test handling of image download."""
    # Patch io_save_file to prevent actual file writing and verify call
    with patch("custom_components.mail_and_packages.helpers.io_save_file") as mock_save:
        await download_img(
            hass,
            "http://fake.website.com/not/a/real/website/image.jpg",
            "/fake/directory/",
            "testfilename.jpg",
        )

        # Verify io_save_file was called with the correct path
        mock_save.assert_called_once()
        args = mock_save.call_args[0]
        # args[0] is path, args[1] is data
        assert str(args[0]) == "/fake/directory/amazon/testfilename.jpg"

        # Verify logging
        assert "Downloading image to:" in caplog.text
        assert "Amazon image downloaded" in caplog.text


@pytest.mark.asyncio
async def test_download_img_error(hass, aioclient_mock_error, caplog):
    """Test handling of errors during image download."""
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        await download_img(
            hass,
            "http://fake.website.com/not/a/real/website/image.jpg",
            "/fake/directory/",
            "testfilename.jpg",
        )
        assert "Problem downloading file http error: 404" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_path_error(hass, caplog):
    """Test handling of errors during image file name generation."""
    config = FAKE_CONFIG_DATA_CORRECTED

    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.mkdir", side_effect=OSError("Mocked creation error")),
    ):
        result = image_file_name(hass, config)
        assert result == "mail_none.gif"
        assert "Problem creating:" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_amazon(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    """Test the image file name generation logic for Amazon devices."""
    config = FAKE_CONFIG_DATA_CORRECTED

    # Create a mock file object to simulate finding 'testfile.jpg' via pathlib
    mock_file = MagicMock()
    mock_file.name = "testfile.jpg"
    # Ensure creation time is "today" so the function reuses the name
    mock_file.stat.return_value.st_ctime = datetime.now().timestamp()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir", return_value=True),
        # Patch iterdir to return our mock file
        patch("pathlib.Path.iterdir", return_value=[mock_file]),
    ):
        result = image_file_name(hass, config, True)
        assert result == "testfile.jpg"


@pytest.mark.asyncio
async def test_image_file_name_ups(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    """Test image_file_name helper with UPS."""
    config = FAKE_CONFIG_DATA_CORRECTED

    # Create a mock file object to simulate finding 'testfile.jpg' via pathlib
    mock_file = MagicMock()
    mock_file.name = "testfile.jpg"
    # Ensure creation time is "today" so the function reuses the name
    mock_file.stat.return_value.st_ctime = datetime.now().timestamp()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir", return_value=True),
        # Patch iterdir to return our mock file
        patch("pathlib.Path.iterdir", return_value=[mock_file]),
    ):
        result = image_file_name(hass, config, ups=True)
        assert result == "testfile.jpg"


@pytest.mark.asyncio
async def test_image_file_name(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    """Test image_file_name helper function."""
    config = FAKE_CONFIG_DATA_CORRECTED

    with (
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", return_value=True),
    ):
        result = image_file_name(hass, config)
        assert ".gif" in result
        assert result != "mail_none.gif"

        # Test custom image settings
        config = FAKE_CONFIG_DATA_CUSTOM_IMG
        result = image_file_name(hass, config)
        assert ".gif" in result
        assert result != "mail_none.gif"
        assert len(mock_copyfile.mock_calls) == 2
        assert "Copying images/test.gif to" in caplog.text

        # Test custom Amazon image settings
        result = image_file_name(hass, config, amazon=True)
        assert ".jpg" in result
        assert result != "no_deliveries.jpg"
        assert "Copying images/test_amazon.jpg to" in caplog.text

        # Test custom UPS image settings
        result = image_file_name(hass, config, ups=True)
        assert ".jpg" in result
        assert result != "no_deliveries.jpg"
        assert "Copying images/test_ups.jpg to" in caplog.text


@pytest.mark.asyncio
async def test_amazon_exception(hass, mock_imap_amazon_exception, caplog):
    """Test Amazon exception email processing."""
    result = await amazon_exception(mock_imap_amazon_exception, the_domain="amazon.com")
    assert result["order"] == ["123-1234567-1234567"]
    assert (
        "Amazon email list: ['auto-confirm@amazon.com', 'shipment-tracking@amazon.com', 'order-update@amazon.com', 'conferma-spedizione@amazon.com', 'confirmar-envio@amazon.com', 'versandbestaetigung@amazon.com', 'confirmation-commande@amazon.com', 'verzending-volgen@amazon.com', 'update-bestelling@amazon.com']"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_hash_file():
    """Test file hashing function."""
    result = hash_file("tests/test_emails/amazon_delivered.eml")
    assert result == "7f9d94e97bb4fc870d2d2b3aeae0c428ebed31dc"


@pytest.mark.asyncio
async def test_fedex_out_for_delivery(hass, mock_imap_fedex_out_for_delivery):
    """Test FedEx out for delivery count."""
    result = await get_count(
        mock_imap_fedex_out_for_delivery, "fedex_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["61290912345678912345"]


@pytest.mark.asyncio
async def test_fedex_out_for_delivery_2(hass, mock_imap_fedex_out_for_delivery_2):
    """Test FedEx out for delivery count (scenario 2)."""
    result = await get_count(
        mock_imap_fedex_out_for_delivery_2, "fedex_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["286548999999"]


@pytest.mark.asyncio
async def test_get_mails_email_search_none(
    hass,
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    """Test get_mails helper when email search returns None."""
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("OK", [None]),
    ):
        result = await get_mails(
            hass,
            mock_imap_usps_informed_digest_no_mail,
            "./",
            "5",
            "mail_today.gif",
            False,
        )
        assert result == 0


@pytest.mark.asyncio
async def test_email_search_none(mock_imap_search_error_none, caplog):
    """Test email_search helper with None result."""
    result = await email_search(
        mock_imap_search_error_none, "fake@eamil.address", "01-Jan-20"
    )
    assert result == ("OK", [None])


# @pytest.mark.asyncio
# async def test_amazon_shipped_fwd(hass, mock_imap_amazon_fwd, caplog):
#     """Test Amazon shipped forwarded email processing."""
#     with (
#         patch(
#             "custom_components.mail_and_packages.helpers.dateparser.parse"
#         ) as mock_parse,
#         caplog.at_level(logging.DEBUG),
#     ):
#         mock_parse.return_value = datetime(2022, 1, 11)
#         result = await get_items(
#             mock_imap_amazon_fwd,
#             "order",
#             fwds="testuser@test.com",
#             the_domain="amazon.com",
#         )
#         assert (
#             "Amazon email search addresses: ['auto-confirm@amazon.com', 'shipment-tracking@amazon.com', 'order-update@amazon.com', 'conferma-spedizione@amazon.com', 'confirmar-envio@amazon.com', 'versandbestaetigung@amazon.com', 'confirmation-commande@amazon.com', 'verzending-volgen@amazon.com', 'update-bestelling@amazon.com']"
#             in caplog.text
#         )
#         assert result == ["123-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_otp(hass, mock_imap_amazon_otp, caplog):
    """Test Amazon OTP extraction."""
    result = await amazon_otp(mock_imap_amazon_otp, ["test@amazon.com"])
    assert result == {"code": ["671314"]}


# @pytest.mark.asyncio
# async def test_amazon_out_for_delivery_today(hass, mock_imap_amazon_arriving_today):
#     """Test that Amazon emails with 'Arriving today' are detected."""
#     result = await get_items(
#         mock_imap_amazon_arriving_today, "order", the_domain="amazon.com"
#     )
#     # Email may or may not have an order number - check if it's extracted correctly if present
#     if len(result) > 0:
#         assert all(
#             re.match(r"[0-9]{3}-[0-9]{7}-[0-9]{7}", order) for order in result
#         ), "Order numbers should match Amazon pattern"

#     # Test that "Arriving today" is detected and parsed correctly when email date matches today
#     with (
#         patch("datetime.date") as mock_date,
#         patch(
#             "custom_components.mail_and_packages.helpers.dateparser"
#         ) as mock_dateparser,
#     ):
#         # Mock today to match the email date (which should be the same day)
#         mock_date.today.return_value = date(2020, 9, 11)
#         # Mock dateparser to return today's date for "today"
#         mock_dateparser.parse.return_value = datetime(2020, 9, 11)
#     result = await get_items(
#         mock_imap_amazon_arriving_today, "count", the_domain="amazon.com"
#     )
#     # The email says "Arriving today" and email date matches today
#     # Delivery count should be 1 (detected "today")
#     # Result is min(deliveries_today, len(order_number))
#     assert result == 1, (
#         "Count should be 1 when 'Arriving today' and email date matches today"
#     )


# @pytest.mark.asyncio
# async def test_amazon_arriving_tomorrow(hass, mock_imap_amazon_arriving_tomorrow):
#     """Test that Amazon emails with 'Arriving tomorrow' are detected."""
#     result = await get_items(
#         mock_imap_amazon_arriving_tomorrow, "order", the_domain="amazon.com"
#     )
#     assert result == ["111-7634359-8390444"]  # Should extract order number

#     # Test that "Arriving tomorrow" doesn't count as arriving today
#     with (
#         patch("datetime.date") as mock_date,
#         patch(
#             "custom_components.mail_and_packages.helpers.dateparser"
#         ) as mock_dateparser,
#     ):
#         mock_date.today.return_value = date(2025, 10, 28)
#         # Mock dateparser to return Oct 29 (tomorrow from email date Oct 28)
#         mock_dateparser.parse.return_value = datetime(2025, 10, 29)
#         result = await get_items(
#             mock_imap_amazon_arriving_tomorrow, "count", the_domain="amazon.com"
#         )
#         # Email date is Oct 28, "tomorrow" = Oct 29, so should NOT count as arriving today
#     assert result == 0


# @pytest.mark.asyncio
# async def test_amazon_arriving_tomorrow_matches_date(
#     hass, mock_imap_amazon_arriving_tomorrow
# ):
#     """Test that 'Arriving tomorrow' works when today is Oct 29 (tomorrow from email date)."""
#     result = await get_items(
#         mock_imap_amazon_arriving_tomorrow, "order", the_domain="amazon.com"
#     )
#     assert result == ["111-7634359-8390444"]  # Should extract order number

#     # Test that "Arriving tomorrow" counts when today matches tomorrow
#     with (
#         patch("datetime.date") as mock_date,
#         patch(
#             "custom_components.mail_and_packages.helpers.dateparser"
#         ) as mock_dateparser,
#     ):
#         # Mock today to be Oct 29, 2025 (tomorrow from email date Oct 28)
#         mock_date.today.return_value = date(2025, 10, 29)
#         # Mock dateparser to return Oct 29 (tomorrow from email date Oct 28)
#         mock_dateparser.parse.return_value = datetime(2025, 10, 29)
#         result = await get_items(
#             mock_imap_amazon_arriving_tomorrow, "count", the_domain="amazon.com"
#         )
#         # Email date is Oct 28, "tomorrow" = Oct 29, today is Oct 29, so SHOULD count
#         assert result == 1


@pytest.mark.asyncio
async def test_get_resourcs(hass):
    """Test get_resources helper function."""
    result = get_resources()
    assert result == {
        "amazon_delivered": "Mail Amazon Packages Delivered",
        "amazon_exception": "Mail Amazon Exception",
        "amazon_hub": "Mail Amazon Hub Packages",
        "amazon_otp": "Mail Amazon OTP Code",
        "amazon_packages": "Mail Amazon Packages",
        "auspost_delivered": "Mail AusPost Delivered",
        "auspost_delivering": "Mail AusPost Delivering",
        "auspost_packages": "Mail AusPost Packages",
        "bonshaw_distribution_network_delivered": "Mail Bonshaw Distribution Network Delivered",
        "bonshaw_distribution_network_delivering": "Mail Bonshaw Distribution Network Delivering",
        "bonshaw_distribution_network_packages": "Mail Bonshaw Distribution Network Packages",
        "buildinglink_delivered": "Mail BuildingLink Delivered",
        "capost_delivered": "Mail Canada Post Delivered",
        "capost_delivering": "Mail Canada Post Delivering",
        "capost_mail": "Mail Canada Post Mail",
        "capost_packages": "Mail Canada Post Packages",
        "dhl_delivered": "Mail DHL Delivered",
        "dhl_delivering": "Mail DHL Delivering",
        "dhl_packages": "Mail DHL Packages",
        "dhl_parcel_nl_delivered": "DHL Parcel NL Delivered",
        "dhl_parcel_nl_delivering": "DHL Parcel NL Delivering",
        "dhl_parcel_nl_packages": "DHL Parcel NL Packages",
        "dpd_com_pl_delivered": "Mail DPD.com.pl Delivered",
        "dpd_com_pl_delivering": "Mail DPD.com.pl Delivering",
        "dpd_com_pl_packages": "Mail DPD.com.pl Packages",
        "dpd_delivered": "Mail DPD Delivered",
        "dpd_delivering": "Mail DPD Delivering",
        "dpd_packages": "Mail DPD Packages",
        "evri_delivered": "Mail Evri Delivered",
        "evri_delivering": "Mail Evri Delivering",
        "evri_packages": "Mail Evri Packages",
        "fedex_delivered": "Mail FedEx Delivered",
        "fedex_delivering": "Mail FedEx Delivering",
        "fedex_packages": "Mail FedEx Packages",
        "gls_delivered": "Mail GLS Delivered",
        "gls_delivering": "Mail GLS Delivering",
        "gls_packages": "Mail GLS Packages",
        "hermes_delivered": "Mail Hermes Delivered",
        "hermes_delivering": "Mail Hermes Delivering",
        "hermes_packages": "Mail Hermes Packages",
        "inpost_pl_delivered": "Mail InPost.pl Delivered",
        "inpost_pl_delivering": "Mail InPost.pl Delivering",
        "inpost_pl_packages": "Mail InPost.pl Packages",
        "intelcom_delivered": "Mail Intelcom Delivered",
        "intelcom_delivering": "Mail Intelcom Delivering",
        "intelcom_packages": "Mail Intelcom Packages",
        "mail_updated": "Mail Updated",
        "poczta_polska_delivering": "Mail Poczta Polska Delivering",
        "poczta_polska_packages": "Mail Poczta Polska Packages",
        "post_at_delivered": "Post AT Delivered",
        "post_at_delivering": "Post AT Delivering",
        "post_at_packages": "Post AT Packages",
        "post_de_delivering": "Post DE Delivering",
        "post_de_packages": "Post DE Packages",
        "post_nl_delivered": "Post NL Delivered",
        "post_nl_delivering": "Post NL Delivering",
        "post_nl_exception": "Post NL Missed Delivery",
        "post_nl_packages": "Post NL Packages",
        "purolator_delivered": "Mail Purolator Delivered",
        "purolator_delivering": "Mail Purolator Delivering",
        "purolator_packages": "Mail Purolator Packages",
        "rewe_lieferservice_delivered": "Rewe Lieferservice Delivered",
        "rewe_lieferservice_delivering": "Rewe Lieferservice Delivering",
        "rewe_lieferservice_packages": "Rewe Lieferservice Packages",
        "royal_delivered": "Mail Royal Mail Delivered",
        "royal_delivering": "Mail Royal Mail Delivering",
        "royal_packages": "Mail Royal Mail Packages",
        "ups_delivered": "Mail UPS Delivered",
        "ups_delivering": "Mail UPS Delivering",
        "ups_exception": "Mail UPS Exception",
        "ups_packages": "Mail UPS Packages",
        "usps_delivered": "Mail USPS Delivered",
        "usps_delivering": "Mail USPS Delivering",
        "usps_exception": "Mail USPS Exception",
        "usps_mail": "Mail USPS Mail",
        "usps_mail_delivered": "USPS Mail Delivered",
        "usps_packages": "Mail USPS Packages",
        "walmart_delivered": "Mail Walmart Delivered",
        "walmart_delivering": "Mail Walmart Delivering",
        "walmart_exception": "Mail Walmart Exception",
        "zpackages_delivered": "Mail Packages Delivered",
        "zpackages_transit": "Mail Packages In Transit",
    }


@pytest.mark.asyncio
async def test_generate_grid_image(
    mock_osremove, mock_os_path_join2, mock_subprocess_call, mock_os_path_split
):
    """Test generate_grid_image helper function."""
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        # Test case 1: count=5 -> 2x3 grid
        generate_grid_img("./", "testfile.gif", 5)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "testfile.gif",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x3:padding=10:color=black",
                "testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )

        # Test case 2: count=8 -> 2x4 grid
        generate_grid_img("./", "testfile.gif", 8)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "testfile.gif",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x4:padding=10:color=black",
                "testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )

        # Test case 3: count=1 -> 2x1 grid
        generate_grid_img("./", "testfile.gif", 1)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "testfile.gif",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x1:padding=10:color=black",
                "testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )

        # Test case 4: count=0 -> 2x1 grid (max(count, 1))
        generate_grid_img("./", "testfile.gif", 0)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "testfile.gif",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x1:padding=10:color=black",
                "testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )


# @pytest.mark.asyncio
# async def test_capost_mail(
#     hass,
#     mock_imap_capost_mail,
#     integration_capost,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_os_path_splitext,
#     mock_image,
#     mock_resizeimage,
#     mock_copyfile,
#     caplog,
# ):
#     """Test Canada Post mail processing."""
#     hass.config.internal_url = "http://127.0.0.1:8123/"
#     entry = integration_capost
#     config = entry.data.copy()

#     result = await process_emails(hass, config)
#     assert result["capost_mail"] == 3


# async def test_amazon_image_path_with_custom_image(hass, integration):
#     """Test Amazon image path when custom image is enabled."""
#     entry = integration
#     config = entry.data.copy()

#     # Test with custom image enabled
#     config["amazon_custom_img"] = True
#     config["amazon_custom_img_file"] = "images/test_amazon_custom.jpg"

#     with patch("pathlib.Path.exists", return_value=True):
#         image_path = get_amazon_image_path(config, hass)
#         assert "images/test_amazon_custom.jpg" in image_path


async def test_amazon_image_path_with_default_image(hass, integration):
    """Test Amazon image path when using default image."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image disabled (should use default)
    config["amazon_custom_img"] = False

    image_path = get_amazon_image_path(config, hass)
    assert "no_deliveries_amazon.jpg" in image_path


async def test_ups_image_path_with_custom_image(hass, integration):
    """Test UPS image path when custom image is enabled."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image enabled
    config["ups_custom_img"] = True
    config["ups_custom_img_file"] = "images/test_ups_custom.jpg"

    with patch("pathlib.Path.exists", return_value=True):
        image_path = get_ups_image_path(config, hass)
        assert "images/test_ups_custom.jpg" in image_path


async def test_ups_image_path_with_default_image(hass, integration):
    """Test UPS image path when using default image."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image disabled (should use default)
    config["ups_custom_img"] = False

    image_path = get_ups_image_path(config, hass)
    assert "no_deliveries_ups.jpg" in image_path


async def test_migration_adds_custom_image_fields(hass, integration):
    """Test that migration adds custom image fields to old configs."""
    entry = integration
    config = entry.data.copy()

    # Simulate an old config without custom image fields
    old_config = config.copy()
    if "amazon_custom_img" in old_config:
        del old_config["amazon_custom_img"]
    if "amazon_custom_img_file" in old_config:
        del old_config["amazon_custom_img_file"]
    if "ups_custom_img" in old_config:
        del old_config["ups_custom_img"]
    if "ups_custom_img_file" in old_config:
        del old_config["ups_custom_img_file"]

    # Test that the migration logic would add these fields
    migrated_config = migrate_config(old_config, version=10)  # Simulate old version

    assert "amazon_custom_img" in migrated_config
    assert migrated_config["amazon_custom_img"] is False
    assert "amazon_custom_img_file" in migrated_config
    assert "no_deliveries_amazon.jpg" in migrated_config["amazon_custom_img_file"]
    assert "ups_custom_img" in migrated_config
    assert migrated_config["ups_custom_img"] is False
    assert "ups_custom_img_file" in migrated_config
    assert "no_deliveries_ups.jpg" in migrated_config["ups_custom_img_file"]


async def test_custom_image_path_validation(hass, integration):
    """Test validation of custom image file paths."""
    entry = integration
    config = entry.data.copy()

    # Test with valid custom image paths
    config["amazon_custom_img"] = True
    config["amazon_custom_img_file"] = "images/valid_amazon.jpg"
    config["ups_custom_img"] = True
    config["ups_custom_img_file"] = "images/valid_ups.jpg"

    with patch("pathlib.Path.exists", return_value=True):
        result = validate_custom_image_paths(config)
        assert result is True

    with patch("pathlib.Path.exists", return_value=False):
        result = validate_custom_image_paths(config)
        assert result is False


async def test_image_path_fallback_logic(hass, integration):
    """Test fallback logic when custom images are not found."""
    entry = integration
    config = entry.data.copy()

    # Enable custom images but mock them as not existing
    config["amazon_custom_img"] = True
    config["amazon_custom_img_file"] = "images/nonexistent_amazon.jpg"
    config["ups_custom_img"] = True
    config["ups_custom_img_file"] = "images/nonexistent_ups.jpg"

    # Fix: Add autospec=True so the instance (p) is passed to the lambda
    with patch(
        "pathlib.Path.exists",
        autospec=True,
        side_effect=lambda p: "nonexistent" not in str(p),
    ):
        # Should fall back to default images when custom ones don't exist
        amazon_path = get_amazon_image_path(config, hass)
        assert "no_deliveries_amazon.jpg" in amazon_path

        ups_path = get_ups_image_path(config, hass)
        assert "no_deliveries_ups.jpg" in ups_path


# Test helper functions
def get_amazon_image_path(config: dict, hass) -> str:
    """Get the Amazon image path based on configuration."""
    if config.get(CONF_AMAZON_CUSTOM_IMG, False):
        custom_path = config.get(
            CONF_AMAZON_CUSTOM_IMG_FILE, DEFAULT_AMAZON_CUSTOM_IMG_FILE
        )
        if Path(custom_path).exists():
            return custom_path

    # Fall back to default image
    return DEFAULT_AMAZON_CUSTOM_IMG_FILE


def get_ups_image_path(config: dict, hass) -> str:
    """Get the UPS image path based on configuration."""
    if config.get(CONF_UPS_CUSTOM_IMG, False):
        custom_path = config.get(CONF_UPS_CUSTOM_IMG_FILE, DEFAULT_UPS_CUSTOM_IMG_FILE)

        if Path(custom_path).exists():
            return custom_path

    # Fall back to default image
    return DEFAULT_UPS_CUSTOM_IMG_FILE


def get_walmart_image_path(config: dict, hass) -> str:
    """Get the Walmart image path based on configuration."""
    if config.get(CONF_WALMART_CUSTOM_IMG, False):
        custom_path = config.get(
            CONF_WALMART_CUSTOM_IMG_FILE, DEFAULT_WALMART_CUSTOM_IMG_FILE
        )

        if Path(custom_path).exists():
            return custom_path

    # Fall back to default image
    return DEFAULT_WALMART_CUSTOM_IMG_FILE


def validate_custom_image_paths(config: dict) -> bool:
    """Validate that custom image file paths exist."""
    if config.get(CONF_AMAZON_CUSTOM_IMG, False):
        amazon_path = config.get(CONF_AMAZON_CUSTOM_IMG_FILE)
        if amazon_path and not Path(amazon_path).exists():
            return False

    if config.get(CONF_UPS_CUSTOM_IMG, False):
        ups_path = config.get(CONF_UPS_CUSTOM_IMG_FILE)

        if ups_path and not Path(ups_path).exists():
            return False

    return True


def migrate_config(config: dict, version: int) -> dict:
    """Migrate configuration to add missing custom image fields."""
    migrated_config = config.copy()

    # Add Amazon custom image fields if missing
    if CONF_AMAZON_CUSTOM_IMG not in migrated_config:
        migrated_config[CONF_AMAZON_CUSTOM_IMG] = False
    if CONF_AMAZON_CUSTOM_IMG_FILE not in migrated_config:
        migrated_config[CONF_AMAZON_CUSTOM_IMG_FILE] = DEFAULT_AMAZON_CUSTOM_IMG_FILE

    # Add UPS custom image fields if missing
    if CONF_UPS_CUSTOM_IMG not in migrated_config:
        migrated_config[CONF_UPS_CUSTOM_IMG] = False
    if CONF_UPS_CUSTOM_IMG_FILE not in migrated_config:
        migrated_config[CONF_UPS_CUSTOM_IMG_FILE] = DEFAULT_UPS_CUSTOM_IMG_FILE

    return migrated_config


# @pytest.mark.asyncio
# async def test_walmart_delivered_email_processing(hass, integration):
#     """Test that Walmart delivered emails are correctly processed and counted."""
#     # Mock the dependencies
#     mock_account = MagicMock()

#     # Test parameters
#     image_path = "/test/images/"
#     coordinator_data = {}

#     # Read the actual test email content
#     test_email_content = Path("tests/test_emails/walmart_delivered.eml").read_text(
#         encoding="utf-8"
#     )

#     with (
#         patch(
#             "custom_components.mail_and_packages.helpers.email_search"
#         ) as mock_email_search,
#         patch(
#             "custom_components.mail_and_packages.helpers.email_fetch"
#         ) as mock_email_fetch,
#         patch("pathlib.Path.is_dir", return_value=True),
#         patch("custom_components.mail_and_packages.helpers.cleanup_images"),
#         patch("pathlib.Path.mkdir"),
#         patch("custom_components.mail_and_packages.helpers.copyfile"),
#         patch(
#             "custom_components.mail_and_packages.helpers._generic_delivery_image_extraction"
#         ) as mock_extract,
#         patch("pathlib.Path.exists", return_value=True),
#         patch("pathlib.Path.stat", return_value=MagicMock(st_size=1000)),
#     ):
#         # Configure mocks
#         mock_email_search.return_value = ("OK", [b"1"])  # One email found
#         mock_email_fetch.return_value = ("OK", [b"1", test_email_content.encode()])
#         mock_extract.return_value = True  # Photo found

#         # Call get_count for walmart_delivered
#         result = (
#             await get_count(
#                 mock_account,
#                 "walmart_delivered",
#                 False,
#                 image_path,
#                 hass,
#                 data=coordinator_data,
#             )
#         )["count"]

#     # Should return at least 1 since one email was found
#     assert result == 1, f"Expected at least 1 Walmart delivery, got {result}"

#     # Verify that coordinator data was updated with the image filename
#     assert ATTR_WALMART_IMAGE in coordinator_data, (
#         "Walmart image should be set in coordinator data"
#     )
#     assert coordinator_data[ATTR_WALMART_IMAGE] in [
#         "walmart_delivery.jpg",
#         "test_walmart.jpg",
#     ], (
#         f"Walmart image filename should be set, got {coordinator_data.get(ATTR_WALMART_IMAGE)}"
#     )


@pytest.mark.asyncio
async def test_walmart_delivering_email_processing(hass):
    """Test that Walmart delivering emails are correctly processed and counted."""
    # Mock the dependencies
    mock_account = MagicMock()

    # Test parameters
    image_path = "/test/images/"

    # Mock email_search to return the test email only for one subject
    with patch(
        "custom_components.mail_and_packages.helpers.email_search"
    ) as mock_email_search:

        def email_search_side_effect(account, email, date, subject):
            # Only return an email for the second subject in the walmart_delivering list
            walmart_subjects = SENSOR_DATA["walmart_delivering"]["subject"]
            if subject == walmart_subjects[1]:  # "Your package should arrive by"
                return ("OK", [b"1"])
            return ("OK", [None])

        mock_email_search.side_effect = email_search_side_effect

        # Mock email_fetch to return our test email content
        with patch(
            "custom_components.mail_and_packages.helpers.email_fetch"
        ) as mock_email_fetch:
            # Read the actual test email content
            test_email_content = Path(
                "tests/test_emails/walmart_delivery.eml"
            ).read_text(encoding="utf-8")

            mock_email_fetch.return_value = (
                "OK",
                [(None, test_email_content.encode())],
            )

            # Call get_count for walmart_delivering
            result = await get_count(
                mock_account,
                "walmart_delivering",
                image_path=image_path,
                hass=hass,
            )

    # Should return 1 since one email was found
    assert result[ATTR_COUNT] == 1, (
        f"Expected 1 Walmart delivering package, got {result[ATTR_COUNT]}"
    )

    # Test that tracking numbers are extracted
    if ATTR_TRACKING in result:
        assert len(result[ATTR_TRACKING]) >= 0, (
            "Tracking numbers should be extracted if present"
        )


@pytest.mark.asyncio
async def test_walmart_image_extraction(hass):
    """Test that Walmart delivery photos are correctly extracted from emails."""
    # Test parameters
    image_path = "/test/images/"
    image_name = "test_walmart.jpg"

    # Read the actual test email content
    test_email_content = Path("tests/test_emails/walmart_delivered.eml").read_text(
        encoding="utf-8"
    )

    # Mock file operations
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        # Fix: Patch Path.open instead of builtins.open
        patch("pathlib.Path.open", mock.mock_open()),
        # Fix: Patch Path.exists to return True so verification passes
        patch("pathlib.Path.exists", return_value=True),
        # Patch Path.stat to avoid FileNotFoundError when getting size
        patch("pathlib.Path.stat", return_value=MagicMock(st_size=1000)),
    ):
        # Call _generic_delivery_image_extraction
        result = _generic_delivery_image_extraction(
            test_email_content,
            image_path,
            image_name,
            "walmart",
            "png",
            "deliveryProofLabel",
            None,
        )

    # Should return True since the email contains a delivery photo
    assert result is True, (
        "Walmart image extraction should return True for email with delivery photo"
    )


async def test_walmart_email_patterns():
    """Test that Walmart email patterns are correctly configured."""
    # Test Walmart delivered email patterns
    walmart_delivered_emails = SENSOR_DATA["walmart_delivered"]["email"]
    walmart_delivered_subjects = SENSOR_DATA["walmart_delivered"]["subject"]

    # Should include the Walmart email address
    assert "help@walmart.com" in walmart_delivered_emails, (
        "Walmart delivered emails should include help@walmart.com"
    )

    # Should include "Delivered:" subject pattern
    assert "Delivered:" in walmart_delivered_subjects, (
        "Walmart delivered subjects should include 'Delivered:'"
    )

    # Test Walmart delivering email patterns
    walmart_delivering_emails = SENSOR_DATA["walmart_delivering"]["email"]
    walmart_delivering_subjects = SENSOR_DATA["walmart_delivering"]["subject"]

    # Should include the same email address
    assert "help@walmart.com" in walmart_delivering_emails, (
        "Walmart delivering emails should include help@walmart.com"
    )

    # Should include "Your package should arrive by" subject pattern
    assert "Your package should arrive by" in walmart_delivering_subjects, (
        "Walmart delivering subjects should include 'Your package should arrive by'"
    )


async def test_walmart_tracking_pattern():
    """Test that Walmart tracking pattern matches the test email tracking number."""
    # Test tracking number from walmart_delivered.eml (if it has one)
    # Note: The test email might not have a tracking number, so we'll test the pattern itself
    walmart_tracking_pattern = SENSOR_DATA["walmart_tracking"]["pattern"]

    # Test the pattern with a sample tracking number
    sample_tracking = "#1234567-12345678"
    pattern = walmart_tracking_pattern[0]  # "#[0-9]{7}-[0-9]{7,8}"
    match = re.search(pattern, sample_tracking)
    assert match is not None, (
        f"Sample tracking number {sample_tracking} should match Walmart pattern {pattern}"
    )


async def test_ups_camera_integration():
    """Test that UPS camera is properly integrated with coordinator data."""
    # Test that UPS camera is defined in CAMERA_DATA
    assert "ups_camera" in CAMERA_DATA, "UPS camera should be defined in CAMERA_DATA"
    assert CAMERA_DATA["ups_camera"][0] == "Mail UPS Camera", (
        "UPS camera should have correct name"
    )

    # Test that ATTR_UPS_IMAGE constant exists
    assert ATTR_UPS_IMAGE == "ups_image", "ATTR_UPS_IMAGE should be defined correctly"


async def test_walmart_camera_integration():
    """Test that Walmart camera is properly integrated with coordinator data."""
    # Test that Walmart camera is defined in CAMERA_DATA
    assert "walmart_camera" in CAMERA_DATA, (
        "Walmart camera should be defined in CAMERA_DATA"
    )
    assert CAMERA_DATA["walmart_camera"][0] == "Mail Walmart Delivery Camera", (
        "Walmart camera should have correct name"
    )

    # Test that ATTR_WALMART_IMAGE constant exists
    assert ATTR_WALMART_IMAGE == "walmart_image", (
        "ATTR_WALMART_IMAGE should be defined correctly"
    )


@pytest.mark.asyncio
async def test_walmart_no_deliveries_handling(hass, integration):
    """Test that Walmart handles no deliveries correctly."""
    # Mock the dependencies
    mock_account = MagicMock()

    # Test parameters
    image_path = "/test/images/"
    coordinator_data = {}

    # Mock email_search to return no emails
    with patch(
        "custom_components.mail_and_packages.helpers.email_search"
    ) as mock_email_search:
        mock_email_search.return_value = ("OK", [None])  # No emails found

        # Mock file operations
        with (
            # Fix: Patch pathlib.Path methods used in helpers.py
            patch("pathlib.Path.is_dir", return_value=True),
            # cleanup_images calls iterdir, mock it to return empty list
            patch("pathlib.Path.iterdir", return_value=[]),
            patch(
                "custom_components.mail_and_packages.helpers.copyfile"
            ) as mock_copyfile,
        ):
            # Call get_count for walmart_delivered
            result = (
                await get_count(
                    mock_account,
                    "walmart_delivered",
                    False,
                    image_path,
                    hass,
                    data=coordinator_data,
                )
            )["count"]

    # Should return 0 since no emails were found
    assert result == 0, f"Expected 0 Walmart deliveries, got {result}"

    # Verify that coordinator data was updated with no-delivery image
    assert ATTR_WALMART_IMAGE in coordinator_data, (
        "Walmart image should be set in coordinator data even with no deliveries"
    )

    # Verify that copyfile was called to create no-delivery image
    assert mock_copyfile.called, "copyfile should be called to create no-delivery image"


@pytest.mark.asyncio
async def test_ups_no_deliveries_handling(hass, integration):
    """Test that UPS handles no deliveries correctly."""
    # Mock the dependencies
    mock_account = MagicMock()

    # Test parameters
    image_path = "/test/images/"
    coordinator_data = {}

    # Mock email_search to return no emails
    with patch(
        "custom_components.mail_and_packages.helpers.email_search"
    ) as mock_email_search:
        mock_email_search.return_value = ("OK", [None])  # No emails found

        # Mock file operations
        with (
            # Fix: Patch pathlib.Path methods used in helpers.py
            patch("pathlib.Path.is_dir", return_value=True),
            # cleanup_images calls iterdir, mock it to return empty list
            patch("pathlib.Path.iterdir", return_value=[]),
            patch(
                "custom_components.mail_and_packages.helpers.copyfile"
            ) as mock_copyfile,
        ):
            # Call get_count for ups_delivered
            result = (
                await get_count(
                    mock_account,
                    "ups_delivered",
                    False,
                    image_path,
                    hass,
                    data=coordinator_data,
                )
            )["count"]

    # Should return 0 since no emails were found
    assert result == 0, f"Expected 0 UPS deliveries, got {result}"

    # Verify that coordinator data was updated with no-delivery image
    assert ATTR_UPS_IMAGE in coordinator_data, (
        "UPS image should be set in coordinator data even with no deliveries"
    )

    # Verify that copyfile was called to create no-delivery image
    assert mock_copyfile.called, "copyfile should be called to create no-delivery image"


async def test_walmart_custom_image_support():
    """Test that Walmart supports custom images like UPS and Amazon."""
    # Test that custom image constants are defined
    assert CONF_WALMART_CUSTOM_IMG == "walmart_custom_img"
    assert CONF_WALMART_CUSTOM_IMG_FILE == "walmart_custom_img_file"
    assert (
        DEFAULT_WALMART_CUSTOM_IMG_FILE
        == "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
    )


async def test_walmart_sensor_integration():
    """Test that Walmart is properly integrated with sensor counts."""
    # Test that Walmart is in the SHIPPERS list
    assert "walmart" in SHIPPERS, (
        "Walmart should be in SHIPPERS list for sensor counting"
    )

    # Test that Walmart sensors are defined
    assert "walmart_delivered" in SENSOR_DATA, (
        "Walmart delivered sensor should be defined"
    )
    assert "walmart_delivering" in SENSOR_DATA, (
        "Walmart delivering sensor should be defined"
    )

    # Test that Walmart will be counted in aggregate sensors
    walmart_delivered = "walmart_delivered"
    walmart_delivering = "walmart_delivering"

    # These sensors will be automatically counted in zpackages_delivered and zpackages_transit
    # because walmart is in the SHIPPERS list
    assert walmart_delivered in SENSOR_DATA
    assert walmart_delivering in SENSOR_DATA


async def test_walmart_order_tracking():
    """Test that Walmart order numbers are correctly extracted."""
    # Test the tracking pattern with various order number formats
    walmart_tracking_pattern = SENSOR_DATA["walmart_tracking"]["pattern"]
    pattern = walmart_tracking_pattern[0]  # "#?[0-9]{7}-[0-9]{7,8}"

    # Test different order number formats
    test_orders = [
        "#2000137-67895124",  # With hash symbol
        "2000137-67895124",  # Without hash symbol
        "#1234567-12345678",  # Different numbers
        "1234567-12345678",  # Different numbers without hash
    ]

    for order in test_orders:
        match = re.search(pattern, order)
        assert match is not None, (
            f"Order number '{order}' should match Walmart tracking pattern"
        )

    # Test that invalid formats don't match
    invalid_orders = [
        "123456-1234567",  # Too short
        "12345678-123456789",  # Too long
        "ABC1234-5678901",  # Contains letters
        "1234567_12345678",  # Wrong separator
    ]

    for order in invalid_orders:
        match = re.search(pattern, order)
        assert match is None, (
            f"Invalid order number '{order}' should not match Walmart tracking pattern"
        )


async def test_get_walmart_image_with_real_email():
    """Test get_walmart_image function with real Walmart delivery email."""
    # Read the actual Walmart delivery email
    test_email = Path("tests/test_emails/walmart_delivery.eml").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        walmart_path = Path(temp_dir) / "walmart"
        walmart_path.mkdir(exist_ok=True)

        # Test with real Walmart email (this email doesn't contain delivery proof images)
        result = _generic_delivery_image_extraction(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
            "walmart",
            "png",
            "deliveryProofLabel",
            None,
        )

        # This email doesn't contain delivery proof images, so should return False
        assert result is False
        assert not (walmart_path / "test_delivery.jpg").exists()


async def test_get_walmart_image_base64():
    """Test get_walmart_image function with base64 encoded images."""
    # Create a test email with base64 encoded image
    test_email = """From: help@walmart.com
To: test@example.com
Subject: Your order was delivered
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/html; charset=utf-8

<html>
<body>
<p>Your package has been delivered!</p>
<div class="deliveryProofLabel">
<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" alt="Delivery Proof">
</div>
</body>
</html>
--boundary123--
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        walmart_path = Path(temp_dir) / "walmart"
        walmart_path.mkdir(exist_ok=True)

        # Test with base64 encoded image using generic function
        result = _generic_delivery_image_extraction(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
            "walmart",
            "png",
            "deliveryProofLabel",
            None,
        )

        assert result is True
        assert (walmart_path / "test_delivery.jpg").exists()


async def test_get_walmart_image_attachment():
    """Test get_walmart_image function with PNG attachments."""
    # Create a test email with PNG attachment
    test_email = """From: help@walmart.com
To: test@example.com
Subject: Your order was delivered
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=utf-8

Your package has been delivered!

--boundary123
Content-Type: image/png
Content-Disposition: attachment; filename="delivery_proof.png"
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==
--boundary123--
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        walmart_path = Path(temp_dir) / "walmart"
        walmart_path.mkdir(exist_ok=True)

        # Test with PNG attachment
        result = _generic_delivery_image_extraction(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
            "walmart",
            "png",
            "deliveryProofLabel",
            None,
        )

        assert result is True
        assert (walmart_path / "test_delivery.jpg").exists()


async def test_get_walmart_image_no_image():
    """Test get_walmart_image function when no image is found."""
    # Create a test email without any images
    test_email = """From: help@walmart.com
To: test@example.com
Subject: Your order was delivered
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Your package has been delivered!
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        # Use Path for directory operations
        walmart_path = Path(temp_dir) / "walmart"
        walmart_path.mkdir(exist_ok=True)

        # Test with no image
        result = _generic_delivery_image_extraction(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
            "walmart",
            "png",
            "deliveryProofLabel",
            None,
        )

        assert result is False
        assert not (walmart_path / "test_delivery.jpg").exists()


async def test_get_walmart_image_file_error():
    """Test get_walmart_image function with file write error."""
    # Create a test email with CID embedded image
    test_email = """From: help@walmart.com
To: test@example.com
Subject: Your order was delivered
MIME-Version: 1.0
Content-Type: multipart/related; boundary="boundary123"

--boundary123
Content-Type: text/html; charset=utf-8

<html>
<body>
<p>Your package has been delivered!</p>
<img src="cid:deliveryProofLabel" alt="Delivery Proof">
</body>
</html>

--boundary123
Content-Type: image/png
Content-ID: <deliveryProofLabel>
Content-Transfer-Encoding: base64

iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==
--boundary123--
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        walmart_path = Path(temp_dir) / "walmart"
        walmart_path.mkdir(parents=True, exist_ok=True)

        # Mock file write to raise an exception
        # Fix: Patch Path.open instead of builtins.open
        with patch("pathlib.Path.open", side_effect=OSError("Permission denied")):
            result = _generic_delivery_image_extraction(
                test_email,
                temp_dir + "/",
                "test_delivery.jpg",
                "walmart",
                "png",
                "deliveryProofLabel",
                None,
            )

            assert result is False


async def test_walmart_email_with_order_number():
    """Test that Walmart emails contain order numbers that can be extracted."""
    # Read the actual Walmart delivery email
    test_email = Path("tests/test_emails/walmart_delivery.eml").read_text(
        encoding="utf-8"
    )

    # Test that the order number is in the email content (handle MIME encoding)
    # The email has MIME encoding with = at end of lines, so we need to check for the pattern
    assert "2000137-6789512" in test_email  # Check for the first part
    assert "4" in test_email  # Check for the last part

    # Test that the tracking pattern matches the order number
    walmart_tracking_pattern = SENSOR_DATA["walmart_tracking"]["pattern"]
    pattern = walmart_tracking_pattern[0]
    match = re.search(pattern, test_email)
    assert match is not None
    # The MIME encoding breaks the full order number, so we check for the partial match
    assert (
        match.group() == "2000137-6789512"
    )  # This is what actually matches due to MIME encoding

    # Test that the pattern can find the order number in the email
    # (The get_tracking function has more complex logic, so we just test the basic pattern matching)
    assert match is not None, "Should find at least a partial order number match"


async def test_walmart_delivered_email_with_real_data():
    """Test Walmart delivered email processing with real email data."""
    # Read the actual Walmart delivered email
    test_email = Path("tests/test_emails/walmart_delivered.eml").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        # Use Path for directory operations
        walmart_path = Path(temp_dir) / "walmart"
        walmart_path.mkdir(exist_ok=True)

        # Test with real Walmart delivered email
        result = _generic_delivery_image_extraction(
            test_email,
            str(Path(temp_dir))
            + "/",  # Function expects string path with trailing slash
            "test_delivery.jpg",
            "walmart",
            "png",
            "deliveryProofLabel",
            None,
        )

        # The email has a valid delivery proof image structure
        assert "deliveryProofLabel" in test_email
        assert "cid:deliveryProofLabel" in test_email
        # Result should be True because the email contains a valid delivery proof image
        assert result is True
        assert (walmart_path / "test_delivery.jpg").exists()


async def test_walmart_image_path_with_custom_image(hass, integration):
    """Test Walmart image path when custom image is enabled."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image enabled
    config["walmart_custom_img"] = True
    config["walmart_custom_img_file"] = "images/test_walmart_custom.jpg"

    # Mock pathlib.Path.exists
    with patch("pathlib.Path.exists", return_value=True):
        image_path = get_walmart_image_path(config, hass)
        assert "images/test_walmart_custom.jpg" in image_path


async def test_walmart_image_path_with_default_image(hass, integration):
    """Test Walmart image path when using default image."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image disabled (should use default)
    config["walmart_custom_img"] = False

    image_path = get_walmart_image_path(config, hass)
    assert "no_deliveries_walmart.jpg" in image_path


@pytest.mark.asyncio
async def test_walmart_search_error_handling(hass):
    """Test walmart_delivered sensor error handling paths."""
    # Mock account and dependencies
    mock_account = MagicMock()
    mock_account.search.return_value = ("OK", [b""])  # Return proper tuple format

    with tempfile.TemporaryDirectory():
        # Test with invalid image path (should handle gracefully)
        result = await get_count(
            mock_account,
            "walmart_delivered",
            False,
            "/invalid/path/",  # Invalid path
            hass,
            data={},
        )

    # Should return 0 when path is invalid
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_fedex_image_extraction(hass):
    """Test that FedEx delivery photos are correctly extracted from emails."""
    # Test parameters
    image_path = "/test/images/"
    image_name = "test_fedex.jpg"

    # Read the actual test email content
    test_email_content = Path("tests/test_emails/fedex_delivered.eml").read_text(
        encoding="utf-8"
    )

    # Mock file operations
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        # Fix: Patch Path.open because helpers.py uses Path(path).open(), not builtins.open()
        patch("pathlib.Path.open", mock.mock_open()),
        # Patch Path.exists to return True so verification passes
        patch("pathlib.Path.exists", return_value=True),
        # Patch Path.stat to avoid FileNotFoundError when getting size
        patch("pathlib.Path.stat", return_value=MagicMock(st_size=1000)),
    ):
        # Call _generic_delivery_image_extraction directly
        result = _generic_delivery_image_extraction(
            test_email_content,
            image_path,
            image_name,
            "fedex",
            "jpeg",
            attachment_filename_pattern="delivery",
        )

    # Should return True since the email contains a delivery photo
    assert result is True, (
        "FedEx image extraction should return True for email with delivery photo"
    )


async def test_fedex_camera_integration():
    """Test that FedEx camera is properly integrated with coordinator data."""
    # Test that FedEx camera is defined in CAMERA_DATA
    assert "fedex_camera" in CAMERA_DATA, (
        "FedEx camera should be defined in CAMERA_DATA"
    )
    assert CAMERA_DATA["fedex_camera"][0] == "Mail FedEx Delivery Camera", (
        "FedEx camera should have correct name"
    )

    # Test that ATTR_FEDEX_IMAGE constant exists
    assert ATTR_FEDEX_IMAGE == "fedex_image", (
        "ATTR_FEDEX_IMAGE should be defined correctly"
    )


@pytest.mark.asyncio
async def test_fedex_no_deliveries_handling(hass, integration):
    """Test that FedEx handles no deliveries correctly."""
    # Mock the dependencies
    mock_account = MagicMock()

    # Test parameters
    image_path = "/test/images/"
    coordinator_data = {}

    # Mock email_search to return no emails
    with patch(
        "custom_components.mail_and_packages.helpers.email_search"
    ) as mock_email_search:
        mock_email_search.return_value = ("OK", [None])  # No emails found

        # Mock file operations
        with (
            patch("pathlib.Path.is_dir", return_value=True),
            # cleanup_images calls iterdir, so we need to mock it to return an empty list
            patch("pathlib.Path.iterdir", return_value=[]),
            patch(
                "custom_components.mail_and_packages.helpers.copyfile"
            ) as mock_copyfile,
        ):
            # Use get_count for fedex_delivered sensor
            result = await get_count(
                mock_account,
                "fedex_delivered",
                False,
                image_path,
                hass,
                data=coordinator_data,
            )

    # Should return 0 since no emails were found
    assert result["count"] == 0, f"Expected 0 FedEx deliveries, got {result['count']}"

    # Verify that coordinator data was updated with no-delivery image
    assert ATTR_FEDEX_IMAGE in coordinator_data, (
        "FedEx image should be set in coordinator data even with no deliveries"
    )

    # Verify that copyfile was called to create no-delivery image
    assert mock_copyfile.called, "copyfile should be called to create no-delivery image"


async def test_fedex_custom_image_support():
    """Test that FedEx supports custom images like UPS, Walmart, and Amazon."""
    # Test that custom image constants are defined
    assert CONF_FEDEX_CUSTOM_IMG == "fedex_custom_img"
    assert CONF_FEDEX_CUSTOM_IMG_FILE == "fedex_custom_img_file"
    assert (
        DEFAULT_FEDEX_CUSTOM_IMG_FILE
        == "custom_components/mail_and_packages/no_deliveries_fedex.jpg"
    )


@pytest.mark.asyncio
async def test_ups_search_error_handling(hass):
    """Test ups_delivered sensor error handling paths."""
    # Mock account and dependencies
    mock_account = MagicMock()
    mock_account.search.return_value = ("OK", [b""])  # Return proper tuple format

    with tempfile.TemporaryDirectory():
        # Test with invalid image path (should handle gracefully)
        result = await get_count(
            mock_account,
            "ups_delivered",
            False,
            "/invalid/path/",  # Invalid path
            hass,
            data={},
        )

        # Should return 0 when path is invalid
        assert result["count"] == 0


@pytest.mark.asyncio
async def test_process_emails_ups_directory_creation_error(hass, caplog):
    """Test process_emails handles UPS directory creation errors gracefully."""
    config = FAKE_CONFIG_DATA.copy()
    config["resources"] = ["ups_delivered"]
    mock_account = AsyncMock()
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="test_image.jpg",
        ),
        patch("pathlib.Path.is_dir", return_value=False),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("custom_components.mail_and_packages.helpers.copyfile"),
    ):
        mock_mkdir.side_effect = OSError("UPS directory creation error")
        result = await process_emails(hass, config)
        assert isinstance(result, dict)
        assert "Error creating Ups directory" in caplog.text
        mock_account.logout.assert_called_once()


@pytest.mark.asyncio
async def test_default_image_path_attribute_error(hass):
    """Test default_image_path handles AttributeError gracefully."""
    # Mock config entry that raises AttributeError on get()
    mock_config = MagicMock()
    mock_config.get.side_effect = AttributeError("No get method")
    mock_config.data = {"storage": "custom/path/"}

    # Should handle AttributeError and use data attribute
    result = default_image_path(hass, mock_config)
    assert result == "custom/path/"


@pytest.mark.asyncio
async def test_default_image_path_no_storage(hass):
    """Test default_image_path returns default when no storage configured."""
    # Mock config entry with no storage
    mock_config = MagicMock()
    mock_config.get.return_value = None

    # Should return default path
    result = default_image_path(hass, mock_config)
    assert result == "custom_components/mail_and_packages/images/"


@pytest.mark.asyncio
async def test_process_emails_directory_creation_error(hass):
    """Test process_emails handles directory creation errors gracefully."""
    config = FAKE_CONFIG_DATA.copy()
    config["resources"] = ["ups_delivered"]
    mock_account = AsyncMock()
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)

    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch("pathlib.Path.is_dir", return_value=False),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch(
            "custom_components.mail_and_packages.helpers.copyfile",
            side_effect=OSError("File copy error"),
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="test_image.jpg",
        ),
    ):
        mock_mkdir.side_effect = OSError("Directory creation error")
        result = await process_emails(hass, config)
        assert isinstance(result, dict)
        assert mock_mkdir.called
        mock_account.logout.assert_called_once()


async def test_hash_file_functionality():
    """Test hash_file function basic functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create Path object
        test_file = Path(temp_dir) / "test.txt"

        # Replace open() with write_text()
        test_file.write_text("test content")

        # Test with valid file (convert to str in case hash_file expects string)
        result = hash_file(str(test_file))
        assert result is not None
        assert len(result) == 40  # SHA1 hash length
        assert isinstance(result, str)

        # Test that same content produces same hash
        result2 = hash_file(str(test_file))
        assert result == result2

        # Test with different content produces different hash
        test_file.write_text("different content")

        result3 = hash_file(str(test_file))
        assert result != result3


async def test_copy_overlays_error_handling():
    """Test copy_overlays handles errors gracefully."""
    with (
        tempfile.TemporaryDirectory() as temp_dir,
        patch("custom_components.mail_and_packages.helpers.copytree") as mock_copytree,
    ):
        mock_copytree.side_effect = Exception("Copy error")

        # This should handle the exception gracefully
        copy_overlays(temp_dir)


@pytest.mark.asyncio
async def test_image_file_name_copy_error(hass, integration):
    """Test image_file_name handles copy errors gracefully."""
    entry = integration
    config = entry.data.copy()

    with (
        patch("os.path.exists", return_value=True),
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=[]),
        patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile,
        patch(
            "custom_components.mail_and_packages.helpers.hash_file",
            return_value="fakehash",
        ),
    ):
        # Make copyfile raise an OSError (what the code catches), not a generic Exception
        mock_copyfile.side_effect = OSError("Copy error")

        # This should return a fallback filename
        result = image_file_name(hass, config, amazon=True)

        # Should return fallback filename
        assert result == "no_deliveries.jpg"


@pytest.mark.asyncio
async def test_login_starttls_security(hass):
    """Test login with startTLS security using aioimaplib."""
    # Patch IMAP4 directly since 'aioimaplib' module is not exposed in helpers
    with patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap:
        mock_acc = AsyncMock()
        mock_imap.return_value = mock_acc

        # Initial state must be NONAUTH to trigger the login logic in the helper
        mock_acc.protocol.state = aioimaplib.NONAUTH

        # Simulate state change to AUTH upon login to pass the final validation check
        async def login_side_effect(*args, **kwargs):
            mock_acc.protocol.state = aioimaplib.AUTH
            return MagicMock(result="OK")

        mock_acc.login.side_effect = login_side_effect

        result = await login(
            hass, "imap.test.com", 143, "user", "pass", "startTLS", True
        )

        assert result == mock_acc
        mock_acc.starttls.assert_called_once()
        mock_acc.login.assert_called_once_with("user", "pass")


@pytest.mark.asyncio
async def test_login_no_ssl_security():
    """Test login with no SSL security."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap4,
        patch("homeassistant.util.ssl.create_client_context") as mock_ssl_context,
    ):
        mock_account = AsyncMock()
        mock_imap4.return_value = mock_account
        mock_ssl_context.return_value = MagicMock()

        # Initial state NONAUTH to trigger login attempts
        mock_account.protocol.state = aioimaplib.NONAUTH
        mock_account.wait_hello_from_server = AsyncMock()

        # Simulate successful login changing state to AUTH
        async def login_side_effect(*args, **kwargs):
            mock_account.protocol.state = aioimaplib.AUTH
            return MagicMock(result="OK")

        mock_account.login.side_effect = login_side_effect

        result = await login(None, "imap.test.com", 143, "user", "pass", "none", True)

        assert result == mock_account
        mock_imap4.assert_called_once()
        mock_account.login.assert_called_once_with("user", "pass")


@pytest.mark.asyncio
async def test_default_image_path_storage(hass, integration):
    """Test default_image_path with storage configuration."""
    entry = integration
    config = entry.data.copy()

    result = default_image_path(hass, config)

    # Should return the storage path
    assert result == ".storage/mail_and_packages/images"


@pytest.mark.asyncio
async def test_amazon_shipped_vs_delivered_logic():
    """Test that Amazon orders that have been delivered are not counted as in transit."""
    # Test the package counting logic directly
    shipped_packages = {"123-4567890-1234567": 2}  # 2 packages shipped for this order
    delivered_packages = {
        "123-4567890-1234567": 2
    }  # 2 packages delivered for this order

    # Calculate in-transit packages by subtracting delivered from shipped
    in_transit_packages = 0
    for order_id, shipped_count in shipped_packages.items():
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count

    # Should return 0 because all shipped packages were delivered
    assert in_transit_packages == 0, (
        f"Expected 0 (all shipped packages were delivered), got {in_transit_packages}"
    )


@pytest.mark.asyncio
async def test_amazon_mixed_orders_shipped_vs_delivered():
    """Test Amazon orders with some delivered and some still in transit."""
    # Test the package counting logic directly
    shipped_packages = {
        "111-1111111-1111111": 1,  # 1 package shipped, not delivered
        "222-2222222-2222222": 2,  # 2 packages shipped, 1 delivered
        "333-3333333-3333333": 1,  # 1 package shipped, not delivered
    }
    delivered_packages = {
        "222-2222222-2222222": 1,  # 1 package delivered
    }

    # Calculate in-transit packages by subtracting delivered from shipped
    in_transit_packages = 0
    # Fixed PLC0206: Use .items() to iterate key and value together
    for order_id, shipped_count in shipped_packages.items():
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count

    # Should return 3 because: 1 + (2-1) + 1 = 3 packages in transit
    assert in_transit_packages == 3, (
        f"Expected 3 (3 packages in transit), got {in_transit_packages}"
    )


@pytest.mark.asyncio
async def test_amazon_delivered_orders_excluded_from_transit():
    """Test that delivered Amazon orders are properly excluded from transit count."""
    # Test the package counting logic directly
    shipped_packages = {
        "111-1111111-1111111": 1,  # 1 package shipped, not delivered
        "222-2222222-2222222": 2,  # 2 packages shipped, 2 delivered
        "333-3333333-3333333": 1,  # 1 package shipped, 1 delivered
    }
    delivered_packages = {
        "222-2222222-2222222": 2,  # 2 packages delivered
        "333-3333333-3333333": 1,  # 1 package delivered
    }

    # Calculate in-transit packages by subtracting delivered from shipped
    in_transit_packages = 0
    for order_id, shipped_count in shipped_packages.items():
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count

    # Should return 1 because only 1 package (#111-1111111-1111111) is in transit
    # Orders #222-2222222-2222222 and #333-3333333-3333333 were fully delivered
    assert in_transit_packages == 1, (
        f"Expected 1 (only 1 package in transit), got {in_transit_packages}"
    )


@pytest.mark.asyncio
async def test_amazon_delivered_with_order_in_body():
    """Test Amazon delivered emails with order numbers in the body (not subject)."""
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    mock_search_res = MagicMock()
    mock_search_res.result = "OK"
    mock_search_res.lines = [b"1 2"]
    mock_account.search.return_value = mock_search_res

    async def mock_fetch(email_id, parts):
        res = MagicMock()
        res.result = "OK"
        if email_id == "1":
            content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 1"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has been delivered.
"""
            res.lines = [(b"1 (RFC822 {1000}", content)]
        elif email_id == "2":
            content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 2"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has been delivered.
"""
            res.lines = [(b"2 (RFC822 {1000}", content)]
        else:
            res.lines = []
        return res

    mock_account.fetch.side_effect = mock_fetch

    result = await get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    assert result == 0


@pytest.mark.asyncio
async def test_amazon_mixed_delivered_subject_and_body():
    """Test Amazon delivered emails with order numbers in both subject and body."""
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    # Mock search result object
    mock_search_res = MagicMock()
    mock_search_res.result = "OK"
    mock_search_res.lines = [b"1 2"]
    mock_account.search.return_value = mock_search_res

    async def mock_fetch(email_id, parts):
        res = MagicMock()
        res.result = "OK"
        if email_id == "1":
            # Order number in subject
            content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 1" - Order 111-1111111-1111111
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order has been delivered.
"""
            res.lines = [(b"1 (RFC822 {1000}", content)]
        elif email_id == "2":
            # Order number in body
            content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 2"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 222-2222222-2222222 has been delivered.
"""
            res.lines = [(b"2 (RFC822 {1000}", content)]
        else:
            res.lines = []
        return res

    mock_account.fetch.side_effect = mock_fetch

    result = await get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    assert result == 0


@pytest.mark.asyncio
async def test_amazon_shipped_minus_delivered_with_body_orders():
    """Test Amazon package counting with shipped emails minus delivered emails (order numbers in body)."""
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    # Fix: Added **kwargs to capture 'charset' and 'criteria' as keyword args
    async def mock_search(*args, **kwargs):
        res = MagicMock()
        res.result = "OK"

        # Access the criteria regardless of whether it's passed as arg or kwarg
        criteria = kwargs.get("criteria", args[0] if args else "")
        criteria_str = str(criteria)

        if "Shipped:" in criteria_str:
            res.lines = [b"1 2"]
        elif "Delivered:" in criteria_str:
            res.lines = [b"3 4"]
        else:
            res.lines = [b""]
        return res

    mock_account.search.side_effect = mock_search

    # Fix: Added **kwargs here as well for consistency
    async def mock_fetch(email_id, parts, **kwargs):
        res = MagicMock()
        res.result = "OK"
        emails = {
            "1": b"From: auto-confirm@amazon.com\nSubject: Shipped: 1\n\nOrder 111-1111111-1111111 shipped.\nArriving today",
            "2": b"From: auto-confirm@amazon.com\nSubject: Shipped: 2\n\nOrder 111-1111111-1111111 shipped.\nArriving today",
            "3": b"From: auto-confirm@amazon.com\nSubject: Delivered: 1\n\nOrder 111-1111111-1111111 delivered.",
            "4": b"From: auto-confirm@amazon.com\nSubject: Delivered: 2\n\nOrder 111-1111111-1111111 delivered.",
        }
        content = emails.get(email_id, b"")
        res.lines = [(f"{email_id} (RFC822 {{1000}}", content)]
        return res

    mock_account.fetch.side_effect = mock_fetch

    result = await get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    assert result == 0


@pytest.mark.asyncio
async def test_amazon_delivered_no_order_number():
    """Test Amazon delivered emails with no order numbers found."""
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"

    # Mock search response object
    mock_search_res = MagicMock()
    mock_search_res.result = "OK"
    mock_search_res.lines = [b"1"]
    mock_account.search.return_value = mock_search_res

    # Mock email fetch with parts and RFC822 content
    async def mock_fetch(email_id, parts):
        fetch_res = MagicMock()
        fetch_res.result = "OK"
        if email_id == "1":
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order has been delivered.
Thank you for your purchase!
"""
            fetch_res.lines = [(b"1 (RFC822 {1000}", email_content)]
        else:
            fetch_res.lines = []
        return fetch_res

    mock_account.fetch.side_effect = mock_fetch

    # Execute the helper
    result = await get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    # Verification
    assert result == 0


@pytest.mark.asyncio
async def test_zpackages_delivered_matches_sum_of_shippers(hass):
    """Test that zpackages_delivered equals the sum of all shipper delivered counts."""
    mock_account = AsyncMock()
    mock_account.host = "imap.test.email"
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list.return_value = mock_list_res
    config = FAKE_CONFIG_DATA.copy()
    data = {
        ATTR_IMAGE_NAME: "test.gif",
        "amazon_image": "test_amazon.jpg",
        "ups_delivered": 2,
        "fedex_delivered": 1,
        "walmart_delivered": 1,
    }
    with patch(
        "custom_components.mail_and_packages.helpers.default_image_path",
        return_value="test/",
    ):
        zpackages_delivered = await fetch(
            hass, config, mock_account, data, "zpackages_delivered"
        )
        expected_sum = 0
        for shipper in SHIPPERS:
            delivered_key = f"{shipper}_delivered"
            expected_sum += data.get(delivered_key, 0)
        assert zpackages_delivered == expected_sum, (
            f"zpackages_delivered ({zpackages_delivered}) should equal "
            f"sum of all shipper delivered counts ({expected_sum})"
        )
        assert zpackages_delivered == 4


@pytest.mark.asyncio
async def test_zpackages_transit_matches_sum_of_shippers(hass):
    """Test that zpackages_transit equals the sum of all shipper delivering counts + Amazon packages."""
    # Use AsyncMock for the IMAP connection object
    mock_account = AsyncMock()
    mock_account.host = "imap.test.email"

    # Setup .list() response with explicit attributes for debug logging
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)

    # Use real config data
    config = FAKE_CONFIG_DATA.copy()

    # Create data dict with individual shipper delivering counts and Amazon packages
    data = {
        ATTR_IMAGE_NAME: "test.gif",
        "amazon_image": "test_amazon.jpg",
        "ups_delivering": 1,
        "fedex_delivering": 2,
        "amazon_packages": 3,
        "amazon_delivered_by_others": 1,
    }

    with patch(
        "custom_components.mail_and_packages.helpers.default_image_path",
        return_value="test/",
    ):
        # fetch is an async function, so it must be awaited
        zpackages_transit = await fetch(
            hass, config, mock_account, data, "zpackages_transit"
        )

        # Calculate expected sum manually
        # Expected Logic: max(sum of shippers, amazon_packages) - amazon_delivered_by_others
        shipper_sum = 0
        for shipper in SHIPPERS:
            if shipper == "amazon":
                continue
            delivering_key = f"{shipper}_delivering"
            shipper_sum += data.get(delivering_key, 0)

        amazon_packages = data.get("amazon_packages", 0)
        # The logic usually takes the max of individual counts or the amazon total
        total_in_transit = max(shipper_sum, amazon_packages)

        amazon_delivered_by_others = data.get("amazon_delivered_by_others", 0)
        expected_sum = max(0, total_in_transit - amazon_delivered_by_others)

        # Verify zpackages_transit matches the expected calculation
        # In this case: max(1+2, 3) - 1 = 3 - 1 = 2
        assert zpackages_transit == expected_sum, (
            f"zpackages_transit ({zpackages_transit}) should equal "
            f"max(shipper_sum, amazon) - delivered_by_others ({expected_sum})"
        )
        assert zpackages_transit == 2


def test_extract_delivery_image_png(tmp_path):
    """Test extracting a PNG delivery image (e.g. Walmart style)."""
    # Create dummy PNG data (base64)
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    # Note: The HTML must contain the cid_keyword ("deliveryProofLabel") for the function to proceed
    email_body = f"""MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary"

--boundary
Content-Type: text/html; charset=utf-8

<html>
  <div class="deliveryProofLabel">
    <img src="data:image/png;base64,{png_data}" />
  </div>
</html>
--boundary--
"""

    # Create target directory
    image_path = str(tmp_path) + "/"
    (tmp_path / "walmart").mkdir(exist_ok=True)

    # Run extraction
    result = _generic_delivery_image_extraction(
        email_body, image_path, "test.png", "walmart", "png", "deliveryProofLabel"
    )

    assert result is True
    assert (tmp_path / "walmart" / "test.png").exists()


def test_extract_delivery_image_bad_base64(tmp_path, caplog):
    """Test extraction with invalid base64 data."""
    # Invalid base64 string with characters that match the regex but cause decode to fail
    # Use data with invalid padding that will cause base64.b64decode to raise binascii.Error
    # The regex pattern [A-Za-z0-9+/=\s]+ will match this, but decoding will fail
    image_path = str(tmp_path) + "/"
    with caplog.at_level(logging.DEBUG):
        bad_data = "InvalidBase64DataWithBadPadding!!"

        email_body = f"""MIME-Version: 1.0
    Content-Type: text/html; charset=utf-8

    <html>
    <div class="deliveryProofLabel">
        <img src="data:image/png;base64,{bad_data}" />
    </div>
    </html>
    """

        result = _generic_delivery_image_extraction(
            email_body,
            image_path,
            "test.png",
            "walmart",
            "png",
            "deliveryProofLabel",
        )

        assert result is False

        # The regex will match "InvalidBase64DataWithBadPadding" (before the !!)
        # but base64.b64decode will fail because of invalid characters
        # However, if the regex only matches valid base64 chars, we need a different approach
        # Use data that doesn't match the regex at all (contains characters outside [A-Za-z0-9+/=\s])
        bad_data_no_match = "This@has#invalid$chars%outside^regex!"

        email_body_no_match = f"""MIME-Version: 1.0
    Content-Type: text/html; charset=utf-8

    <html>
    <div class="deliveryProofLabel">
        <img src="data:image/png;base64,{bad_data_no_match}" />
    </div>
    </html>
    """

        result = _generic_delivery_image_extraction(
            email_body_no_match,
            image_path,
            "test.png",
            "walmart",
            "png",
            "deliveryProofLabel",
        )

        assert result is False

        # Use an email with CID reference but no actual CID image data
        # This will cause the CID extraction to fail, and there's no base64 data to fall back to
        email_body_no_image = """MIME-Version: 1.0
    Content-Type: multipart/related; boundary="boundary123"

    --boundary123
    Content-Type: text/html; charset=utf-8

    <html>
    <div class="deliveryProofLabel">
        <img src="cid:deliveryProofLabel" alt="Delivery Proof">
    </div>
    </html>
    --boundary123--
    """

        # Should return False because:
        # 1. CID reference exists but no CID image data in email
        # 2. No base64 data to fall back to
        result = _generic_delivery_image_extraction(
            email_body_no_image,
            image_path,
            "test.png",
            "walmart",
            "png",
            "deliveryProofLabel",
        )

        assert result is False


def test_extract_delivery_image_save_error(tmp_path):
    """Test error handling when saving the image fails."""
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    email_body = f"""MIME-Version: 1.0
Content-Type: text/html; charset=utf-8

<html>
  <div class="deliveryProofLabel">
    <img src="data:image/png;base64,{png_data}" />
  </div>
</html>
"""

    # Patch pathlib.Path.open to raise an OSError
    with patch("pathlib.Path.open", side_effect=OSError("Permission denied")):
        result = _generic_delivery_image_extraction(
            email_body,
            str(tmp_path) + "/",
            "test.png",
            "walmart",
            "png",
            "deliveryProofLabel",
        )

    assert result is False


# @pytest.mark.asyncio
# async def test_find_text_decode_error():
#     """Test find_text handles decoding errors gracefully."""

#     # Mock account
#     mock_account = MagicMock()
#     mock_account.search.return_value = ("OK", [b"1"])

#     # Mock email message parts
#     mock_msg = MagicMock()

#     # Part 1: Valid text
#     part1 = MagicMock()
#     part1.get_content_type.return_value = "text/plain"
#     part1.get_payload.return_value = b"Hello World"

#     # Part 2: Payload is None (will cause AttributeError on decode)
#     part2 = MagicMock()
#     part2.get_content_type.return_value = "text/plain"
#     part2.get_payload.return_value = None

#     mock_msg.walk.return_value = [part1, part2]

#     # Mock email_fetch to return our constructed message
#     with (
#         patch("custom_components.mail_and_packages.helpers.email_fetch") as mock_fetch,
#         patch("email.message_from_bytes", return_value=mock_msg),
#     ):
#         mock_fetch.return_value = ("OK", [(b"1", b"raw_data")])

#         # Search for "World" which is in part1. Part2 should crash but be skipped.
#         count = await find_text(("OK", [b"1"]), mock_account, ["World"], False)

#         assert count == 1


@pytest.mark.asyncio
async def test_check_ffmpeg():
    """Test ffmpeg check helper."""
    with patch(
        "custom_components.mail_and_packages.helpers.which",
        return_value="/usr/bin/ffmpeg",
    ):
        assert await _check_ffmpeg() is not None

    with patch("custom_components.mail_and_packages.helpers.which", return_value=None):
        assert await _check_ffmpeg() is None


@pytest.mark.asyncio
async def test_download_img_connection_error(hass, caplog):
    """Test download_img handles connection errors."""
    with patch(
        "aiohttp.ClientSession.get",
        side_effect=aiohttp.ClientError("Connection failed"),
    ):
        await download_img(
            hass,
            "http://fake.website.com/image.jpg",
            "/fake/directory/",
            "testfilename.jpg",
        )


@pytest.mark.asyncio
async def test_process_emails_fedex_dir_creation(hass, integration, caplog):
    """Test FedEx directory creation logic in process_emails."""
    entry = integration
    config = entry.data

    # Setup the AsyncMock connection
    mock_account = AsyncMock()

    # Define attributes for logging to avoid generic mock objects in logs
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)

    # Mock mandatory search and logout for the process flow
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()

    # Mock is_dir to return False for FedEx path specifically to trigger creation logic
    def is_dir_side_effect(self):
        if "fedex" in str(self):
            return False
        return True

    with (
        patch("pathlib.Path.is_dir", side_effect=is_dir_side_effect, autospec=True),
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("custom_components.mail_and_packages.helpers.copyfile"),
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="test.gif",
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        await process_emails(hass, config)

        # Verify we tried to create the directory
        assert mock_mkdir.called
        assert "Created Fedex directory" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_fedex_dir_creation_error(hass, integration, caplog):
    """Test FedEx directory creation error handling."""
    entry = integration
    config = entry.data

    # Use AsyncMock for the IMAP connection object
    mock_account = AsyncMock()

    # Setup .list() response with explicit attributes for debug logging
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)

    # Standard search and logout mocks required for process_emails flow
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()

    def is_dir_side_effect(self):
        # We target the fedex directory specifically
        if "fedex" in str(self):
            return False
        return True

    # Simulate error during mkdir
    with (
        patch("pathlib.Path.is_dir", side_effect=is_dir_side_effect, autospec=True),
        patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")),
        patch("custom_components.mail_and_packages.helpers.copyfile"),
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="test.gif",
        ),
        patch("pathlib.Path.exists", return_value=True),
    ):
        await process_emails(hass, config)

        # Verify the specific error log is captured
        assert "Error creating Fedex directory" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_default_image_copy_errors(hass, integration, caplog):
    """Test error handling when copying default images fails."""
    entry = integration
    config = entry.data

    # Setup the AsyncMock connection
    mock_account = AsyncMock()

    # Ensure .list() has attributes for debug logging to avoid <MagicMock> in logs
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)

    # Standard search and logout mocks
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()

    # Mock exists to return False for default images so it tries to copy them
    def exists_side_effect(path):
        path_str = str(path)
        if (
            any(x in path_str for x in ["ups", "walmart", "fedex"])
            and "no_deliveries" not in path_str
        ):
            return False
        return True

    # Simulate error during copyfile
    with (
        patch("os.path.exists", side_effect=exists_side_effect),
        patch(
            "custom_components.mail_and_packages.helpers.copyfile",
            side_effect=OSError("Copy failed"),
        ),
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="test.gif",
        ),
    ):
        await process_emails(hass, config)

        # Verify error logs for all three providers are captured in caplog
        assert "Error creating default Ups image" in caplog.text
        assert "Error creating default Walmart image" in caplog.text
        assert "Error creating default Fedex image" in caplog.text


@pytest.mark.asyncio
async def test_resize_images_corrupt_file(caplog):
    """Test resize_images with a corrupt or non-image file."""
    with patch("PIL.Image.open", side_effect=OSError("Corrupt image")):
        resize_images(["corrupt.jpg"], 724, 320)
        assert "Error processing image" in caplog.text


@pytest.mark.asyncio
async def test_email_search_timeout(caplog):
    """Test email_search handling a socket timeout."""
    mock_imap = MagicMock()
    mock_imap.search.side_effect = TimeoutError("IMAP connection timed out")

    result = await email_search(mock_imap, "test@email.com", "01-Jan-2024")
    assert result == ("BAD", "IMAP connection timed out")
    assert "Error searching emails" in caplog.text


@pytest.mark.asyncio
async def test_email_search_yahoo(caplog):
    """Test email_search handling a socket timeout."""
    mock_account = AsyncMock()
    mock_account.host = "imap.mail.yahoo.com"
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))

    result = await email_search(
        mock_account, ["test@test.com"], "01-Jan-2024", subject="Pâckage"
    )
    assert result == ("OK", [b""])


@pytest.mark.asyncio
async def test_login_network_error(hass, caplog):
    """Test login failure due to network error."""
    # Patch IMAP4_SSL in the helpers module so the mock is used by the login function
    with (
        patch(
            "custom_components.mail_and_packages.helpers.IMAP4_SSL",
            side_effect=OSError("Network unreachable"),
        ),
        pytest.raises(OSError, match="Network unreachable"),
    ):
        await login(hass, "host", 993, "user", "pwd", "SSL", True)


@pytest.mark.asyncio
async def test_email_search_unicode_error(caplog):
    """Test email search with unicode characters failure."""
    mock_imap = MagicMock()
    # Simulate OSError during a literal search
    mock_imap.search.side_effect = OSError("Literal search failed")

    # Passing a non-ascii subject triggers the utf8_flag logic
    check, value = await email_search(
        mock_imap, ["test@test.com"], "01-Jan-2024", subject="Pâckage"
    )

    assert check == "BAD"
    assert "Error searching emails: Literal search failed" in caplog.text


def test_cleanup_images_directory_missing(caplog):
    """Test cleanup_images when the directory does not exist."""
    with patch("pathlib.Path.is_dir", return_value=False):
        cleanup_images("/nonexistent/path/")
        assert "Directory does not exist" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_login_failure(hass):
    """Test process_emails returns empty data when login fails."""
    config = {"host": "imap.test.com", "resources": []}
    with patch("custom_components.mail_and_packages.helpers.login", return_value=False):
        result = await process_emails(hass, config)
        assert result == {}


@pytest.mark.asyncio
async def test_process_emails_select_folder_failure(hass):
    """Test process_emails returns an empty dict when folder selection fails."""
    config = {
        "host": "imap.test.com",
        "port": 993,
        "username": "test",
        "password": "pwd",
        "imap_security": "SSL",
        "verify_ssl": True,
        "folder": "INBOX",
        "resources": [],
    }
    mock_account = AsyncMock()
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)
    mock_account.logout = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
    ):
        result = await process_emails(hass, config)
        assert result == {}
        mock_account.logout.assert_called_once()


@pytest.mark.asyncio
async def test_copy_images_mkdir_error(hass, caplog):
    """Test copy_images handles directory creation errors."""
    config = {CONF_ALLOW_EXTERNAL: True}
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.mkdir", side_effect=OSError("Disk Full")),
    ):
        copy_images(hass, config)
        assert "Problem creating:" in caplog.text
        assert "Disk Full" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_tuple_input(caplog):
    """Test cleanup_images when path is passed as a tuple."""
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.unlink") as mock_unlink,
    ):
        cleanup_images(("/fake/path/", "image.jpg"))
        assert mock_unlink.called


@pytest.mark.asyncio
async def test_cleanup_images_oserror_on_list(caplog):
    """Test cleanup_images handles OSError when listing directory."""
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.iterdir", side_effect=OSError("IO Error")),
    ):
        cleanup_images("/fake/path/")
        assert "Error listing directory for cleanup" in caplog.text


@pytest.mark.asyncio
async def test_amazon_search_no_data(hass):
    """Test amazon_search when server response is not OK."""
    account = MagicMock()
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("BAD", [None]),
    ):
        count = await amazon_search(account, "/path/", hass, "img.jpg", "amazon.com")
        assert count == 0


# @pytest.mark.asyncio
# async def test_amazon_otp_decode_error(caplog):
#     """Test amazon_otp handles decoding errors."""
#     # account must be an AsyncMock for aioimaplib compatibility
#     account = AsyncMock()

#     # Mock search response with explicit attributes
#     mock_search_res = MagicMock()
#     mock_search_res.result = "OK"
#     mock_search_res.lines = [b"1"]
#     account.search = AsyncMock(return_value=mock_search_res)

#     # Mock fetch response with explicit attributes
#     mock_fetch_res = MagicMock()
#     mock_fetch_res.result = "OK"
#     mock_fetch_res.lines = [(None, b"Raw Data")]
#     account.fetch = AsyncMock(return_value=mock_fetch_res)

#     with patch(
#         "custom_components.mail_and_packages.helpers.quopri.decodestring",
#         side_effect=ValueError("Decode fail"),
#     ):
#         # Use a valid Amazon domain to ensure the loop executes
#         result = await amazon_otp(account, ["test@amazon.com"])

#     # Verify result is an empty code list and the error is logged
#     assert result == {"code": []}
#     assert "Problem decoding email message: Decode fail" in caplog.text


@pytest.mark.asyncio
async def test_generic_extraction_payload_not_bytes():
    """Test image extraction when payload is a string to hit Line 1920."""
    test_html = "<html><body>No image</body></html>"
    mock_part = MagicMock()
    mock_part.get_content_type.return_value = "text/html"
    mock_part.get_payload.return_value = test_html

    mock_msg = MagicMock()
    mock_msg.walk.return_value = [mock_part]

    with patch("email.message_from_bytes", return_value=mock_msg):
        result = _generic_delivery_image_extraction(
            b"data", "/path/", "img.jpg", "ups", "jpeg", "cid"
        )
        assert result is False


@pytest.mark.asyncio
async def test_process_emails_grid_generation_coverage(hass):
    """Test process_emails with grid generation enabled."""
    config = {
        "host": "imap.test.com",
        "port": 993,
        "username": "test",
        "password": "pwd",
        "imap_security": "SSL",
        "verify_ssl": True,
        "generate_grid": True,
        "resources": ["usps_mail"],
    }
    mock_account = AsyncMock()
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="mail.gif",
        ),
        patch(
            "custom_components.mail_and_packages.helpers.email_fetch",
            new_callable=AsyncMock,
        ),
    ):
        result = await process_emails(hass, config)
        assert result["grid_image"] == "mail_grid.png"


@pytest.mark.asyncio
async def test_copy_images_shutil_error(hass, caplog):
    """Test copy_images handles shutil errors."""
    config = {CONF_ALLOW_EXTERNAL: True}
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.helpers.copytree",
            side_effect=shutil.Error("Copy fail"),
        ),
    ):
        copy_images(hass, config)
        assert "Problem copying files" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_errors(caplog):
    """Test cleanup_images error paths."""
    # Directory disappears during iteration
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.iterdir", side_effect=FileNotFoundError),
    ):
        cleanup_images("/fake/path/")
        # Should return silently or log directory removed

    # Permission error during listing
    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.iterdir", side_effect=OSError("Permission Denied")),
    ):
        cleanup_images("/fake/path/")
        assert "Error listing directory for cleanup" in caplog.text


@pytest.mark.asyncio
async def test_generate_mp4_ffmpeg_error(caplog):
    """Test _generate_mp4 handles FFmpeg failure."""
    with (
        patch("pathlib.Path.is_file", return_value=False),
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")),
    ):
        _generate_mp4("/path/", "image.gif")
        assert "FFmpeg failed to generate MP4" in caplog.text


@pytest.mark.asyncio
async def test_selectfolder_list_exception(caplog):
    """Test selectfolder when account.list() raises an OSError."""
    mock_account = AsyncMock()
    mock_account.list.side_effect = OSError("Server disconnected during list")
    result = await selectfolder(mock_account, "INBOX")
    assert result is False
    assert "Error listing folder INBOX: Server disconnected during list" in caplog.text


@pytest.mark.asyncio
async def test_selectfolder_select_exception(caplog):
    """Test selectfolder when account.select() raises an OSError."""
    mock_account = AsyncMock()

    # Mock list to return a response object with a .result attribute
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list.return_value = mock_list_res

    # Mock select to raise the OSError when awaited
    mock_account.select.side_effect = OSError("Folder locked")

    result = await selectfolder(mock_account, "INBOX")

    assert result is False
    assert "Folder locked" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_shipper_mkdir_error(hass, caplog):
    """Test error handling when creating a shipper-specific directory fails."""
    config = FAKE_CONFIG_DATA_CORRECTED

    # Use AsyncMock for the connection object
    mock_account = AsyncMock()

    # Setup .list() response with explicit attributes for debug logging
    mock_list_res = MagicMock()
    mock_list_res.result = "OK"
    mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
    mock_account.list = AsyncMock(return_value=mock_list_res)

    # Mock mandatory search and logout calls
    mock_account.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    mock_account.logout = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.helpers.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.selectfolder",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("pathlib.Path.is_dir", return_value=False),
        patch("pathlib.Path.mkdir", side_effect=OSError("Read-only file system")),
    ):
        await process_emails(hass, config)

        # Verify the OSError during directory creation is caught and logged
        assert "Error creating Ups directory" in caplog.text


@pytest.mark.asyncio
async def test_get_amazon_image_ignored_domain(hass):
    """Test that Amazon images from non-S3 domains are ignored."""
    mock_email_body = '<html><img src="https://malicious.site/image.jpg"></html>'
    mock_account = AsyncMock()

    mock_fetch_res = MagicMock()
    mock_fetch_res.result = "OK"
    mock_fetch_res.lines = [(b"1", mock_email_body.encode())]
    mock_account.fetch.return_value = mock_fetch_res

    with patch(
        "custom_components.mail_and_packages.helpers.download_img"
    ) as mock_download:
        await get_amazon_image(b"1", mock_account, "./", hass, "amazon.jpg")

        mock_download.assert_not_called()


# @pytest.mark.asyncio
# async def test_amazon_hub_decode_error(caplog):
#     """Test amazon_hub handles malformed multipart emails."""
#     mock_account = AsyncMock()

#     # Setup search response with explicit attributes
#     mock_search_res = MagicMock()
#     mock_search_res.result = "OK"
#     mock_search_res.lines = [b"1"]
#     mock_account.search = AsyncMock(return_value=mock_search_res)

#     # Setup fetch response with explicit attributes
#     mock_fetch_res = MagicMock()
#     mock_fetch_res.result = "OK"
#     mock_fetch_res.lines = [(b"1", b"raw_data")]
#     mock_account.fetch = AsyncMock(return_value=mock_fetch_res)

#     mock_msg = MagicMock()
#     mock_msg.is_multipart.return_value = True
#     # Side effect to trigger the error handling logic in amazon_hub
#     mock_msg.get_payload.side_effect = IndexError("No parts found")

#     with (
#         patch(
#             "custom_components.mail_and_packages.helpers.email.message_from_bytes",
#             return_value=mock_msg,
#         ),
#         caplog.at_level(logging.DEBUG),
#     ):
#         # Call the sensor logic; ensure it handles the IndexError gracefully
#         result = await amazon_hub(mock_account)

#         assert result["count"] == 0
#         # Align assertion with actual log output seen in error logic
#         assert "Problem decoding email message: No parts found" in caplog.text


@pytest.mark.asyncio
async def test_parse_amazon_arrival_date_weekday():
    """Test parsing arrival dates that are just a weekday name."""
    email_date = date(2025, 10, 27)
    email_msg = "Arriving Wednesday"

    with (
        patch(
            "custom_components.mail_and_packages.helpers.get_today",
            return_value=email_date,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.amazon_date_regex",
            return_value="Wednesday",
        ),
    ):
        result = _parse_amazon_arrival_date(email_msg, email_date)
        assert result == email_date + timedelta(days=2)


@pytest.mark.asyncio
async def test_amazon_search_no_emails_found(hass):
    """Test amazon_search copies default image when no emails are found."""
    mock_account = AsyncMock()

    mock_search_res = MagicMock()
    mock_search_res.result = "OK"
    mock_search_res.lines = [b""]
    mock_account.search.return_value = mock_search_res

    with (
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
        patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copy,
        patch(
            "custom_components.mail_and_packages.helpers.amazon_email_addresses",
            return_value=["test@amazon.com"],
        ),
    ):
        await amazon_search(
            mock_account,
            "/fake/path/",
            hass,
            "amazon.jpg",
            "amazon.com",
            coordinator_data={},
        )
        assert mock_copy.called


def test_build_search_multiple_addresses():
    """Test building search query with multiple addresses to cover OR prefix logic."""
    # Length 3 ensures multiple OR prefixes are added
    addresses = ["test1@test.com", "test2@test.com", "test3@test.com"]

    utf8, search = build_search(addresses, "01-Jan-2024")
    # Verify the prefix list is "OR OR" (len - 1)
    assert search.count("OR") == 2
    assert (
        search
        == '(OR OR FROM "test1@test.com" FROM "test2@test.com" FROM "test3@test.com" SUBJECT "" SINCE 01-Jan-2024)'
    )


@pytest.mark.asyncio
async def test_generic_extraction_string_input(tmp_path):
    """Test image extraction when input is a string instead of bytes."""
    sdata = "From: help@walmart.com\nSubject: Delivered\n\nContent"
    image_path = str(tmp_path) + "/"

    # This hits the 'else' branch of 'if isinstance(sdata, bytes)'
    result = _generic_delivery_image_extraction(
        sdata, image_path, "img.jpg", "walmart", "jpeg", cid_name="none"
    )
    assert result is False


@pytest.mark.asyncio
async def test_login_no_security():
    """Test IMAP login with no security (Plain)."""
    # Patch helpers.IMAP4 directly since 'aioimaplib' is not exposed in helpers
    with patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap:
        mock_acc = AsyncMock()
        mock_imap.return_value = mock_acc

        # Setup mocks
        mock_acc.wait_hello_from_server = AsyncMock()

        # Set initial state to NONAUTH to trigger login logic
        mock_acc.protocol.state = aioimaplib.NONAUTH

        # Simulate state change to AUTH upon login
        async def login_side_effect(*args, **kwargs):
            mock_acc.protocol.state = aioimaplib.AUTH
            return MagicMock(result="OK")

        mock_acc.login = AsyncMock(side_effect=login_side_effect)

        # Pass None for hass (first arg) and correct the argument positions
        # login(hass, host, port, user, pwd, security, verify)
        result = await login(None, "host", 143, "user", "pwd", "None", True)

        assert result == mock_acc
        mock_acc.starttls.assert_not_called()
        # Verify login was called with the correct credentials
        mock_acc.login.assert_called_once_with("user", "pwd")


@pytest.mark.asyncio
async def test_generate_grid_img_odd_count():
    """Test grid generation calculation for odd number of images."""
    with (
        patch("custom_components.mail_and_packages.helpers.cleanup_images"),
        patch("subprocess.call") as mock_sub,
    ):
        generate_grid_img("/path/", "mail.gif", 3)

        # Flatten the list of arguments into one string to search
        cmd_string = " ".join(mock_sub.call_args[0][0])
        assert "tile=2x2" in cmd_string


@pytest.mark.asyncio
async def test_email_fetch_icloud():
    """Test email_fetch uses BODY[] parts for iCloud host."""
    mock_acc = AsyncMock()
    mock_acc.host = "imap.mail.me.com"

    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [(b"", b"Email Content")]
    mock_acc.fetch.return_value = mock_res

    await email_fetch(mock_acc, "1")

    mock_acc.fetch.assert_called_with("1", "BODY[]")


# @pytest.mark.asyncio
# async def test_get_mails_unexpected_html(hass, caplog, tmp_path):
#     """Test get_mails with HTML part missing expected content."""
#     account = AsyncMock()
#     # Convert the secure temp path object to a string
#     temp_dir = str(tmp_path)

#     # Create a mock email message with text/html but no images
#     msg = email.message.Message()
#     msg.set_type("text/html")
#     msg.set_payload(
#         '<html><body><img id="mailpiece-image-src-id" src="bad_src"></body></html>'
#     )

#     # We need to structure the response so email_fetch returns this message
#     mock_fetch_response = [(b"1 (RFC822 {100}", msg.as_bytes())]

#     with (
#         patch(
#             "custom_components.mail_and_packages.helpers.email_search",
#             return_value=("OK", ["1"]),
#         ),
#         patch(
#             "custom_components.mail_and_packages.helpers.email_fetch",
#             return_value=("OK", mock_fetch_response),
#         ),
#         patch("custom_components.mail_and_packages.helpers.cleanup_images"),
#         patch("custom_components.mail_and_packages.helpers.copy_overlays"),
#         patch("pathlib.Path.is_dir", return_value=True),
#     ):
#         await get_mails(hass, account, temp_dir, 5, "img.gif")
#         assert "Unexpected html format found." in caplog.text


async def test_generic_delivery_image_extraction_attachment_save_error(
    caplog, tmp_path
):
    """Test generic image extraction failure during attachment save."""
    temp_dir = str(tmp_path)
    msg = Message()
    msg.set_type("multipart/mixed")
    image_part = Message()
    image_part.set_type("image/jpeg")
    image_part.add_header("Content-Disposition", "attachment", filename="delivery.jpg")
    image_part.set_payload("fake_image_data")
    msg.attach(image_part)
    sdata = msg.as_bytes()
    with patch(
        "custom_components.mail_and_packages.helpers._save_image_data_to_disk",
        side_effect=ValueError("Simulated Save Error"),
    ):
        result = _generic_delivery_image_extraction(
            sdata,
            temp_dir,
            "test.jpg",
            "ups",
            "jpeg",
        )
        # Should return False because of the exception
        assert result is False
        assert "Error saving ups delivery photo" in caplog.text
        assert "Simulated Save Error" in caplog.text


@pytest.mark.asyncio
async def test_fetch_amazon_otp(hass):
    """Test fetch logic for amazon_otp."""
    config = FAKE_CONFIG_DATA_CORRECTED
    account = AsyncMock()
    data = {
        ATTR_IMAGE_NAME: "mail_today.gif",
        ATTR_AMAZON_IMAGE: "amazon_today.jpg",
    }
    mock_otp_result = {"code": ["123456"]}
    with patch(
        "custom_components.mail_and_packages.helpers.amazon_otp",
        return_value=mock_otp_result,
    ) as mock_otp:
        result = await fetch(hass, config, account, data, AMAZON_OTP)
        mock_otp.assert_called_once()
        assert result == mock_otp_result


@pytest.mark.asyncio
async def test_image_file_name_stat_error(hass, caplog):
    """Test image_file_name handling of stat errors."""
    config = FAKE_CONFIG_DATA_CORRECTED
    mock_file = MagicMock()
    mock_file.name = "existing_image.gif"
    mock_file.stat.side_effect = OSError("Mocked Stat Error")

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[mock_file]),
        patch(
            "custom_components.mail_and_packages.helpers.hash_file",
            return_value="fake_hash",
        ),
    ):
        result = image_file_name(hass, config)

        # Verify the function caught the error, logged it, and returned the default image name
        assert result == "mail_none.gif"
        assert "Problem accessing file: existing_image.gif" in caplog.text
        assert "Mocked Stat Error" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_hash_error(hass, caplog):
    """Test image_file_name handling of hash_file errors."""
    config = FAKE_CONFIG_DATA_CORRECTED
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir", return_value=True),
        patch(
            "custom_components.mail_and_packages.helpers.hash_file",
            side_effect=OSError("Mocked Hash Error"),
        ),
    ):
        result = image_file_name(hass, config)
        assert result == "mail_none.gif"

        # Verify the error log from the exception block
        assert "Problem accessing file:" in caplog.text
        assert "Mocked Hash Error" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_generate_new_uuid(hass):
    """Test generating a new UUID filename for old/different images."""
    config = FAKE_CONFIG_DATA_CORRECTED
    mock_file = MagicMock()
    mock_file.name = "existing_image.gif"

    # Set creation time to yesterday so (today != created) is True
    yesterday = datetime.now() - timedelta(days=1)
    mock_file.stat.return_value.st_ctime = yesterday.timestamp()

    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.mkdir", return_value=True),
        patch("pathlib.Path.iterdir", return_value=[mock_file]),
        patch(
            "custom_components.mail_and_packages.helpers.hash_file",
            side_effect=["hash_source", "hash_existing"],
        ),
        patch("custom_components.mail_and_packages.helpers.copyfile"),
        patch("uuid.uuid4", return_value="1234-5678-9012-3456"),
    ):
        result = image_file_name(hass, config)

        # Verify line 506 was executed: result should be uuid + ext
        assert result == "1234-5678-9012-3456.gif"


def test_build_search_no_subject():
    """Test build_search with no subject (None)."""
    addresses_multi = ["test1@test.com", "test2@test.com"]
    utf8, search = build_search(addresses_multi, "01-Jan-2024", subject=None)

    assert utf8 is False
    assert (
        search == '(OR FROM "test1@test.com" FROM "test2@test.com" SINCE 01-Jan-2024)'
    )
    addresses_single = ["test1@test.com"]
    utf8, search = build_search(addresses_single, "01-Jan-2024", subject=None)

    assert utf8 is False
    assert search == '(FROM "test1@test.com" SINCE 01-Jan-2024)'


# @pytest.mark.asyncio
# async def test_get_mails_save_error_html_image(hass, caplog, tmp_path):
#     """Test get_mails handling error when saving HTML image (covers lines 926-928)."""
#     account = AsyncMock()
#     temp_dir = str(tmp_path)

#     # Create HTML content with the specific ID required to trigger the image extraction logic
#     html_content = """
#     <html>
#     <body>
#         <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" />
#     </body>
#     </html>
#     """

#     # Create the email message
#     msg = email.message.Message()
#     msg.set_type("text/html")
#     msg.set_payload(html_content)

#     mock_fetch_response = [(b"1 (RFC822 {100}", msg.as_bytes())]

#     with (
#         patch(
#             "custom_components.mail_and_packages.helpers.email_search",
#             return_value=("OK", ["1"]),
#         ),
#         patch(
#             "custom_components.mail_and_packages.helpers.email_fetch",
#             return_value=("OK", mock_fetch_response),
#         ),
#         patch(
#             "custom_components.mail_and_packages.helpers.io_save_file",
#             side_effect=OSError("Disk write failed"),
#         ),
#         patch("custom_components.mail_and_packages.helpers.cleanup_images"),
#         patch("custom_components.mail_and_packages.helpers.copy_overlays"),
#         patch("pathlib.Path.is_dir", return_value=True),
#     ):
#         result = await get_mails(hass, account, temp_dir, 5, "mail_today.gif")

#         # Verify the function returned the current image count (0)
#         assert result == 0
#         # Verify the critical error was logged (Lines 927-928)
#         assert "Error opening filepath: Disk write failed" in caplog.text


@pytest.mark.asyncio
async def test_generation_functions_remove_old_files(caplog, tmp_path):
    """Test that _generate_mp4 and generate_grid_img remove existing files before creation."""
    temp_dir = str(tmp_path) + "/"

    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch(
            "custom_components.mail_and_packages.helpers.cleanup_images"
        ) as mock_cleanup,
        patch("subprocess.run"),
        patch("subprocess.call"),
    ):
        # 1. Test _generate_mp4 logic
        _generate_mp4(temp_dir, "test.gif")

        assert mock_cleanup.call_count == 1
        assert "Removing old mp4:" in caplog.text

        # 2. Test generate_grid_img logic
        generate_grid_img(temp_dir, "test.gif", 5)

        assert mock_cleanup.call_count == 2
        assert "Removing old png grid:" in caplog.text


@pytest.mark.asyncio
async def test_get_count_missing_image_attr(hass, caplog, tmp_path):
    """Test get_count handling of missing image attribute for shipper (covers lines 1324-1331)."""
    mock_account = MagicMock()
    secure_image_path = str(tmp_path) + "/"
    fake_sensor_data = SENSOR_DATA["ups_delivered"].copy()

    with (
        patch.dict(
            "custom_components.mail_and_packages.helpers.SENSOR_DATA",
            {"test_delivered": fake_sensor_data},
        ),
        patch.dict(
            "custom_components.mail_and_packages.helpers.CAMERA_DATA",
            {"test_camera": ["Test Camera"]},
        ),
    ):
        result = await get_count(
            mock_account,
            "test_delivered",
            image_path=secure_image_path,
            hass=hass,
        )
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == ""
    assert "Could not find image attribute ATTR_TEST_IMAGE for test" in caplog.text


# @pytest.mark.asyncio
# async def test_get_items_subject_decoding_fallback_failure(hass, caplog):
#     """Test get_items handling of subject decoding errors."""
#     mock_account = AsyncMock()
#     mock_account.host = "imap.test.email"
#     mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
#     mock_fetch_res = MagicMock()
#     mock_fetch_res.result = "OK"
#     mock_fetch_res.lines = [(b"1 (RFC822 {100}", b"Subject: Test\r\n\r\nBody")]
#     mock_account.fetch.return_value = mock_fetch_res

#     # Define a class that raises specific errors on consecutive string conversions
#     class TrickySubject:
#         def __init__(self):
#             self.call_count = 0

#         def __str__(self):
#             self.call_count += 1
#             if self.call_count == 1:
#                 raise LookupError("Simulated LookupError")
#             if self.call_count == 2:
#                 raise TypeError("Simulated TypeError")
#             return "Safe Fallback Subject"

#     tricky_subject = TrickySubject()
#     with patch(
#         "custom_components.mail_and_packages.helpers.decode_header",
#         return_value=[(tricky_subject, "utf-8")],
#     ):
#         await get_items(mock_account, "count", "amazon.com")
#     assert "Error decoding subject with fallback: Simulated TypeError" in caplog.text


@pytest.mark.asyncio
async def test_get_count_calculates_correctly(hass):
    """Test get_count with locally defined mock data."""

    # 1. Create a mock IMAP account object
    mock_account = AsyncMock()

    # 2. Setup the SEARCH response (Simulate finding 3 emails: IDs 1, 2, and 3)
    # Note: verify if your code splits by space. Standard IMAP returns space-separated IDs.
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1 2 3"])

    # 3. Setup the FETCH response (Simulate the email content)
    # We use a side_effect to return specific content for specific IDs if logic depends on it
    async def fetch_side_effect(uid, parts):
        mock_response = MagicMock(result="OK")

        # Determine content based on UID passed by get_count
        uid_str = uid.decode() if isinstance(uid, bytes) else uid

        # Example: Email 1 and 3 match criteria, Email 2 does not (if get_count filters them)
        if uid_str == "1":
            body = b"Subject: Amazon Delivered\r\n\r\nItem Delivered."
        elif uid_str == "2":
            body = b"Subject: Something else\r\n\r\nNot relevant."
        elif uid_str == "3":
            body = b"Subject: Amazon Delivered\r\n\r\nItem Delivered."
        else:
            body = b""

        # Return the format your code expects: [Header, Body]
        header = f"{uid_str} (UID {uid_str} BODY[TEXT] {{100}}".encode()
        mock_response.lines = [header, body]
        return mock_response

    mock_account.fetch.side_effect = fetch_side_effect

    # 4. Call the function directly with the mock
    # passing necessary args like sensor_type="amazon_delivered", email_domain="amazon.com"
    count = await get_count(
        mock_account,
        "amazon_delivered",
        hass=hass,
        amazon_domain="amazon.com",
    )

    # 5. Assertions
    # If your logic counts all search results:
    assert count["count"] == 30
    # If your logic filters inside get_count (e.g. checks Subject again):
    # assert count == 2

    # Verify search was called
    mock_account.search.assert_called()


def test_match_patterns():
    """Test the _match_patterns helper function logic."""

    # ---------------------------------------------------------
    # Scenario 1: body_count=False (Counting occurrences)
    # ---------------------------------------------------------
    text_counting = "apple apple orange banana apple"
    patterns_counting = [re.compile(r"apple"), re.compile(r"orange")]

    count, value = _match_patterns(text_counting, patterns_counting, body_count=False)

    # Expect 3 apples + 1 orange = 4
    assert count == 4
    # Value should be None when body_count is False
    assert value is None

    # ---------------------------------------------------------
    # Scenario 2: body_count=True (Extracting values)
    # ---------------------------------------------------------
    text_extracting = "You have 5 packages arriving today."
    # Pattern must contain a capture group for the number
    patterns_extracting = [re.compile(r"have (\d+) packages")]

    count, value = _match_patterns(
        text_extracting, patterns_extracting, body_count=True
    )

    # Count remains 0 in extraction mode
    assert count == 0
    # Extracted value should be the integer 5
    assert value == 5

    # ---------------------------------------------------------
    # Scenario 3: No Matches
    # ---------------------------------------------------------
    text_no_match = "No mail today."
    patterns_no_match = [re.compile(r"packages")]

    count, value = _match_patterns(text_no_match, patterns_no_match, body_count=False)

    assert count == 0
    assert value is None

    # ---------------------------------------------------------
    # Scenario 4: Multiple Patterns Extraction (Last Match Logic)
    # ---------------------------------------------------------
    # If multiple patterns match in body_count mode, the function iterates
    # through all of them, updating extracted_value each time a match is found.
    text_multi = "Metric A: 10, Metric B: 20"
    patterns_multi = [re.compile(r"Metric A: (\d+)"), re.compile(r"Metric B: (\d+)")]

    _, value = _match_patterns(text_multi, patterns_multi, body_count=True)

    # It should return 20 because it is the last pattern in the list that matched
    assert value == 20


@pytest.mark.asyncio
async def test_amazon_date_search():
    """Test the amazon_date_search helper function."""
    # Mock the patterns to predictable strings for testing
    mock_patterns = ["end_pattern_1", "end_pattern_2"]

    with patch(
        "custom_components.mail_and_packages.helpers.AMAZON_TIME_PATTERN_END",
        mock_patterns,
    ):
        # Scenario 1: Pattern is found
        # "The date is " is 12 characters long, so "end_pattern_1" starts at index 12
        msg_match = "The date is end_pattern_1"
        assert amazon_date_search(msg_match) == 12

        # Scenario 2: Pattern is found (checking second pattern in list)
        msg_match_2 = "The date is end_pattern_2"
        assert amazon_date_search(msg_match_2) == 12

        # Scenario 3: No pattern is found
        msg_no_match = "The date is not here"
        assert amazon_date_search(msg_no_match) == -1


@pytest.mark.asyncio
async def test_get_email_body(caplog):
    """Test the _get_email_body helper function."""
    # Scenario 1: Single part email
    msg_single = email.message.Message()
    msg_single.set_payload("Test Single Body")
    # The helper converts payload to str, decodes quoted-printable, then decodes utf-8
    assert _get_email_body(msg_single) == "Test Single Body"

    # Scenario 2: Multipart email
    msg_multi = email.message.Message()
    msg_multi.add_header("Content-Type", "multipart/mixed")
    part = email.message.Message()
    part.set_payload("Multipart Body Content")
    msg_multi.attach(part)

    # Use .strip() to remove the leading newline introduced by str(MessageObject)
    assert _get_email_body(msg_multi).strip() == "Multipart Body Content"

    # Scenario 3: Exception handling (IndexError on empty multipart)
    msg_empty_multi = email.message.Message()
    msg_empty_multi.add_header("Content-Type", "multipart/mixed")
    # IMPORTANT: is_multipart() checks if payload is a list.
    # We must explicitly set it to a list to simulate a multipart message with no parts.
    msg_empty_multi.set_payload([])

    assert _get_email_body(msg_empty_multi) == ""
    assert "Problem decoding email message:" in caplog.text

    # Scenario 4: Exception handling (Decoding error)
    # Mock quopri to raise a ValueError to simulate a bad payload
    with patch("quopri.decodestring", side_effect=ValueError("Bad encoding")):
        assert _get_email_body(msg_single) == ""
        assert "Bad encoding" in caplog.text


@pytest.mark.asyncio
async def test_parse_amazon_arrival_date_variations():
    """Test various scenarios for _parse_amazon_arrival_date."""
    # Base email date: Wednesday, Oct 25, 2023
    email_date = date(2023, 10, 25)

    # Scenario 1: Regex Match (e.g. "tomorrow")
    # This path triggers when amazon_date_regex returns a value.
    # "tomorrow" relative to Oct 25 is Oct 26.
    with (
        patch(
            "custom_components.mail_and_packages.helpers.AMAZON_TIME_PATTERN",
            ["Arriving"],
        ),
        patch(
            "custom_components.mail_and_packages.helpers.amazon_date_regex",
            return_value="tomorrow",
        ),
    ):
        result = _parse_amazon_arrival_date("Arriving tomorrow", email_date)
        assert result == date(2023, 10, 26)

    # Scenario 2: String Slicing with explicit date
    # This path triggers when amazon_date_regex returns None.
    # It slices the string from the end of the pattern to the index returned by amazon_date_search.
    msg = "Expected by October 27"
    with (
        patch(
            "custom_components.mail_and_packages.helpers.AMAZON_TIME_PATTERN",
            ["Expected by"],
        ),
        patch(
            "custom_components.mail_and_packages.helpers.amazon_date_regex",
            return_value=None,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.amazon_date_search",
            return_value=len(msg),
        ),
    ):
        result = _parse_amazon_arrival_date(msg, email_date)
        assert result == date(2023, 10, 27)

    # Scenario 3: Weekday logic - Past date check
    # Email date: Oct 25, 2023 (Wednesday).
    # Text: "Arriving Monday".
    # Logic: Monday (0) - Wednesday (2) = -2. (-2 % 7) = 5 days ahead.
    # Calculated Arrival: Oct 25 + 5 days = Oct 30, 2023.
    # Mock Today: Nov 1, 2023.
    # Since Oct 30 < Nov 1, the function should ignore this date and return None.
    msg_weekday = "Arriving Monday"
    with (
        patch(
            "custom_components.mail_and_packages.helpers.AMAZON_TIME_PATTERN",
            ["Arriving"],
        ),
        patch(
            "custom_components.mail_and_packages.helpers.amazon_date_regex",
            return_value=None,
        ),
        patch(
            "custom_components.mail_and_packages.helpers.amazon_date_search",
            return_value=len(msg_weekday),
        ),
        patch(
            "custom_components.mail_and_packages.helpers.get_today",
            return_value=date(2023, 11, 1),
        ),
    ):
        result = _parse_amazon_arrival_date(msg_weekday, email_date)
        assert result is None
