"""Tests for helpers module."""

import datetime
import errno
from freezegun import freeze_time
from datetime import date, timezone
from unittest import mock
from unittest.mock import call, mock_open, patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from custom_components.mail_and_packages.helpers import (
    _generate_mp4,
    amazon_exception,
    amazon_hub,
    amazon_search,
    cleanup_images,
    download_img,
    email_fetch,
    email_search,
    get_count,
    get_formatted_date,
    get_items,
    get_mails,
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
    FAKE_CONFIG_DATA_CORRECTED_EXTERNAL,
    FAKE_CONFIG_DATA_CUSTOM_IMG,
    FAKE_CONFIG_DATA_EXTERNAL,
    FAKE_CONFIG_DATA_NO_RND,
)

MAIL_IMAGE_URL_ENTITY = "sensor.mail_image_url"
MAIL_IMAGE_SYSTEM_PATH = "sensor.mail_image_system_path"


@pytest.mark.asyncio
async def test_get_formatted_date():
    assert get_formatted_date() == datetime.datetime.today().strftime("%d-%b-%Y")


@pytest.mark.asyncio
async def test_update_time():
    assert isinstance(update_time(), datetime.datetime)


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

    config = entry.data.copy()
    assert config == FAKE_CONFIG_DATA_CORRECTED
    state = hass.states.get(MAIL_IMAGE_SYSTEM_PATH)
    assert state is not None
    assert "/testing_config/custom_components/mail_and_packages/images/" in state.state
    state = hass.states.get(MAIL_IMAGE_URL_ENTITY)
    assert state.state == "unknown"
    result = process_emails(hass, config)
    assert isinstance(result["mail_updated"], datetime.datetime)
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
    assert isinstance(result["mail_updated"], datetime.datetime)
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
    assert (
        "www/mail_and_packages/amazon/anotherfakefile.mp4"
        in mock_osremove.call_args.args[0]
    )


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

    entry.version = 2
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
    with patch("os.path.isdir", return_value=False), patch(
        "os.makedirs", side_effect=OSError
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
    result = get_mails(
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
async def test_ups_out_for_delivery_html_only(
    hass, mock_imap_ups_out_for_delivery_html
):
    result = get_count(
        mock_imap_ups_out_for_delivery_html, "ups_delivering", True, "./", hass
    )
    assert result["count"] == 1
    assert result["tracking"] == ["1Z0Y12345678031234"]


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
async def test_amazon_shipped_count(hass, mock_imap_amazon_shipped):
    result = get_items(mock_imap_amazon_shipped, "count")
    assert result == 1


@pytest.mark.asyncio
async def test_amazon_shipped_order(hass, mock_imap_amazon_shipped):
    result = get_items(mock_imap_amazon_shipped, "order")
    assert result == ["123-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt(hass, mock_imap_amazon_shipped_alt):
    result = get_items(mock_imap_amazon_shipped_alt, "order")
    assert result == ["123-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt_2(hass, mock_imap_amazon_shipped_alt_2):
    result = get_items(mock_imap_amazon_shipped_alt_2, "order")
    assert result == ["113-9999999-8459426"]
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2021, 12, 3)

        result = get_items(mock_imap_amazon_shipped_alt_2, "count")
        assert result == 1


@pytest.mark.asyncio
async def test_amazon_shipped_order_alt_timeformat(
    hass, mock_imap_amazon_shipped_alt_timeformat
):
    result = get_items(mock_imap_amazon_shipped_alt_timeformat, "order")
    assert result == ["321-1234567-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_uk(hass, mock_imap_amazon_shipped_uk):
    result = get_items(mock_imap_amazon_shipped_uk, "order")
    assert result == ["123-4567890-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_uk(hass, mock_imap_amazon_shipped_uk_2):
    result = get_items(mock_imap_amazon_shipped_uk_2, "order")
    assert result == ["123-4567890-1234567"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_it(hass, mock_imap_amazon_shipped_it):
    result = get_items(mock_imap_amazon_shipped_it, "order")
    assert result == ["405-5236882-9395563"]


@pytest.mark.asyncio
async def test_amazon_shipped_order_it_count(hass, mock_imap_amazon_shipped_it):
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2021, 12, 1)
        result = get_items(mock_imap_amazon_shipped_it, "count")
        assert result == 1


@pytest.mark.asyncio
async def test_amazon_search(hass, mock_imap_no_email):
    result = amazon_search(mock_imap_no_email, "test/path", hass, "testfilename.jpg")
    assert result == 0


@pytest.mark.asyncio
async def test_amazon_search_results(hass, mock_imap_amazon_shipped):
    result = amazon_search(
        mock_imap_amazon_shipped, "test/path", hass, "testfilename.jpg"
    )
    assert result == 78


@pytest.mark.asyncio
async def test_amazon_search_delivered(
    hass, mock_imap_amazon_delivered, mock_download_img
):
    result = amazon_search(
        mock_imap_amazon_delivered, "test/path", hass, "testfilename.jpg"
    )
    assert result == 78
    assert mock_download_img.called


@pytest.mark.asyncio
async def test_amazon_search_delivered_it(
    hass, mock_imap_amazon_delivered_it, mock_download_img
):
    result = amazon_search(
        mock_imap_amazon_delivered_it, "test/path", hass, "testfilename.jpg"
    )
    assert result == 78


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
        get_items(mock_imap_amazon_shipped, "order")
        assert "Problem decoding email message:" in caplog.text


@pytest.mark.asyncio
async def test_amazon_shipped_order_exception(hass, mock_imap_amazon_shipped, caplog):
    with patch("quopri.decodestring", side_effect=ValueError):
        get_items(mock_imap_amazon_shipped, "order")
        assert "Problem decoding email message:" in caplog.text


@pytest.mark.asyncio
async def test_generate_mp4(
    mock_osremove, mock_os_path_join, mock_subprocess_call, mock_os_path_split
):
    with patch("custom_components.mail_and_packages.helpers.cleanup_images"):
        _generate_mp4("./", "testfile.gif")

        mock_os_path_join.assert_called_with("./", "testfile.mp4")
        # mock_osremove.assert_called_with("./", "testfile.mp4")
        mock_subprocess_call.assert_called_with(
            [
                "ffmpeg",
                "-i",
                "./testfile.mp4",
                "-pix_fmt",
                "yuv420p",
                "./testfile.mp4",
            ],
            stdout=-3,
            stderr=-3,
        )


@pytest.mark.asyncio
async def test_connection_error(caplog):
    result = login("localhost", 993, "fakeuser", "suchfakemuchpassword")
    assert not result
    assert "Network error while connecting to server:" in caplog.text


@pytest.mark.asyncio
async def test_login_error(mock_imap_login_error, caplog):
    login("localhost", 993, "fakeuser", "suchfakemuchpassword")
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
            "http://fake.website.com/not/a/real/website/image.jpg",
            "/fake/directory/",
            "testfilename.jpg",
        )
        assert m_open.call_count == 1
        assert m_open.call_args == call("/fake/directory/amazon/testfilename.jpg", "wb")
        assert "URL content-type: image/gif" in caplog.text
        assert "Amazon image downloaded" in caplog.text


@pytest.mark.asyncio
async def test_download_img_error(aioclient_mock_error, caplog):
    m_open = mock_open()
    with patch("builtins.open", m_open, create=True):
        await download_img(
            "http://fake.website.com/not/a/real/website/image.jpg",
            "/fake/directory/",
            "testfilename.jpg",
        )
        assert "Problem downloading file http error: 404" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_path_error(hass, caplog):
    config = FAKE_CONFIG_DATA_CORRECTED

    with patch("os.path.exists", return_value=False), patch(
        "os.makedirs", side_effect=OSError
    ):
        result = image_file_name(hass, config)
        assert result == "mail_none.gif"
        assert "Problem creating:" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_amazon(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    config = FAKE_CONFIG_DATA_CORRECTED

    with patch("os.path.exists", return_value=True), patch(
        "os.makedirs", return_value=True
    ):
        result = image_file_name(hass, config, True)
        assert result == "testfile.jpg"


@pytest.mark.asyncio
async def test_image_file_name(
    hass, mock_listdir_nogif, mock_getctime_today, mock_hash_file, mock_copyfile, caplog
):
    config = FAKE_CONFIG_DATA_CORRECTED

    with patch("os.path.exists", return_value=True), patch(
        "os.makedirs", return_value=True
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


@pytest.mark.asyncio
async def test_amazon_exception(hass, mock_imap_amazon_exception, caplog):
    result = amazon_exception(mock_imap_amazon_exception, ['""'])
    assert result["order"] == ["123-1234567-1234567"] * 13
    assert result["count"] == 13

    result = amazon_exception(mock_imap_amazon_exception, ["testemail@fakedomain.com"])
    assert result["count"] == 14
    assert (
        "Amazon domains to be checked: ['amazon.com', 'amazon.ca', 'amazon.co.uk', 'amazon.in', 'amazon.de', 'amazon.it', 'amazon.com.au', 'amazon.pl', 'amazon.es', 'amazon.fr', 'amazon.ae', 'fakeuser@fake.email', 'fakeuser2@fake.email', 'testemail@fakedomain.com']"
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
    result = get_items(mock_imap_amazon_fwd, "order")
    assert result == ["123-1234567-1234567"]
    assert "First pass: Tuesday, January 11" in caplog.text
