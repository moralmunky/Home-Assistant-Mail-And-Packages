"""Tests for init module."""
import datetime
from datetime import date
from custom_components.mail_and_packages.const import DOMAIN, DOMAIN_DATA, DATA
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.async_mock import patch, call
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.mail_and_packages.helpers import (
    get_formatted_date,
    process_emails,
    update_time,
    cleanup_images,
    email_search,
    get_mails,
    _generate_mp4,
    download_img,
    amazon_hub,
    amazon_search,
    get_count,
    get_items,
    login,
)

from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_BAD, FAKE_CONFIG_DATA_NO_RND
import pytest


async def test_unload_entry(hass, mock_update):
    """Test unloading entities. """
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA,
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
        "custom_components.mail_and_packages.helpers.update_time",
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


async def test_process_emails_no_random(hass, mock_imap_no_email):
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA_NO_RND,
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


async def test_get_mails(mock_imap_no_email):
    result = get_mails(mock_imap_no_email, "./", "5", "mail_today.gif", False)
    assert result == 0


async def test_informed_delivery_emails(mock_imap_usps_informed_digest):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove") as mock_osremove, patch(
        "os.makedirs"
    ) as mock_osmakedir, patch(
        "custom_components.mail_and_packages.helpers.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "builtins.open"
    ), patch(
        "custom_components.mail_and_packages.helpers.Image"
    ), patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
    ), patch(
        "custom_components.mail_and_packages.helpers.io"
    ):
        result = get_mails(
            mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", False
        )
        assert result == 3


async def test_informed_delivery_emails_mp4(mock_imap_usps_informed_digest):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove") as mock_osremove, patch(
        "os.makedirs"
    ) as mock_osmakedir, patch(
        "custom_components.mail_and_packages.helpers.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "builtins.open"
    ), patch(
        "custom_components.mail_and_packages.helpers.Image"
    ), patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
    ), patch(
        "custom_components.mail_and_packages.helpers.io"
    ), patch(
        "custom_components.mail_and_packages.helpers._generate_mp4"
    ) as mock_generate_mp4:
        result = get_mails(
            mock_imap_usps_informed_digest, "./", "5", "mail_today.gif", True
        )
        assert result == 3
        assert mock_generate_mp4.called_with("./", "mail_today.gif")


async def test_informed_delivery_emails_open_err(
    mock_imap_usps_informed_digest, caplog
):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove"), patch("os.makedirs"), patch(
        "custom_components.mail_and_packages.helpers.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "custom_components.mail_and_packages.helpers.Image"
    ), patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
    ), patch(
        "custom_components.mail_and_packages.helpers.io"
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


async def test_informed_delivery_emails_io_err(mock_imap_usps_informed_digest):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove"), patch("os.makedirs"), patch(
        "custom_components.mail_and_packages.helpers.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "builtins.open"
    ), patch(
        "custom_components.mail_and_packages.helpers.Image"
    ), patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
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
):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove") as mock_osremove, patch(
        "os.makedirs"
    ) as mock_osmakedir, patch(
        "custom_components.mail_and_packages.helpers.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "builtins.open"
    ), patch(
        "custom_components.mail_and_packages.helpers.Image"
    ), patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
    ), patch(
        "custom_components.mail_and_packages.helpers.io"
    ):
        result = get_mails(
            mock_imap_usps_informed_digest_missing, "./", "5", "mail_today.gif", False
        )
        assert result == 5


async def test_informed_delivery_no_mail(mock_imap_usps_informed_digest_no_mail):
    with patch(
        "os.listdir",
        return_value=["testfile.gif", "anotherfakefile.mp4", "lastfile.txt"],
    ), patch("os.remove"), patch("os.makedirs"), patch(
        "os.path.isfile", return_value=True
    ), patch(
        "custom_components.mail_and_packages.helpers.update_time",
        return_value="Sep-23-2020 10:28 AM",
    ), patch(
        "builtins.open"
    ), patch(
        "custom_components.mail_and_packages.helpers.Image"
    ), patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ), patch(
        "os.path.splitext", return_value=("test_filename", "gif")
    ), patch(
        "custom_components.mail_and_packages.helpers.io"
    ):
        result = get_mails(
            mock_imap_usps_informed_digest_no_mail, "./", "5", "mail_today.gif", False
        )
        assert result == 0


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


async def test_amazon_shipped_count(hass, mock_imap_amazon_shipped):
    with patch("datetime.date") as mock_date:
        mock_date.today.return_value = date(2020, 9, 11)

        result = get_items(mock_imap_amazon_shipped, "count")
        assert result == 4


async def test_amazon_shipped_order(hass, mock_imap_amazon_shipped):
    result = get_items(mock_imap_amazon_shipped, "order")
    assert result == ["#123-1234567-1234567"]


async def test_amazon_shipped_order_alt(hass, mock_imap_amazon_shipped_alt):
    result = get_items(mock_imap_amazon_shipped_alt, "order")
    assert result == ["#123-1234567-1234567"]


async def test_amazon_search(hass, mock_imap_no_email):
    result = amazon_search(mock_imap_no_email, "test/path", hass)
    assert result == 0


async def test_amazon_search_results(hass, mock_imap_amazon_shipped):
    result = amazon_search(mock_imap_amazon_shipped, "test/path", hass)
    assert result == 4


async def test_amazon_search_delivered(hass, mock_imap_amazon_delivered):
    result = amazon_search(mock_imap_amazon_delivered, "test/path", hass)
    assert result == 4


async def test_amazon_hub(hass, mock_imap_amazon_the_hub):
    result = amazon_hub(mock_imap_amazon_the_hub)
    assert result["count"] == 1
    assert result["code"] == ["123456"]


async def test_generate_mp4():
    with patch("os.path.join") as mock_path_join, patch(
        "custom_components.mail_and_packages.helpers.cleanup_images"
    ) as mock_remove, patch("subprocess.call") as mock_subprocess:
        _generate_mp4("./", "testfile.gif")

        mock_path_join.called_with("./", "testfile.gif")
        mock_remove.called_with("./", "testfile.mp4")
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


async def test_login_error(caplog):
    result = login("localhost", 993, "fakeuser", "suchfakemuchpassword")
    assert not result
    assert (
        "Network error while connecting to server: [Errno 111] Connection refused"
        in caplog.text
    )


# async def test_download_img(aioclient_mock):
#     with patch("aiohttp.ClientSession") as mock_client:
#         mock_client = aioclient_mock
#         await download_img("http://fake.website.com", "/not/a/real/website/image.jpg")

