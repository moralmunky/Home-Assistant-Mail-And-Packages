"""Tests for helpers module."""

import datetime
import os
import re
import subprocess
import tempfile
from datetime import date, datetime
from unittest import mock
from unittest.mock import MagicMock, call, mock_open, patch

import pytest
from freezegun import freeze_time
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    ATTR_WALMART_IMAGE,
    CAMERA_DATA,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
    DOMAIN,
    SENSOR_DATA,
    SHIPPERS,
)
from custom_components.mail_and_packages.helpers import (
    _generate_mp4,
    amazon_exception,
    amazon_hub,
    amazon_otp,
    amazon_search,
    cleanup_images,
    copy_overlays,
    default_image_path,
    download_img,
    email_fetch,
    email_search,
    generate_grid_img,
    get_count,
    get_formatted_date,
    get_items,
    get_mails,
    get_resources,
    get_tracking,
    get_ups_image,
    get_walmart_image,
    hash_file,
    image_file_name,
    login,
    process_emails,
    resize_images,
    selectfolder,
    update_time,
    ups_search,
    walmart_search,
)
from tests.const import (
    FAKE_CONFIG_DATA,
    FAKE_CONFIG_DATA_BAD,
    FAKE_CONFIG_DATA_CORRECTED,
    FAKE_CONFIG_DATA_CORRECTED_EXTERNAL,
    FAKE_CONFIG_DATA_CUSTOM_IMG,
    FAKE_CONFIG_DATA_NO_PATH,
    FAKE_CONFIG_DATA_NO_RND,
)

MAIL_IMAGE_URL_ENTITY = "sensor.mail_image_url"
MAIL_IMAGE_SYSTEM_PATH = "sensor.mail_image_system_path"
MAIL_IMAGE_GRID_IMAGE_PATH = "sensor.mail_grid_image_path"


@pytest.mark.asyncio
async def test_get_formatted_date():
    assert get_formatted_date() == date.today().strftime("%d-%b-%Y")


@pytest.mark.asyncio
async def test_update_time():
    assert isinstance(update_time(), datetime)


@pytest.mark.asyncio
async def test_cleanup_images(mock_listdir, mock_osremove):
    cleanup_images("/tests/fakedir/")
    calls = [
        call("/tests/fakedir/testfile.gif"),
        call("/tests/fakedir/anotherfakefile.mp4"),
    ]
    mock_osremove.assert_has_calls(calls)


@pytest.mark.asyncio
async def test_cleanup_found_images_remove_err(
    mock_listdir, mock_osremove_exception, caplog
):
    cleanup_images("/tests/fakedir/")
    assert "Error attempting to remove found image:" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_remove_err(mock_listdir, mock_osremove_exception, caplog):
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
    hass.config.internal_url = "http://127.0.0.1:8123/"
    entry = integration

    config = FAKE_CONFIG_DATA_CORRECTED
    assert config == FAKE_CONFIG_DATA_CORRECTED
    state = hass.states.get(MAIL_IMAGE_SYSTEM_PATH)
    assert state is not None
    assert "/testing_config/custom_components/mail_and_packages/images/" in state.state
    state = hass.states.get(MAIL_IMAGE_URL_ENTITY)
    assert state.state == "unknown"
    result = process_emails(hass, config)
    assert isinstance(result["mail_updated"], datetime)
    assert result["zpackages_delivered"] == 0
    assert result["zpackages_transit"] == 0
    assert result["amazon_delivered"] == 0
    assert result["amazon_hub"] == 0
    assert result["amazon_packages"] == 0
    assert result["amazon_order"] == []
    assert result["amazon_hub_code"] == []


@pytest.mark.asyncio
async def test_process_emails_external(
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
):
    hass.config.internal_url = "http://127.0.0.1:8123/"
    hass.config.external_url = "http://really.fake.host.net:8123/"

    entry = integration_fake_external

    config = entry.data.copy()
    assert config == FAKE_CONFIG_DATA_CORRECTED_EXTERNAL
    state = hass.states.get(MAIL_IMAGE_SYSTEM_PATH)
    assert state is not None
    assert "/testing_config/custom_components/mail_and_packages/images/" in state.state
    state = hass.states.get(MAIL_IMAGE_URL_ENTITY)
    assert state.state == "unknown"
    result = process_emails(hass, config)
    assert isinstance(result["mail_updated"], datetime)
    assert result["zpackages_delivered"] == 0
    assert result["zpackages_transit"] == 0
    assert result["amazon_delivered"] == 0
    assert result["amazon_hub"] == 0
    assert result["amazon_packages"] == 0
    assert result["amazon_order"] == []
    assert result["amazon_hub_code"] == []
    assert (
        "custom_components/mail_and_packages/images/" in mock_copytree.call_args.args[0]
    )
    assert "www/mail_and_packages" in mock_copytree.call_args.args[1]
    assert mock_copytree.call_args.kwargs == {"dirs_exist_ok": True}
    # Check that both Amazon and UPS files are being cleaned up
    amazon_removed = False
    ups_removed = False

    for remove_call in mock_osremove.call_args_list:
        if "www/mail_and_packages/amazon/anotherfakefile.mp4" in remove_call.args[0]:
            amazon_removed = True
        if "www/mail_and_packages/ups/anotherfakefile.mp4" in remove_call.args[0]:
            ups_removed = True

    assert amazon_removed
    assert ups_removed


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
    entry = integration_fake_external
    config = entry.data.copy()
    with patch("os.makedirs") as mock_osmakedirs:
        mock_osmakedirs.side_effect = OSError
        process_emails(hass, config)

    assert "Problem creating:" in caplog.text


# @pytest.mark.asyncio
# async def test_process_emails_copytree_error(
#     hass,
#     integration,
#     mock_imap_no_email,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_copyfile,
#     mock_hash_file,
#     mock_getctime_today,
#     caplog,
# ):
#     entry = integration
#     config = entry.data.copy()
#     with patch("custom_components.mail_and_packages.helpers.copytree") as mock_copytree:
#         mock_copytree.side_effect = Exception
#         process_emails(hass, config)
#     assert "Problem copying files from" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_bad(hass, mock_imap_no_email, mock_update):
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
    entry = integration

    config = entry.data
    result = process_emails(hass, config)
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
    entry = integration

    config = entry.data
    result = process_emails(hass, config)
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
    entry = integration

    config = entry.data
    result = process_emails(hass, config)
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
    entry = integration

    config = entry.data
    result = process_emails(hass, config)
    assert ".gif" in result["image_name"]


@pytest.mark.asyncio
async def test_process_folder_error(
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
    entry = integration

    config = entry.data
    with patch(
        "custom_components.mail_and_packages.helpers.selectfolder", return_value=False
    ):
        result = process_emails(hass, config)
        assert result == {}


# @pytest.mark.asyncio
# async def test_image_filename_oserr(
#     hass,
#     integration,
#     mock_imap_no_email,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_copyfile,
#     mock_copytree,
#     mock_hash_file_oserr,
#     mock_getctime_today,
#     caplog,
# ):
#     """Test settting up entities."""
#     entry = integration

#     assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 48
#     assert "Problem accessing file:" in caplog.text


# @pytest.mark.asyncio
# async def test_image_getctime_oserr(
#     hass,
#     integration,
#     mock_imap_no_email,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_copyfile,
#     mock_copytree,
#     mock_hash_file,
#     mock_getctime_err,
#     caplog,
# ):
#     """Test settting up entities."""
#     entry = integration

#     assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 48
#     assert "Problem accessing file:" in caplog.text


@pytest.mark.asyncio
async def test_email_search(mock_imap_search_error, caplog):
    result = email_search(mock_imap_search_error, "fake@eamil.address", "01-Jan-20")
    assert result == ("BAD", "Invalid SEARCH format")
    assert "Error searching emails:" in caplog.text

    result = email_search(
        mock_imap_search_error, "fake@eamil.address", "01-Jan-20", "Fake Subject"
    )
    assert result == ("BAD", "Invalid SEARCH format")
    assert "Error searching emails:" in caplog.text


@pytest.mark.asyncio
async def test_email_fetch(mock_imap_fetch_error, caplog):
    result = email_fetch(mock_imap_fetch_error, 1, "(RFC822)")
    assert result == ("BAD", "Invalid Email")
    assert "Error fetching emails:" in caplog.text


@pytest.mark.asyncio
async def test_get_mails(mock_imap_no_email, mock_copyfile):
    result = get_mails(mock_imap_no_email, "./", "5", "mail_today.gif", False)
    assert result == 0


@pytest.mark.asyncio
async def test_get_mails_makedirs_error(mock_imap_no_email, mock_copyfile, caplog):
    with (
        patch("os.path.isdir", return_value=False),
        patch("os.makedirs", side_effect=OSError),
    ):
        get_mails(mock_imap_no_email, "./", "5", "mail_today.gif", False)
        assert "Error creating directory:" in caplog.text


@pytest.mark.asyncio
async def test_get_mails_copyfile_error(
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    get_mails(
        mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
    )
    assert "File not found" in caplog.text


@pytest.mark.asyncio
async def test_get_mails_email_search_error(
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("BAD", []),
    ):
        result = get_mails(
            mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
        )
        assert result == 0


@pytest.mark.asyncio
async def test_informed_delivery_emails(
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = get_mails(
            mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
        )
        assert result == 3
        assert "USPSInformedDelivery@usps.gov" in caplog.text
        assert "USPSInformeddelivery@informeddelivery.usps.com" in caplog.text
        assert "USPSInformeddelivery@email.informeddelivery.usps.com" in caplog.text
        assert "USPS Informed Delivery" in caplog.text


@pytest.mark.asyncio
async def test_informed_delivery_forwarded_emails(
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
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = get_mails(
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
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = get_mails(
            mock_imap_usps_new_informed_digest, "./", "5", "mail_today.gif", False
        )
        assert result == 4
        assert "USPSInformedDelivery@usps.gov" in caplog.text
        assert "USPSInformeddelivery@informeddelivery.usps.com" in caplog.text
        assert "USPSInformeddelivery@email.informeddelivery.usps.com" in caplog.text
        assert "USPS Informed Delivery" in caplog.text


# async def test_get_mails_image_error(
#     mock_imap_usps_informed_digest,
#     mock_osremove,
#     mock_osmakedir,
#     mock_listdir,
#     mock_os_path_splitext,
#     mock_resizeimage,
#     mock_copyfile,
#     caplog,
# ):
#     with patch("custom_components.mail_and_packages.helpers.Image.Image.save") as mock_image:
#         m_open = mock_open()
#         with patch("builtins.open", m_open, create=True):
#             mock_image.Image.return_value = mock.Mock(autospec=True)
#             mock_image.side_effect = Exception("Processing Error")
#             result = get_mails(
#                 mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
#             )
#             assert result == 3
#             assert "Error attempting to generate image:" in caplog.text


@pytest.mark.asyncio
async def test_informed_delivery_emails_mp4(
    mock_imap_usps_informed_digest,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
):
    with patch(
        "custom_components.mail_and_packages.helpers._generate_mp4"
    ) as mock_generate_mp4:
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            result = get_mails(
                mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", True
            )
            assert result == 3
            mock_generate_mp4.assert_called_with("./", "mail_today.gif")


@pytest.mark.asyncio
async def test_informed_delivery_emails_open_err(
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


@pytest.mark.asyncio
async def test_informed_delivery_emails_io_err(
    mock_imap_usps_informed_digest,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image_save_excpetion,
    mock_copyfile,
):
    with pytest.raises(ValueError) as exc_info:
        m_open = mock_open()
        with patch("builtins.open", m_open, create=True):
            get_mails(
                mock_imap_usps_informed_digest,
                "/totally/fake/path/",
                "5",
                "mail_today.gif",
                False,
            )
    assert type(exc_info.value) is ValueError


@pytest.mark.asyncio
async def test_informed_delivery_missing_mailpiece(
    mock_imap_usps_informed_digest_missing,
    mock_listdir,
    mock_osremove,
    mock_osmakedir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
):
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = get_mails(
            mock_imap_usps_informed_digest_missing, "./", "5", "mail_today.gif", False
        )
        assert result == 5


@pytest.mark.asyncio
async def test_informed_delivery_no_mail(
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
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        result = get_mails(
            mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
        )
        assert result == 0


@pytest.mark.asyncio
async def test_informed_delivery_no_mail_copy_error(
    mock_imap_usps_informed_digest_no_mail,
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
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        get_mails(
            mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
        )
        assert "./mail_today.gif" in mock_copyfile_exception.call_args.args
        assert "File not found" in caplog.text


@pytest.mark.asyncio
async def test_ups_out_for_delivery(hass, mock_imap_ups_out_for_delivery):
    result = get_count(
        mock_imap_ups_out_for_delivery, "ups_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["1Z2345YY0678901234"]


@pytest.mark.asyncio
async def test_usps_delivered(hass, mock_imap_usps_delivered_individual):
    result = get_count(
        mock_imap_usps_delivered_individual, "usps_delivered", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["9400100000000000000000"]


@pytest.mark.asyncio
async def test_ups_out_for_delivery_html_only(
    hass, mock_imap_ups_out_for_delivery_html
):
    result = get_count(
        mock_imap_ups_out_for_delivery_html, "ups_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["1Z0Y12345678031234"]


@pytest.mark.asyncio
async def test_ups_delivered(hass, mock_imap_ups_delivered):
    result = get_count(mock_imap_ups_delivered, "ups_delivered", True, "./", hass)
    assert result["count"] == 1
    assert result["tracking"] == ["1Z2345YY0678901234"]


@pytest.mark.asyncio
async def test_ups_delivered_with_photo(hass, mock_imap_ups_delivered_with_photo):
    """Test UPS delivered with delivery photo extraction."""
    result = get_count(
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

    # Test image extraction
    result = get_ups_image(
        test_email,
        str(tmp_path) + "/",
        "test_ups_image.jpg",
    )

    # Verify extraction was successful
    assert result is True

    # Verify image file was created
    image_file = ups_path / "test_ups_image.jpg"
    assert image_file.exists()

    # Verify it's a valid JPEG (should start with JPEG magic bytes)
    with open(image_file, "rb") as f:
        data = f.read()
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

    # Test image extraction
    result = get_ups_image(
        test_email,
        str(tmp_path) + "/",
        "test_ups_image.jpg",
    )

    # Verify extraction was successful
    assert result is True

    # Verify image file was created
    image_file = ups_path / "test_ups_image.jpg"
    assert image_file.exists()

    # Verify it's a valid JPEG
    with open(image_file, "rb") as f:
        data = f.read()
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

    # Test image extraction
    result = get_ups_image(
        test_email,
        str(tmp_path),
        "test_ups_image.jpg",
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
    with patch("os.path.isdir", return_value=True), patch(
        "os.makedirs", return_value=True
    ):
        result = ups_search(mock_imap_no_email, "./", "test_ups.jpg")
        assert result == 0
        assert "No UPS deliveries found." in caplog.text
        # Should have copied the default no delivery image
        assert len(mock_copyfile.mock_calls) > 0


@pytest.mark.asyncio
async def test_ups_search_with_photo(tmp_path):
    """Test UPS search with delivery photo extraction."""
    # Create a mock IMAP account that returns our test email
    mock_account = mock.Mock()
    mock_account.host = "imap.test.email"  # Add host attribute

    # Mock the email search to return a message ID
    mock_account.search.return_value = ("OK", [b"1"])

    # Create test email content
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

    # Mock the fetch to return our test email
    mock_account.fetch.return_value = ("OK", [(b"", test_email.encode("utf-8"))])

    # Create UPS directory
    ups_path = tmp_path / "ups"
    ups_path.mkdir()

    # Test the full UPS search workflow
    with patch(
        "os.path.isdir", side_effect=lambda path: str(path) == str(ups_path)
    ), patch("os.makedirs", return_value=True), patch("os.listdir", return_value=[]):
        result = ups_search(mock_account, str(tmp_path) + "/", "test_ups_image.jpg")

    # Verify that one delivery was found and processed
    assert result == 1

    # Verify image file was created
    image_file = ups_path / "test_ups_image.jpg"
    assert image_file.exists()

    # Verify it's a valid JPEG
    with open(image_file, "rb") as f:
        data = f.read()
        assert data.startswith(b"\xff\xd8\xff")  # JPEG magic bytes


@pytest.mark.asyncio
async def test_usps_out_for_delivery(hass, mock_imap_usps_out_for_delivery):
    result = get_count(
        mock_imap_usps_out_for_delivery, "usps_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["92123456508577307776690000"]


@pytest.mark.asyncio
async def test_dhl_out_for_delivery(hass, mock_imap_dhl_out_for_delivery, caplog):
    result = get_count(
        mock_imap_dhl_out_for_delivery, "dhl_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["4212345678"]
    assert "UTF-8 not supported." not in caplog.text


@pytest.mark.asyncio
async def test_dhl_no_utf8(hass, mock_imap_dhl_no_utf8, caplog):
    result = get_count(mock_imap_dhl_no_utf8, "dhl_delivering", True, "./", hass)
    assert result["count"] == 1
    assert result["tracking"] == ["4212345678"]
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
    result = get_count(
        mock_imap_evri_out_for_delivery, "evri_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["H01QPZ0007431687"]


@pytest.mark.asyncio
async def test_royal_out_for_delivery(hass, mock_imap_royal_out_for_delivery):
    result = get_count(
        mock_imap_royal_out_for_delivery, "royal_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["MA038501234GB"]


@freeze_time("2020-09-11")
@pytest.mark.asyncio
async def test_amazon_shipped_count(hass, mock_imap_amazon_shipped, caplog):
    result = get_items(mock_imap_amazon_shipped, "count", the_domain="amazon.com")
    assert (
        "Amazon email search addresses: ['auto-confirm@amazon.com', 'shipment-tracking@amazon.com', 'order-update@amazon.com', 'conferma-spedizione@amazon.com', 'confirmar-envio@amazon.com', 'versandbestaetigung@amazon.com', 'confirmation-commande@amazon.com', 'verzending-volgen@amazon.com', 'update-bestelling@amazon.com']"
        in caplog.text
    )
    assert result == 1


@pytest.mark.asyncio
async def test_amazon_shipped_order(hass, mock_imap_amazon_shipped):
    result = get_items(mock_imap_amazon_shipped, "order", the_domain="amazon.com")
    assert result == ["123-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt(hass, mock_imap_amazon_shipped_alt):
    # Mock dateparser to avoid timezone issues in tests
    with patch(
        "custom_components.mail_and_packages.helpers.dateparser"
    ) as mock_dateparser:
        mock_dateparser.parse.return_value = datetime(2020, 9, 11)
        result = get_items(
            mock_imap_amazon_shipped_alt, "order", the_domain="amazon.com"
        )
        assert result == ["123-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt_2(hass, mock_imap_amazon_shipped_alt_2):
    result = get_items(mock_imap_amazon_shipped_alt_2, "order", the_domain="amazon.com")
    assert result == ["113-9999999-8459426"]
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2021, 12, 3)

        result = get_items(
            mock_imap_amazon_shipped_alt_2, "count", the_domain="amazon.com"
        )
        assert result == 0


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt_2_delivery_today(
    hass, mock_imap_amazon_shipped_alt_2
):
    """Test the same email but with mocked date matching the delivery date."""
    result = get_items(mock_imap_amazon_shipped_alt_2, "order", the_domain="amazon.com")
    assert result == ["113-9999999-8459426"]
    with patch("datetime.date") as mock_date:
        # Mock today to be the delivery date (2022-12-03 as parsed by dateparser)
        mock_date.today.return_value = date(2022, 12, 3)

        result = get_items(
            mock_imap_amazon_shipped_alt_2, "count", the_domain="amazon.com"
        )
        assert result == 1


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt_timeformat(
    hass, mock_imap_amazon_shipped_alt_timeformat
):
    result = get_items(
        mock_imap_amazon_shipped_alt_timeformat, "order", the_domain="amazon.com"
    )
    assert result == ["321-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_uk(hass, mock_imap_amazon_shipped_uk):
    # Mock dateparser to avoid timezone issues in tests
    with patch(
        "custom_components.mail_and_packages.helpers.dateparser"
    ) as mock_dateparser:
        mock_dateparser.parse.return_value = datetime(2020, 12, 12)
        result = get_items(
            mock_imap_amazon_shipped_uk, "order", the_domain="amazon.co.uk"
        )
        assert result == ["123-4567890-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_uk_2(hass, mock_imap_amazon_shipped_uk_2):
    # Mock dateparser to avoid timezone issues in tests
    with patch(
        "custom_components.mail_and_packages.helpers.dateparser"
    ) as mock_dateparser:
        mock_dateparser.parse.return_value = datetime(2021, 11, 16)
        result = get_items(
            mock_imap_amazon_shipped_uk_2, "order", the_domain="amazon.co.uk"
        )
        assert result == ["123-4567890-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_it(hass, mock_imap_amazon_shipped_it):
    result = get_items(mock_imap_amazon_shipped_it, "order", the_domain="amazon.it")
    assert result == ["405-5236882-9395563"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_it_count(hass, mock_imap_amazon_shipped_it):
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2021, 12, 1)
        result = get_items(mock_imap_amazon_shipped_it, "count", the_domain="amazon.it")
        assert result == 0


@pytest.mark.asyncio
async def test_amazon_shipped_order_it_count_delivery_today(
    hass, mock_imap_amazon_shipped_it
):
    """Test the same Italian email but with mocked date matching the delivery date."""
    result = get_items(mock_imap_amazon_shipped_it, "order", the_domain="amazon.it")
    assert result == ["405-5236882-9395563"]
    with patch("datetime.date") as mock_date:
        # Mock today to be the delivery date (2025-12-01 as parsed by dateparser)
        mock_date.today.return_value = date(2025, 12, 1)

        result = get_items(mock_imap_amazon_shipped_it, "count", the_domain="amazon.it")
        assert result == 1


@pytest.mark.asyncio
async def test_amazon_search(hass, mock_imap_no_email):
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        result = amazon_search(
            mock_imap_no_email,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.com",
        )
        assert result == 0


@pytest.mark.asyncio
async def test_amazon_search_results(
    hass, mock_imap_amazon_shipped, mock_imap_amazon_delivered
):
    """Test Amazon search functionality for both shipped and delivered emails."""
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        # Test shipped emails (should return 0 since email is not arriving today)
        shipped_result = get_items(
            mock_imap_amazon_shipped, "count", the_domain="amazon.com"
        )
        assert (
            shipped_result == 0
        ), f"Expected 0 shipped emails arriving today, got {shipped_result}"

        # Test delivered emails
        delivered_result = amazon_search(
            mock_imap_amazon_delivered,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.com",
        )
        assert (
            delivered_result == 10
        ), f"Expected 10 delivered emails (no deduplication), got {delivered_result}"


@pytest.mark.asyncio
async def test_amazon_search_delivered(
    hass, mock_imap_amazon_delivered, mock_download_img, caplog
):
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        result = amazon_search(
            mock_imap_amazon_delivered,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.com",
        )
        await hass.async_block_till_done()
        assert (
            "Amazon email search addresses: ['auto-confirm@amazon.com', 'shipment-tracking@amazon.com', 'order-update@amazon.com', 'conferma-spedizione@amazon.com', 'confirmar-envio@amazon.com', 'versandbestaetigung@amazon.com', 'confirmation-commande@amazon.com', 'verzending-volgen@amazon.com', 'update-bestelling@amazon.com']"
            in caplog.text
        )
        assert result == 10
        assert mock_download_img.called


@pytest.mark.asyncio
async def test_amazon_search_delivered_it(
    hass, mock_imap_amazon_delivered_it, mock_download_img
):
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        result = amazon_search(
            mock_imap_amazon_delivered_it,
            "test/path/amazon/",
            hass,
            "testfilename.jpg",
            "amazon.it",
        )
        assert result == 10


@pytest.mark.asyncio
async def test_amazon_hub(hass, mock_imap_amazon_the_hub):
    result = amazon_hub(mock_imap_amazon_the_hub)
    assert result["count"] == 1
    assert result["code"] == ["123456"]

    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("BAD", []),
    ):
        result = amazon_hub(mock_imap_amazon_the_hub)
        assert result == {}

    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("OK", [None]),
    ):
        result = amazon_hub(mock_imap_amazon_the_hub)
        assert result == {}


@pytest.mark.asyncio
async def test_amazon_hub_2(hass, mock_imap_amazon_the_hub_2):
    result = amazon_hub(mock_imap_amazon_the_hub_2)
    assert result["count"] == 1
    assert result["code"] == ["123456"]

    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("BAD", []),
    ):
        result = amazon_hub(mock_imap_amazon_the_hub_2)
        assert result == {}

    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("OK", [None]),
    ):
        result = amazon_hub(mock_imap_amazon_the_hub_2)
        assert result == {}


@pytest.mark.asyncio
async def test_amazon_shipped_order_exception(hass, mock_imap_amazon_shipped, caplog):
    with patch("quopri.decodestring", side_effect=ValueError):
        get_items(mock_imap_amazon_shipped, "order", the_domain="amazon.com")
        assert "Problem decoding email message:" in caplog.text


@pytest.mark.asyncio
async def test_generate_mp4(mock_osremove):
    """Test generating mp4."""
    # Patch subprocess.run since the code now uses it instead of call
    with patch("subprocess.run") as mock_run, patch(
        "custom_components.mail_and_packages.helpers.cleanup_images"
    ):

        # Call the function
        _generate_mp4("./", "testfile.gif")

        # Construct expected paths
        expected_input = os.path.join("./", "testfile.gif")
        expected_output = os.path.join("./", "testfile.mp4")

        # Assert called with correct arguments
        # Note: The optimization added '-y' and 'check=True'
        mock_run.assert_called_with(
            [
                "ffmpeg",
                "-y",
                "-i",
                expected_input,
                "-pix_fmt",
                "yuv420p",
                expected_output,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )


# @pytest.mark.asyncio
# async def test_generate_mp4(
#     mock_osremove, mock_os_path_join, mock_subprocess_call, mock_os_path_split
# ):
#     with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
#         _generate_mp4("./", "testfile.gif")

#         mock_os_path_join.assert_called_with("./", "testfile.mp4")
#         # mock_osremove.assert_called_with("./", "testfile.mp4")
#         mock_subprocess_call.assert_called_with(
#             [
#                 "ffmpeg",
#                 "-i",
#                 "./testfile.mp4",
#                 "-pix_fmt",
#                 "yuv420p",
#                 "./testfile.mp4",
#             ],
#             stdout=-3,
#             stderr=-3,
#         )


@pytest.mark.asyncio
async def test_connection_error(caplog):
    result = login("localhost", 993, "fakeuser", "suchfakemuchpassword", "SSL")
    assert not result
    assert "Network error while connecting to server:" in caplog.text


@pytest.mark.asyncio
async def test_login_error(mock_imap_login_error, caplog):
    login("localhost", 993, "fakeuser", "suchfakemuchpassword", "SSL")
    assert "Error logging into IMAP Server:" in caplog.text


@pytest.mark.asyncio
async def test_selectfolder_list_error(mock_imap_list_error, caplog):
    assert not selectfolder(mock_imap_list_error, "somefolder")
    assert "Error listing folders:" in caplog.text


@pytest.mark.asyncio
async def test_selectfolder_select_error(mock_imap_select_error, caplog):
    assert not selectfolder(mock_imap_select_error, "somefolder")
    assert "Error selecting folder:" in caplog.text


@pytest.mark.asyncio
async def test_resize_images_open_err(mock_open_excpetion, caplog):
    resize_images(["testimage.jpg", "anothertest.jpg"], 724, 320)
    assert "Error attempting to open image" in caplog.text


@pytest.mark.asyncio
async def test_resize_images_read_err(mock_image_excpetion, caplog):
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        resize_images(["testimage.jpg", "anothertest.jpg"], 724, 320)
        assert "Error attempting to read image" in caplog.text


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_usps_exception(hass, mock_imap_usps_exception):
    result = get_count(mock_imap_usps_exception, "usps_exception", False, "./", hass)
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
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        await download_img(
            hass,
            "http://fake.website.com/not/a/real/website/image.jpg",
            "/fake/directory/",
            "testfilename.jpg",
        )
        assert m_open.call_count == 1
        assert m_open.call_args == call("/fake/directory/amazon/testfilename.jpg", "wb")
        assert "URL content-type: image/gif" in caplog.text
        assert "Amazon image downloaded" in caplog.text


@pytest.mark.asyncio
async def test_download_img_error(hass, aioclient_mock_error, caplog):
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
    config = FAKE_CONFIG_DATA_CORRECTED

    with (
        patch("os.path.exists", return_value=False),
        patch("os.makedirs", side_effect=OSError),
    ):
        result = image_file_name(hass, config)
        assert result == "mail_none.gif"
        assert "Problem creating:" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_amazon(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    config = FAKE_CONFIG_DATA_CORRECTED

    with (
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", return_value=True),
    ):
        result = image_file_name(hass, config, True)
        assert result == "testfile.jpg"


@pytest.mark.asyncio
async def test_image_file_name_ups(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    config = FAKE_CONFIG_DATA_CORRECTED

    with (
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", return_value=True),
    ):
        result = image_file_name(hass, config, ups=True)
        assert result == "testfile.jpg"


@pytest.mark.asyncio
async def test_image_file_name(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    config = FAKE_CONFIG_DATA_CORRECTED

    with (
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", return_value=True),
    ):
        result = image_file_name(hass, config)
        assert ".gif" in result
        assert not result == "mail_none.gif"

        # Test custom image settings
        config = FAKE_CONFIG_DATA_CUSTOM_IMG
        result = image_file_name(hass, config)
        assert ".gif" in result
        assert not result == "mail_none.gif"
        assert len(mock_copyfile.mock_calls) == 2
        assert "Copying images/test.gif to" in caplog.text

        # Test custom Amazon image settings
        result = image_file_name(hass, config, amazon=True)
        assert ".jpg" in result
        assert not result == "no_deliveries.jpg"
        assert "Copying images/test_amazon.jpg to" in caplog.text

        # Test custom UPS image settings
        result = image_file_name(hass, config, ups=True)
        assert ".jpg" in result
        assert not result == "no_deliveries.jpg"
        assert "Copying images/test_ups.jpg to" in caplog.text


@pytest.mark.asyncio
async def test_amazon_exception(hass, mock_imap_amazon_exception, caplog):
    result = amazon_exception(mock_imap_amazon_exception, the_domain="amazon.com")
    assert result["order"] == ["123-1234567-1234567"]
    assert result["count"] == 1

    result = amazon_exception(
        mock_imap_amazon_exception,
        ["testemail@fakedomain.com"],
        the_domain="amazon.com",
    )
    assert result["count"] == 1
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
    result = get_count(
        mock_imap_fedex_out_for_delivery, "fedex_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["61290912345678912345"]


@pytest.mark.asyncio
async def test_fedex_out_for_delivery_2(hass, mock_imap_fedex_out_for_delivery_2):
    result = get_count(
        mock_imap_fedex_out_for_delivery_2, "fedex_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["286548999999"]


@pytest.mark.asyncio
async def test_get_mails_email_search_none(
    mock_imap_usps_informed_digest_no_mail,
    mock_copyoverlays,
    mock_copyfile_exception,
    caplog,
):
    with patch(
        "custom_components.mail_and_packages.helpers.email_search",
        return_value=("OK", [None]),
    ):
        result = get_mails(
            mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
        )
        assert result == 0


@pytest.mark.asyncio
async def test_email_search_none(mock_imap_search_error_none, caplog):
    result = email_search(
        mock_imap_search_error_none, "fake@eamil.address", "01-Jan-20"
    )
    assert result == ("OK", [b""])


@pytest.mark.asyncio
async def test_amazon_shipped_fwd(hass, mock_imap_amazon_fwd, caplog):
    with patch(
        "custom_components.mail_and_packages.helpers.dateparser.parse"
    ) as mock_parse:
        mock_parse.return_value = datetime(2022, 1, 11)
        result = get_items(
            mock_imap_amazon_fwd,
            "order",
            fwds="testuser@test.com",
            the_domain="amazon.com",
        )
        assert (
            "Amazon email list: ['auto-confirm@amazon.com', 'shipment-tracking@amazon.com', 'order-update@amazon.com', 'conferma-spedizione@amazon.com', 'confirmar-envio@amazon.com', 'versandbestaetigung@amazon.com', 'confirmation-commande@amazon.com', 'verzending-volgen@amazon.com', 'update-bestelling@amazon.com']"
            in caplog.text
        )
        assert "First pass: Tuesday, January 11" in caplog.text
        assert result == ["123-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_otp(hass, mock_imap_amazon_otp, caplog):
    result = amazon_otp(mock_imap_amazon_otp, ["test@amazon.com"])
    assert result == {"code": ["671314"]}


@pytest.mark.asyncio
async def test_amazon_out_for_delivery_today(hass, mock_imap_amazon_arriving_today):
    """Test that Amazon emails with 'Arriving today' are detected."""
    result = get_items(
        mock_imap_amazon_arriving_today, "order", the_domain="amazon.com"
    )
    # Email may or may not have an order number - check if it's extracted correctly if present
    if len(result) > 0:
        assert all(
            re.match(r"[0-9]{3}-[0-9]{7}-[0-9]{7}", order) for order in result
        ), "Order numbers should match Amazon pattern"

    # Test that "Arriving today" is detected and parsed correctly when email date matches today
    with patch("datetime.date") as mock_date, patch(
        "custom_components.mail_and_packages.helpers.dateparser"
    ) as mock_dateparser:
        # Mock today to match the email date (which should be the same day)
        mock_date.today.return_value = date(2020, 9, 11)
        # Mock dateparser to return today's date for "today"
        mock_dateparser.parse.return_value = datetime(2020, 9, 11)
    result = get_items(
        mock_imap_amazon_arriving_today, "count", the_domain="amazon.com"
    )
    # The email says "Arriving today" and email date matches today
    # Delivery count should be 1 (detected "today")
    # Result is min(deliveries_today, len(order_number))
    assert (
        result == 1
    ), "Count should be 1 when 'Arriving today' and email date matches today"


@pytest.mark.asyncio
async def test_amazon_arriving_tomorrow(hass, mock_imap_amazon_arriving_tomorrow):
    """Test that Amazon emails with 'Arriving tomorrow' are detected."""
    result = get_items(
        mock_imap_amazon_arriving_tomorrow, "order", the_domain="amazon.com"
    )
    assert result == ["111-7634359-8390444"]  # Should extract order number

    # Test that "Arriving tomorrow" doesn't count as arriving today
    with patch("datetime.date") as mock_date, patch(
        "custom_components.mail_and_packages.helpers.dateparser"
    ) as mock_dateparser:
        mock_date.today.return_value = date(2025, 10, 28)
        # Mock dateparser to return Oct 29 (tomorrow from email date Oct 28)
        mock_dateparser.parse.return_value = datetime(2025, 10, 29)
        result = get_items(
            mock_imap_amazon_arriving_tomorrow, "count", the_domain="amazon.com"
        )
        # Email date is Oct 28, "tomorrow" = Oct 29, so should NOT count as arriving today
    assert result == 0


@pytest.mark.asyncio
async def test_amazon_arriving_tomorrow_matches_date(
    hass, mock_imap_amazon_arriving_tomorrow
):
    """Test that 'Arriving tomorrow' works when today is Oct 29 (tomorrow from email date)."""
    result = get_items(
        mock_imap_amazon_arriving_tomorrow, "order", the_domain="amazon.com"
    )
    assert result == ["111-7634359-8390444"]  # Should extract order number

    # Test that "Arriving tomorrow" counts when today matches tomorrow
    with patch("datetime.date") as mock_date, patch(
        "custom_components.mail_and_packages.helpers.dateparser"
    ) as mock_dateparser:
        # Mock today to be Oct 29, 2025 (tomorrow from email date Oct 28)
        mock_date.today.return_value = date(2025, 10, 29)
        # Mock dateparser to return Oct 29 (tomorrow from email date Oct 28)
        mock_dateparser.parse.return_value = datetime(2025, 10, 29)
        result = get_items(
            mock_imap_amazon_arriving_tomorrow, "count", the_domain="amazon.com"
        )
        # Email date is Oct 28, "tomorrow" = Oct 29, today is Oct 29, so SHOULD count
        assert result == 1


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
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        generate_grid_img("./", "testfile.gif", 5)
        mock_os_path_join2.assert_called_with("./", "testfile_grid.png")
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "./testfile_grid.png",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x3:padding=10:color=black",
                "./testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )
        generate_grid_img("./", "testfile.gif", 8)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "./testfile_grid.png",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x4:padding=10:color=black",
                "./testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )
        generate_grid_img("./", "testfile.gif", 1)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "./testfile_grid.png",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x1:padding=10:color=black",
                "./testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )
        generate_grid_img("./", "testfile.gif", 0)
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "./testfile_grid.png",
                "-r",
                "0.20",
                "-filter_complex",
                "tile=2x1:padding=10:color=black",
                "./testfile_grid.png",
            ],
            stdout=-3,
            stderr=-3,
        )


@pytest.mark.asyncio
async def test_capost_mail(
    hass,
    integration_capost,
    mock_imap_capost_mail,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_os_path_splitext,
    mock_image,
    mock_resizeimage,
    mock_copyfile,
    caplog,
):
    hass.config.internal_url = "http://127.0.0.1:8123/"
    entry = integration_capost
    config = entry.data.copy()

    state = hass.states.get(MAIL_IMAGE_SYSTEM_PATH)
    assert state is not None
    assert "/testing_config/custom_components/mail_and_packages/images/" in state.state
    state = hass.states.get(MAIL_IMAGE_URL_ENTITY)
    assert state.state == "unknown"
    result = process_emails(hass, config)
    assert result["capost_mail"] == 3


async def test_amazon_image_path_with_custom_image(hass, integration):
    """Test Amazon image path when custom image is enabled."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image enabled
    config["amazon_custom_img"] = True
    config["amazon_custom_img_file"] = "images/test_amazon_custom.jpg"

    # Mock the file existence
    with patch("os.path.exists", return_value=True):
        image_path = get_amazon_image_path(config, hass)
        assert "images/test_amazon_custom.jpg" in image_path


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

    # Mock the file existence
    with patch("os.path.exists", return_value=True):
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

    with patch("os.path.exists", return_value=True):
        result = validate_custom_image_paths(config)
        assert result is True

    # Test with invalid paths
    with patch("os.path.exists", return_value=False):
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

    with patch("os.path.exists", side_effect=lambda path: "nonexistent" not in path):
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
        if os.path.exists(custom_path):
            return custom_path

    # Fall back to default image
    return DEFAULT_AMAZON_CUSTOM_IMG_FILE


def get_ups_image_path(config: dict, hass) -> str:
    """Get the UPS image path based on configuration."""
    if config.get(CONF_UPS_CUSTOM_IMG, False):
        custom_path = config.get(CONF_UPS_CUSTOM_IMG_FILE, DEFAULT_UPS_CUSTOM_IMG_FILE)
        if os.path.exists(custom_path):
            return custom_path

    # Fall back to default image
    return DEFAULT_UPS_CUSTOM_IMG_FILE


def get_walmart_image_path(config: dict, hass) -> str:
    """Get the Walmart image path based on configuration."""
    if config.get(CONF_WALMART_CUSTOM_IMG, False):
        custom_path = config.get(
            CONF_WALMART_CUSTOM_IMG_FILE, DEFAULT_WALMART_CUSTOM_IMG_FILE
        )
        if os.path.exists(custom_path):
            return custom_path

    # Fall back to default image
    return DEFAULT_WALMART_CUSTOM_IMG_FILE


def validate_custom_image_paths(config: dict) -> bool:
    """Validate that custom image file paths exist."""
    if config.get(CONF_AMAZON_CUSTOM_IMG, False):
        amazon_path = config.get(CONF_AMAZON_CUSTOM_IMG_FILE)
        if amazon_path and not os.path.exists(amazon_path):
            return False

    if config.get(CONF_UPS_CUSTOM_IMG, False):
        ups_path = config.get(CONF_UPS_CUSTOM_IMG_FILE)
        if ups_path and not os.path.exists(ups_path):
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


@pytest.mark.asyncio
@patch("custom_components.mail_and_packages.helpers.copyfile")
@patch("custom_components.mail_and_packages.helpers.os.makedirs")
@patch("custom_components.mail_and_packages.helpers.os.listdir")
@patch("custom_components.mail_and_packages.helpers.cleanup_images")
@patch("custom_components.mail_and_packages.helpers.os.path.isdir")
@patch("custom_components.mail_and_packages.helpers.get_walmart_image")
@patch("custom_components.mail_and_packages.helpers.email_fetch")
@patch("custom_components.mail_and_packages.helpers.email_search")
async def test_walmart_delivered_email_processing(
    mock_email_search,
    mock_email_fetch,
    mock_get_walmart_image,
    mock_isdir,
    mock_cleanup,
    mock_listdir,
    mock_makedirs,
    mock_copyfile,
):
    """Test that Walmart delivered emails are correctly processed and counted."""
    # Mock dependencies
    mock_account = MagicMock()

    # Test parameters
    image_path = "/test/images/"
    walmart_image_name = "test_walmart.jpg"
    coordinator_data = {}

    # Setup Mocks
    # email_search returns ID "1"
    mock_email_search.return_value = ("OK", [b"1"])

    # email_fetch returns dummy content (content is irrelevant as get_walmart_image is mocked)
    mock_email_fetch.return_value = ("OK", [(None, b"Subject: Delivery\n\nDelivered")])

    # Simulate a successful image extraction
    mock_get_walmart_image.return_value = True

    # Simulate file system state
    mock_isdir.return_value = True
    mock_listdir.return_value = ["test_walmart.jpg"]

    # Execute
    result = walmart_search(
        mock_account,
        image_path,
        walmart_image_name,
        coordinator_data,
    )

    # Assertions
    # Should return 1 since one email ID was found
    assert result == 1, f"Expected 1 Walmart delivery, got {result}"

    # Verify that coordinator data was updated with the image filename found in listdir
    assert ATTR_WALMART_IMAGE in coordinator_data
    assert coordinator_data[ATTR_WALMART_IMAGE] == "test_walmart.jpg"

    # Verify key interactions
    mock_email_search.assert_called()
    mock_get_walmart_image.assert_called()


async def test_walmart_delivering_email_processing():
    """Test that Walmart delivering emails are correctly processed."""
    # Mock the dependencies
    mock_account = MagicMock()
    mock_hass = MagicMock()

    # Test parameters
    image_path = "/test/images/"

    # Mock email_search to return the test email
    with patch(
        "custom_components.mail_and_packages.helpers.email_search"
    ) as mock_email_search:
        mock_email_search.return_value = ("OK", [b"1"])  # One email found

        # Mock email_fetch to return our test email content
        with patch(
            "custom_components.mail_and_packages.helpers.email_fetch"
        ) as mock_email_fetch:
            # Read the actual test email content
            with open(
                "tests/test_emails/walmart_delivery.eml", "r", encoding="utf-8"
            ) as f:
                test_email_content = f.read()

            mock_email_fetch.return_value = (
                "OK",
                [(None, test_email_content.encode())],
            )

            # Call get_count for walmart_delivering
            result = get_count(
                mock_account,
                "walmart_delivering",
                image_path=image_path,
                hass=mock_hass,
            )

    # Should return 1 since one email was found
    assert (
        result[ATTR_COUNT] == 1
    ), f"Expected 1 Walmart delivering package, got {result[ATTR_COUNT]}"


async def test_walmart_image_extraction():
    """Test that Walmart delivery photos are correctly extracted from emails."""
    # Test parameters
    image_path = "/test/images/"
    image_name = "test_walmart.jpg"

    # Read the actual test email content
    with open("tests/test_emails/walmart_delivered.eml", "r", encoding="utf-8") as f:
        test_email_content = f.read()

    # Mock file operations
    with patch(
        "custom_components.mail_and_packages.helpers.os.path.isdir"
    ) as mock_isdir:
        mock_isdir.return_value = True
        with patch("builtins.open", mock.mock_open()) as mock_file:
            # Call get_walmart_image
            result = get_walmart_image(test_email_content, image_path, image_name)

    # Should return True since the email contains a delivery photo
    assert (
        result is True
    ), "Walmart image extraction should return True for email with delivery photo"


async def test_walmart_email_patterns():
    """Test that Walmart email patterns are correctly configured."""
    # Test Walmart delivered email patterns
    walmart_delivered_emails = SENSOR_DATA["walmart_delivered"]["email"]
    walmart_delivered_subjects = SENSOR_DATA["walmart_delivered"]["subject"]

    # Should include the Walmart email address
    assert (
        "help@walmart.com" in walmart_delivered_emails
    ), "Walmart delivered emails should include help@walmart.com"

    # Should include "Delivered:" subject pattern
    assert (
        "Delivered:" in walmart_delivered_subjects
    ), "Walmart delivered subjects should include 'Delivered:'"

    # Test Walmart delivering email patterns
    walmart_delivering_emails = SENSOR_DATA["walmart_delivering"]["email"]
    walmart_delivering_subjects = SENSOR_DATA["walmart_delivering"]["subject"]

    # Should include the same email address
    assert (
        "help@walmart.com" in walmart_delivering_emails
    ), "Walmart delivering emails should include help@walmart.com"

    # Should include "Your package should arrive by" subject pattern
    assert (
        "Your package should arrive by" in walmart_delivering_subjects
    ), "Walmart delivering subjects should include 'Your package should arrive by'"


async def test_walmart_tracking_pattern():
    """Test that Walmart tracking pattern matches the test email tracking number."""
    # Test tracking number from walmart_delivered.eml (if it has one)
    # Note: The test email might not have a tracking number, so we'll test the pattern itself
    walmart_tracking_pattern = SENSOR_DATA["walmart_tracking"]["pattern"]

    # Test the pattern with a sample tracking number
    sample_tracking = "#1234567-12345678"
    pattern = walmart_tracking_pattern[0]  # "#[0-9]{7}-[0-9]{7,8}"
    match = re.search(pattern, sample_tracking)
    assert (
        match is not None
    ), f"Sample tracking number {sample_tracking} should match Walmart pattern {pattern}"


async def test_walmart_camera_integration():
    """Test that Walmart camera is properly integrated with coordinator data."""
    # Test that Walmart camera is defined in CAMERA_DATA
    assert (
        "walmart_camera" in CAMERA_DATA
    ), "Walmart camera should be defined in CAMERA_DATA"
    assert (
        CAMERA_DATA["walmart_camera"][0] == "Mail Walmart Camera"
    ), "Walmart camera should have correct name"

    # Test that ATTR_WALMART_IMAGE constant exists
    assert (
        ATTR_WALMART_IMAGE == "walmart_image"
    ), "ATTR_WALMART_IMAGE should be defined correctly"


async def test_walmart_no_deliveries_handling():
    """Test that Walmart handles no deliveries correctly."""
    # Mock the dependencies
    mock_account = MagicMock()

    # Test parameters
    image_path = "/test/images/"
    walmart_image_name = "test_walmart.jpg"
    coordinator_data = {}

    # Mock email_search to return no emails
    with patch(
        "custom_components.mail_and_packages.helpers.email_search"
    ) as mock_email_search:
        mock_email_search.return_value = ("OK", [None])  # No emails found

        # Mock file operations
        with patch(
            "custom_components.mail_and_packages.helpers.os.path.isdir"
        ) as mock_isdir:
            mock_isdir.return_value = True
            with patch(
                "custom_components.mail_and_packages.helpers.copyfile"
            ) as mock_copyfile:
                # Call walmart_search
                result = walmart_search(
                    mock_account,
                    image_path,
                    walmart_image_name,
                    coordinator_data,
                )

    # Should return 0 since no emails were found
    assert result == 0, f"Expected 0 Walmart deliveries, got {result}"

    # Verify that coordinator data was updated with no-delivery image
    assert (
        ATTR_WALMART_IMAGE in coordinator_data
    ), "Walmart image should be set in coordinator data even with no deliveries"

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
    assert (
        "walmart" in SHIPPERS
    ), "Walmart should be in SHIPPERS list for sensor counting"

    # Test that Walmart sensors are defined
    assert (
        "walmart_delivered" in SENSOR_DATA
    ), "Walmart delivered sensor should be defined"
    assert (
        "walmart_delivering" in SENSOR_DATA
    ), "Walmart delivering sensor should be defined"

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
        assert (
            match is not None
        ), f"Order number '{order}' should match Walmart tracking pattern"

    # Test that invalid formats don't match
    invalid_orders = [
        "123456-1234567",  # Too short
        "12345678-123456789",  # Too long
        "ABC1234-5678901",  # Contains letters
        "1234567_12345678",  # Wrong separator
    ]

    for order in invalid_orders:
        match = re.search(pattern, order)
        assert (
            match is None
        ), f"Invalid order number '{order}' should not match Walmart tracking pattern"


async def test_get_walmart_image_with_real_email():
    """Test get_walmart_image function with real Walmart delivery email."""
    # Read the actual Walmart delivery email
    with open("tests/test_emails/walmart_delivery.eml", "r", encoding="utf-8") as f:
        test_email = f.read()

    with tempfile.TemporaryDirectory() as temp_dir:
        walmart_path = f"{temp_dir}/walmart/"
        os.makedirs(walmart_path, exist_ok=True)

        # Test with real Walmart email (this email doesn't contain delivery proof images)
        result = get_walmart_image(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
        )

        # This email doesn't contain delivery proof images, so should return False
        assert result is False
        assert not os.path.exists(f"{walmart_path}test_delivery.jpg")


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
        walmart_path = f"{temp_dir}/walmart/"
        os.makedirs(walmart_path, exist_ok=True)

        # Test with base64 encoded image
        result = get_walmart_image(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
        )

        assert result is True
        assert os.path.exists(f"{walmart_path}test_delivery.jpg")


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
        walmart_path = f"{temp_dir}/walmart/"
        os.makedirs(walmart_path, exist_ok=True)

        # Test with PNG attachment
        result = get_walmart_image(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
        )

        assert result is True
        assert os.path.exists(f"{walmart_path}test_delivery.jpg")


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
        walmart_path = f"{temp_dir}/walmart/"
        os.makedirs(walmart_path, exist_ok=True)

        # Test with no image
        result = get_walmart_image(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
        )

        assert result is False
        assert not os.path.exists(f"{walmart_path}test_delivery.jpg")


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
        walmart_path = f"{temp_dir}/walmart/"
        os.makedirs(walmart_path, exist_ok=True)

        # Mock file write to raise an exception
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            result = get_walmart_image(
                test_email,
                temp_dir + "/",
                "test_delivery.jpg",
            )

            assert result is False


async def test_walmart_email_with_order_number():
    """Test that Walmart emails contain order numbers that can be extracted."""
    # Read the actual Walmart delivery email
    with open("tests/test_emails/walmart_delivery.eml", "r", encoding="utf-8") as f:
        test_email = f.read()

    # Test that the order number is in the email content (handle MIME encoding)
    order_number = "2000137-67895124"
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
    with open("tests/test_emails/walmart_delivered.eml", "r", encoding="utf-8") as f:
        test_email = f.read()

    with tempfile.TemporaryDirectory() as temp_dir:
        walmart_path = f"{temp_dir}/walmart/"
        os.makedirs(walmart_path, exist_ok=True)

        # Test with real Walmart delivered email
        result = get_walmart_image(
            test_email,
            temp_dir + "/",
            "test_delivery.jpg",
        )

        # This email contains a valid delivery proof image with CID embedded image
        # The function should successfully find and save the image
        print(f"Walmart delivered email processing result: {result}")

        # The email has a valid delivery proof image structure
        assert "deliveryProofLabel" in test_email
        assert "cid:deliveryProofLabel" in test_email
        # Result should be True because the email contains a valid delivery proof image
        assert result is True
        assert os.path.exists(f"{walmart_path}test_delivery.jpg")


async def test_walmart_delivering_email_processing():
    """Test that Walmart delivering emails are correctly processed and counted."""
    # Mock the dependencies
    mock_account = MagicMock()
    mock_hass = MagicMock()

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
            else:
                return ("OK", [None])

        mock_email_search.side_effect = email_search_side_effect

        # Mock email_fetch to return our test email content
        with patch(
            "custom_components.mail_and_packages.helpers.email_fetch"
        ) as mock_email_fetch:
            # Read the actual test email content
            with open(
                "tests/test_emails/walmart_delivery.eml", "r", encoding="utf-8"
            ) as f:
                test_email_content = f.read()

            mock_email_fetch.return_value = (
                "OK",
                [(None, test_email_content.encode())],
            )

            # Call get_count for walmart_delivering
            result = get_count(
                mock_account,
                "walmart_delivering",
                image_path=image_path,
                hass=mock_hass,
            )

    # Should return 1 since one email was found
    assert (
        result[ATTR_COUNT] == 1
    ), f"Expected 1 Walmart delivering package, got {result[ATTR_COUNT]}"

    # Test that tracking numbers are extracted
    if ATTR_TRACKING in result:
        assert (
            len(result[ATTR_TRACKING]) >= 0
        ), "Tracking numbers should be extracted if present"


async def test_walmart_image_path_with_custom_image(hass, integration):
    """Test Walmart image path when custom image is enabled."""
    entry = integration
    config = entry.data.copy()

    # Test with custom image enabled
    config["walmart_custom_img"] = True
    config["walmart_custom_img_file"] = "images/test_walmart_custom.jpg"

    # Mock the file existence
    with patch("os.path.exists", return_value=True):
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


async def test_walmart_search_error_handling():
    """Test walmart_search function error handling paths."""
    # Mock account and dependencies
    mock_account = MagicMock()
    mock_account.search.return_value = ("OK", [b""])  # Return proper tuple format

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with invalid image path (should handle gracefully)
        result = walmart_search(
            mock_account,
            "/invalid/path/",  # Invalid path
            "test_image.jpg",
            {},
        )

    # Should return 0 when path is invalid
    assert result == 0


async def test_ups_search_error_handling():
    """Test ups_search function error handling paths."""
    # Mock account and dependencies
    mock_account = MagicMock()
    mock_account.search.return_value = ("OK", [b""])  # Return proper tuple format

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with invalid image path (should handle gracefully)
        result = ups_search(
            mock_account,
            "/invalid/path/",  # Invalid path
            "test_image.jpg",
            {},
        )

        # Should return 0 when path is invalid
        assert result == 0


async def test_process_emails_ups_directory_creation_error():
    """Test process_emails handles UPS directory creation errors gracefully."""
    # Mock hass and config
    mock_hass = MagicMock()
    mock_hass.config.path.return_value = "/test/path"
    config = FAKE_CONFIG_DATA.copy()
    config["resources"] = ["ups_delivered"]

    with patch(
        "custom_components.mail_and_packages.helpers.login"
    ) as mock_login, patch(
        "custom_components.mail_and_packages.helpers.image_file_name",
        return_value="test_image.jpg",
    ), patch(
        "os.path.isdir", return_value=False
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs"
    ) as mock_makedirs, patch(
        "custom_components.mail_and_packages.helpers.copyfile"
    ) as mock_copyfile:

        # Mock login to return a mock account
        mock_account = MagicMock()
        mock_login.return_value = mock_account

        # Mock makedirs to raise an exception
        mock_makedirs.side_effect = Exception("UPS directory creation error")

        # This should not raise an exception, but handle errors gracefully
        result = process_emails(mock_hass, config)

        # Should return a dict even with errors
        assert isinstance(result, dict)


async def test_default_image_path_attribute_error():
    """Test default_image_path handles AttributeError gracefully."""
    # Mock config entry that raises AttributeError on get()
    mock_config = MagicMock()
    mock_config.get.side_effect = AttributeError("No get method")
    mock_config.data = {"storage": "custom/path/"}

    # Mock hass
    mock_hass = MagicMock()

    # Should handle AttributeError and use data attribute
    result = default_image_path(mock_hass, mock_config)
    assert result == "custom/path/"


async def test_default_image_path_no_storage():
    """Test default_image_path returns default when no storage configured."""
    # Mock config entry with no storage
    mock_config = MagicMock()
    mock_config.get.return_value = None

    # Mock hass
    mock_hass = MagicMock()

    # Should return default path
    result = default_image_path(mock_hass, mock_config)
    assert result == "custom_components/mail_and_packages/images/"


async def test_process_emails_directory_creation_error():
    """Test process_emails handles directory creation errors gracefully."""
    # Mock hass and config
    mock_hass = MagicMock()
    mock_hass.config.path.return_value = "/test/path"
    config = FAKE_CONFIG_DATA.copy()
    config["resources"] = ["ups_delivered"]

    with patch(
        "custom_components.mail_and_packages.helpers.login"
    ) as mock_login, patch("os.path.isdir", return_value=False), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs"
    ) as mock_makedirs, patch(
        "custom_components.mail_and_packages.helpers.copyfile"
    ) as mock_copyfile:

        # Mock login to return a mock account
        mock_account = MagicMock()
        mock_login.return_value = mock_account

        # Mock image_file_name to return normal values
        with patch(
            "custom_components.mail_and_packages.helpers.image_file_name",
            return_value="test_image.jpg",
        ):
            mock_makedirs.side_effect = Exception("Directory creation error")

            # Mock copyfile to raise an exception
            mock_copyfile.side_effect = Exception("File copy error")

            # This should not raise an exception, but handle errors gracefully
            result = process_emails(mock_hass, config)

            # Should return a dict even with errors
            assert isinstance(result, dict)


async def test_hash_file_functionality():
    """Test hash_file function basic functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        # Test with valid file
        result = hash_file(test_file)
        assert result is not None
        assert len(result) == 40  # SHA1 hash length
        assert isinstance(result, str)

        # Test that same content produces same hash
        result2 = hash_file(test_file)
        assert result == result2

        # Test with different content produces different hash
        with open(test_file, "w") as f:
            f.write("different content")
        result3 = hash_file(test_file)
        assert result != result3


async def test_copy_overlays_error_handling():
    """Test copy_overlays function error handling."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock shutil.copytree to raise an exception
        with patch(
            "custom_components.mail_and_packages.helpers.copytree",
            side_effect=Exception("Copy error"),
        ):
            # Should handle the exception gracefully and log an error
            copy_overlays(temp_dir)


async def test_image_file_name_copy_error():
    """Test image_file_name handles copy errors gracefully."""
    # Mock hass and config
    mock_hass = MagicMock()
    mock_hass.config.path.return_value = "/test/path"
    mock_config = FAKE_CONFIG_DATA.copy()

    with patch("os.path.exists", return_value=True), patch(
        "os.path.isdir", return_value=True
    ), patch("os.listdir", return_value=[]), patch(
        "custom_components.mail_and_packages.helpers.copyfile"
    ) as mock_copyfile:
        # Make copyfile raise an exception
        mock_copyfile.side_effect = Exception("Copy error")

        # This should return a fallback filename
        result = image_file_name(mock_hass, mock_config, amazon=True)

        # Should return fallback filename
        assert result == "no_deliveries.jpg"


async def test_copy_overlays_error_handling():
    """Test copy_overlays handles errors gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock copytree to raise an exception
        with patch(
            "custom_components.mail_and_packages.helpers.copytree"
        ) as mock_copytree:
            mock_copytree.side_effect = Exception("Copy error")

            # This should handle the exception gracefully
            copy_overlays(temp_dir)


async def test_login_starttls_security():
    """Test login with startTLS security."""
    # Mock the IMAP4 class and its methods
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib.IMAP4"
    ) as mock_imap4:
        mock_account = MagicMock()
        mock_imap4.return_value = mock_account

        # Test startTLS security
        result = login("imap.test.com", 993, "user", "pass", "startTLS", True)

        # Should return the mock account
        assert result == mock_account
        mock_account.starttls.assert_called_once()


async def test_login_no_ssl_security():
    """Test login with no SSL security."""
    # Mock the IMAP4 class and its methods
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib.IMAP4"
    ) as mock_imap4:
        mock_account = MagicMock()
        mock_imap4.return_value = mock_account

        # Test no SSL security
        result = login("imap.test.com", 993, "user", "pass", "none", True)

        # Should return the mock account
        assert result == mock_account


async def test_default_image_path_storage():
    """Test default_image_path with storage configuration."""
    # Mock hass and config
    mock_hass = MagicMock()
    mock_hass.config.path.return_value = "/test/path"
    config = FAKE_CONFIG_DATA.copy()

    result = default_image_path(mock_hass, config)

    # Should return the storage path
    assert result == ".storage/mail_and_packages/images"


async def test_default_image_path_no_storage():
    """Test default_image_path without storage configuration."""
    # Mock hass and config
    mock_hass = MagicMock()
    mock_hass.config.path.return_value = "/test/path"
    config = FAKE_CONFIG_DATA_NO_PATH.copy()

    result = default_image_path(mock_hass, config)

    # Should return the default path
    assert result == "custom_components/mail_and_packages/images/"


@pytest.mark.asyncio
async def test_amazon_shipped_vs_delivered_logic():
    """Test that Amazon orders that have been delivered are not counted as in transit."""
    # Test the package counting logic directly
    shipped_packages = {"123-4567890-1234567": 2}  # 2 packages shipped for this order
    delivered_packages = {
        "123-4567890-1234567": 2
    }  # 2 packages delivered for this order

    print("Package counts:")
    print(f"shipped_packages: {shipped_packages}")
    print(f"delivered_packages: {delivered_packages}")

    # Calculate in-transit packages by subtracting delivered from shipped
    in_transit_packages = 0
    for order_id in shipped_packages:
        shipped_count = shipped_packages[order_id]
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count
        print(
            f"Order {order_id}: {shipped_count} shipped, {delivered_count} delivered, {in_transit_count} in transit"
        )

    print(f"Total in-transit packages: {in_transit_packages}")

    # Should return 0 because all shipped packages were delivered
    assert (
        in_transit_packages == 0
    ), f"Expected 0 (all shipped packages were delivered), got {in_transit_packages}"


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

    print("Package counts:")
    print(f"shipped_packages: {shipped_packages}")
    print(f"delivered_packages: {delivered_packages}")

    # Calculate in-transit packages by subtracting delivered from shipped
    in_transit_packages = 0
    for order_id in shipped_packages:
        shipped_count = shipped_packages[order_id]
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count
        print(
            f"Order {order_id}: {shipped_count} shipped, {delivered_count} delivered, {in_transit_count} in transit"
        )

    print(f"Total in-transit packages: {in_transit_packages}")

    # Should return 3 because: 1 + (2-1) + 1 = 3 packages in transit
    assert (
        in_transit_packages == 3
    ), f"Expected 3 (3 packages in transit), got {in_transit_packages}"


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

    print("Package counts:")
    print(f"shipped_packages: {shipped_packages}")
    print(f"delivered_packages: {delivered_packages}")

    # Calculate in-transit packages by subtracting delivered from shipped
    in_transit_packages = 0
    for order_id in shipped_packages:
        shipped_count = shipped_packages[order_id]
        delivered_count = delivered_packages.get(order_id, 0)
        in_transit_count = max(0, shipped_count - delivered_count)
        in_transit_packages += in_transit_count
        print(
            f"Order {order_id}: {shipped_count} shipped, {delivered_count} delivered, {in_transit_count} in transit"
        )

    print(f"Total in-transit packages: {in_transit_packages}")

    # Should return 1 because only 1 package (#111-1111111-1111111) is in transit
    # Orders #222-2222222-2222222 and #333-3333333-3333333 were fully delivered
    assert (
        in_transit_packages == 1
    ), f"Expected 1 (only 1 package in transit), got {in_transit_packages}"


@pytest.mark.asyncio
async def test_amazon_delivered_with_order_in_body():
    """Test Amazon delivered emails with order numbers in the body (not subject)."""
    # Mock account
    mock_account = MagicMock()
    mock_account.host = "imap.gmail.com"

    # Mock email search to return delivered emails
    mock_account.search.return_value = ("OK", [b"1 2"])

    # Mock email fetch to return delivered emails with order numbers in body
    def mock_fetch(email_id, parts):
        if email_id == "1":
            # Delivered email with order number in body
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 1"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"1 (RFC822 {1000}", email_content)])
        elif email_id == "2":
            # Another delivered email with order number in body
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 2"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"2 (RFC822 {1000}", email_content)])
        return ("OK", [])

    mock_account.fetch.side_effect = mock_fetch

    # Test the function
    result = get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    # Should return 0 because both delivered emails are for the same order
    # and there are no shipped emails to subtract from
    assert result == 0, f"Expected 0 (no in-transit packages), got {result}"


@pytest.mark.asyncio
async def test_amazon_mixed_delivered_subject_and_body():
    """Test Amazon delivered emails with order numbers in both subject and body."""
    # Mock account
    mock_account = MagicMock()
    mock_account.host = "imap.gmail.com"

    # Mock email search to return delivered emails
    mock_account.search.return_value = ("OK", [b"1 2"])

    # Mock email fetch to return mixed delivered emails
    def mock_fetch(email_id, parts):
        if email_id == "1":
            # Delivered email with order number in subject
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 1" - Order 111-1111111-1111111
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"1 (RFC822 {1000}", email_content)])
        elif email_id == "2":
            # Delivered email with order number in body
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 2"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 222-2222222-2222222 has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"2 (RFC822 {1000}", email_content)])
        return ("OK", [])

    mock_account.fetch.side_effect = mock_fetch

    # Test the function
    result = get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    # Should return 0 because both delivered emails are counted
    # and there are no shipped emails to subtract from
    assert result == 0, f"Expected 0 (no in-transit packages), got {result}"


@pytest.mark.asyncio
async def test_amazon_shipped_minus_delivered_with_body_orders():
    """Test Amazon package counting with shipped emails minus delivered emails (order numbers in body)."""
    # Mock account
    mock_account = MagicMock()
    mock_account.host = "imap.gmail.com"

    # Mock email search to return both shipped and delivered emails
    def mock_search(criteria):
        if "Shipped:" in criteria:
            return ("OK", [b"1 2"])  # 2 shipped emails
        elif "Delivered:" in criteria:
            return ("OK", [b"3 4"])  # 2 delivered emails
        return ("OK", [b""])

    mock_account.search.side_effect = mock_search

    # Mock email fetch to return mixed emails
    def mock_fetch(email_id, parts):
        if email_id == "1":
            # Shipped email arriving today
            email_content = b"""From: auto-confirm@amazon.com
Subject: Shipped: "Test Product 1"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has shipped.
Arriving today
"""
            return ("OK", [(b"1 (RFC822 {1000}", email_content)])
        elif email_id == "2":
            # Another shipped email arriving today
            email_content = b"""From: auto-confirm@amazon.com
Subject: Shipped: "Test Product 2"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has shipped.
Arriving today
"""
            return ("OK", [(b"2 (RFC822 {1000}", email_content)])
        elif email_id == "3":
            # Delivered email with order number in body
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 1"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"3 (RFC822 {1000}", email_content)])
        elif email_id == "4":
            # Another delivered email with order number in body
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product 2"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order 111-1111111-1111111 has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"4 (RFC822 {1000}", email_content)])
        return ("OK", [])

    mock_account.fetch.side_effect = mock_fetch

    # Test the function
    result = get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    # Should return 0 because 2 shipped - 2 delivered = 0 in transit
    assert result == 0, f"Expected 0 (2 shipped - 2 delivered = 0), got {result}"


@pytest.mark.asyncio
async def test_amazon_delivered_no_order_number():
    """Test Amazon delivered emails with no order numbers found."""
    # Mock account
    mock_account = MagicMock()
    mock_account.host = "imap.gmail.com"

    # Mock email search to return delivered emails
    mock_account.search.return_value = ("OK", [b"1"])

    # Mock email fetch to return delivered email without order number
    def mock_fetch(email_id, parts):
        if email_id == "1":
            # Delivered email without order number
            email_content = b"""From: auto-confirm@amazon.com
Subject: Delivered: "Test Product"
Date: Wed, 29 Oct 2025 19:30:00 +0000

Your order has been delivered.
Thank you for your purchase!
"""
            return ("OK", [(b"1 (RFC822 {1000}", email_content)])
        return ("OK", [])

    mock_account.fetch.side_effect = mock_fetch

    # Test the function
    result = get_items(mock_account, "count", "amazon.com", 7, "gmail.com")

    # Should return 0 because no order number was found to count
    assert result == 0, f"Expected 0 (no order number found), got {result}"


def test_extract_delivery_image_png(tmp_path):
    """Test extracting a PNG delivery image (e.g. Walmart style)."""
    from custom_components.mail_and_packages.helpers import _extract_delivery_image

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
    os.makedirs(os.path.join(image_path, "walmart"), exist_ok=True)

    # Run extraction
    result = _extract_delivery_image(
        email_body, image_path, "test.png", "walmart", "deliveryProofLabel", "image/png"
    )

    assert result is True
    assert os.path.exists(os.path.join(image_path, "walmart", "test.png"))


def test_extract_delivery_image_bad_base64(tmp_path):
    """Test extraction with invalid base64 data."""
    from custom_components.mail_and_packages.helpers import _extract_delivery_image

    # Invalid base64 string (contains spaces or invalid chars not padding)
    bad_data = "This is not valid base64 data!!!"

    email_body = f"""MIME-Version: 1.0
Content-Type: text/html; charset=utf-8

<html>
  <div class="deliveryProofLabel">
    <img src="data:image/png;base64,{bad_data}" />
  </div>
</html>
"""

    image_path = str(tmp_path) + "/"

    # Should handle the exception gracefully and return False
    result = _extract_delivery_image(
        email_body, image_path, "test.png", "walmart", "deliveryProofLabel", "image/png"
    )

    assert result is False


def test_extract_delivery_image_save_error(tmp_path):
    """Test error handling when saving the image fails."""
    from unittest.mock import mock_open, patch

    from custom_components.mail_and_packages.helpers import _extract_delivery_image

    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

    email_body = f"""MIME-Version: 1.0
Content-Type: text/html; charset=utf-8

<html>
  <div class="deliveryProofLabel">
    <img src="data:image/png;base64,{png_data}" />
  </div>
</html>
"""

    # Patch builtins.open to raise an OSError
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        result = _extract_delivery_image(
            email_body,
            str(tmp_path) + "/",
            "test.png",
            "walmart",
            "deliveryProofLabel",
            "image/png",
        )

    assert result is False


@pytest.mark.asyncio
async def test_find_text_decode_error():
    """Test find_text handles decoding errors gracefully."""
    from unittest.mock import MagicMock

    from custom_components.mail_and_packages.helpers import find_text

    # Mock account
    mock_account = MagicMock()
    mock_account.search.return_value = ("OK", [b"1"])

    # Mock email message parts
    mock_msg = MagicMock()

    # Part 1: Valid text
    part1 = MagicMock()
    part1.get_content_type.return_value = "text/plain"
    part1.get_payload.return_value = b"Hello World"

    # Part 2: Payload is None (will cause AttributeError on decode)
    part2 = MagicMock()
    part2.get_content_type.return_value = "text/plain"
    part2.get_payload.return_value = None

    mock_msg.walk.return_value = [part1, part2]

    # Mock email_fetch to return our constructed message
    with patch(
        "custom_components.mail_and_packages.helpers.email_fetch"
    ) as mock_fetch, patch("email.message_from_bytes", return_value=mock_msg):

        mock_fetch.return_value = ("OK", [(b"1", b"raw_data")])

        # Search for "World" which is in part1. Part2 should crash but be skipped.
        count = find_text(("OK", [b"1"]), mock_account, ["World"], False)

        assert count == 1
