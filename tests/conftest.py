""" Fixtures for Mail and Packages tests. """
import imaplib
from unittest import mock
from unittest.mock import patch
from tests.const import FAKE_UPDATE_DATA

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture()
def mock_update():
    """ Mock email data update class values. """
    with patch(
        "custom_components.mail_and_packages.process_emails", autospec=True
    ) as mock_update:
        # value = mock.Mock()
        mock_update.return_value = FAKE_UPDATE_DATA
        yield mock_update


@pytest.fixture()
def mock_imap():
    """ Mock imap class values. """
    with patch("custom_components.mail_and_packages.helpers.imaplib") as mock_imap:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_login_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_login_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_login_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.side_effect = Exception("Invalid username or password")

        yield mock_conn


@pytest.fixture()
def mock_imap_select_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_select_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_select_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )

        mock_conn.select.side_effect = Exception("Invalid folder")

        yield mock_conn


@pytest.fixture()
def mock_imap_list_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_list_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_list_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )

        mock_conn.list.side_effect = Exception("List error")

        yield mock_conn


@pytest.fixture()
def mock_imap_no_email():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_no_email:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_no_email.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("BAD", [])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_search_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_search_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_search_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.side_effect = Exception("Invalid SEARCH format")
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_fetch_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_fetch_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_fetch_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.select.return_value = ("OK", [])
        mock_conn.fetch.side_effect = Exception("Invalid Email")
        yield mock_conn


@pytest.fixture()
def mock_imap_index_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_index_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_index_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "." "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"0"])
        yield mock_imap_index_error


@pytest.fixture()
def mock_imap_index_error_2():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_index_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_index_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) ";" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"0"])
        yield mock_imap_index_error


@pytest.fixture()
def mock_imap_mailbox_format2():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_mailbox_format2:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_mailbox_format2.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "ERR",
            [b'(\\HasNoChildren) "." "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"0"])
        yield mock_conn


@pytest.fixture()
def mock_imap_usps_informed_digest():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_usps_informed_digest:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_usps_informed_digest.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/informed_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_usps_informed_digest_missing():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_usps_informed_digest_missing:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_usps_informed_digest_missing.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/informed_delivery_missing_mailpiece.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_usps_informed_digest_no_mail():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_usps_informed_digest_no_mail:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_usps_informed_digest_no_mail.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/informed_delivery_no_mail.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_ups_out_for_delivery():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_ups_out_for_delivery:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_ups_out_for_delivery.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/ups_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_dhl_out_for_delivery():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_dhl_out_for_delivery:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_dhl_out_for_delivery.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/dhl_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_usps_out_for_delivery():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_usps_out_for_delivery:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_usps_out_for_delivery.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/usps_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_shipped():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_shipped:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_shipped.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_shipped.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_shipped_uk():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_shipped:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_shipped.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_uk_shipped.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_shipped_alt():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_shipped_alt:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_shipped_alt.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_shipped_alt.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_shipped_it():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_shipped_it:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_shipped_it.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_shipped_it.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_delivered():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_delivered:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_delivered.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_delivered.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_delivered_it():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_delivered_it:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_delivered_it.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_delivered_it.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_the_hub():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_the_hub:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_the_hub.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_hub_notice.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def test_valid_ffmpeg():
    """ Fixture to mock which """
    with patch("custom_components.mail_and_packages.helpers.which") as mock_which:
        mock_which.return_value = "anything"
        yield mock_which


@pytest.fixture
def test_invalid_ffmpeg():
    """ Fixture to mock which """
    with patch("custom_components.mail_and_packages.helpers.which") as mock_which:
        mock_which.return_value = None
        yield mock_which


@pytest.fixture
def mock_copyfile_exception():
    """ Fixture to mock which """
    with patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile:
        mock_copyfile.side_effect = Exception("File not found")
        yield mock_copyfile


@pytest.fixture
def mock_copyfile():
    """ Fixture to mock copyfile """
    with patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile:
        mock_copyfile.return_value = True
        yield mock_copyfile


@pytest.fixture
def mock_listdir():
    """ Fixture to mock listdir """
    with patch("os.listdir") as mock_listdir:
        mock_listdir.return_value = [
            "testfile.gif",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir


@pytest.fixture
def mock_osremove():
    """ Fixture to mock remove """
    with patch("os.remove") as mock_remove:
        mock_remove.return_value = True
        yield mock_remove


@pytest.fixture
def mock_osremove_exception():
    """ Fixture to mock remove """
    with patch("os.remove") as mock_osremove_exception:
        mock_osremove_exception.side_effect = Exception("Invalid directory")
        yield mock_osremove_exception


@pytest.fixture
def mock_osmakedir():
    """ Fixture to mock makedirs """
    with patch("os.makedirs") as mock_osmakedir:
        mock_osmakedir.return_value = True
        yield mock_osmakedir


@pytest.fixture
def mock_osmakedir_excpetion():
    """ Fixture to mock makedir """
    with patch("os.makedir") as mock_osmakedir:
        mock_osmakedir.side_effect = Exception("File not found")
        yield mock_osmakedir


@pytest.fixture
def mock_open():
    """ Fixture to mock open """
    with patch("builtins.open") as mock_open:
        mock_open.return_value = mock.Mock(autospec=True)
        mock_open.write.return_value = None
        yield mock_open


@pytest.fixture
def mock_open_excpetion():
    """ Fixture to mock open """
    with patch("builtins.open") as mock_open_excpetion:
        mock_open_excpetion.side_effect = Exception("File not found")

        yield mock_open_excpetion


@pytest.fixture
def mock_os_path_splitext():
    """ Fixture to mock splitext """
    with patch("os.path.splitext") as mock_os_path_splitext:
        mock_os_path_splitext.return_value = ("test_filename", "gif")
        yield mock_os_path_splitext


@pytest.fixture
def mock_update_time():
    """ Fixture to mock splitext """
    with patch(
        "custom_components.mail_and_packages.helpers.update_time"
    ) as mock_update_time:
        mock_update_time.return_value = "Sep-23-2020 10:28 AM"
        yield mock_update_time


@pytest.fixture
def mock_image():
    """ Fixture to mock splitext """
    with patch("custom_components.mail_and_packages.helpers.Image") as mock_image:

        yield mock_image


@pytest.fixture
def mock_image_excpetion():
    """ Fixture to mock splitext """
    with patch(
        "custom_components.mail_and_packages.helpers.Image"
    ) as mock_image_excpetion:
        mock_image_excpetion.return_value = mock.Mock(autospec=True)
        mock_image_excpetion.open.side_effect = Exception("SystemError")
        yield mock_image_excpetion


@pytest.fixture
def mock_resizeimage():
    """ Fixture to mock splitext """
    with patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ) as mock_resizeimage:

        yield mock_resizeimage


@pytest.fixture
def mock_io():
    """ Fixture to mock splitext """
    with patch("custom_components.mail_and_packages.helpers.io") as mock_io:

        yield mock_io


@pytest.fixture
def mock_os_path_isfile():
    """ Fixture to mock splitext """
    with patch("os.path.isfile") as mock_os_path_isfile:
        mock_os_path_isfile.return_value = True
        yield mock_os_path_isfile


@pytest.fixture
def mock_os_path_join():
    """ Fixture to mock splitext """
    with patch("os.path.join") as mock_path_join:

        yield mock_path_join


@pytest.fixture
def mock_os_path_split():
    """ Fixture to mock split """
    with patch("os.path.split") as mock_os_path_split:

        yield mock_os_path_split


@pytest.fixture
def mock_subprocess_call():
    """ Fixture to mock splitext """
    with patch("subprocess.call") as mock_subprocess_call:

        yield mock_subprocess_call


@pytest.fixture
def mock_copy_overlays():
    """ Fixture to mock splitext """
    with patch(
        "custom_components.mail_and_packages.helpers.copy_overlays"
    ) as mock_copy_overlays:

        yield mock_copy_overlays


@pytest.fixture()
def mock_download_img():
    """ Mock email data update class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.download_img", autospec=True
    ) as mock_download_img:
        mock_download_img.return_value = True
        yield mock_download_img


@pytest.fixture()
def mock_imap_hermes_out_for_delivery():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_hermes_out_for_delivery:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_hermes_out_for_delivery.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/hermes_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_royal_out_for_delivery():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_royal_out_for_delivery:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_royal_out_for_delivery.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/royal_mail_uk_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture
def mock_copyoverlays():
    """ Fixture to mock makedirs """
    with patch(
        "custom_components.mail_and_packages.helpers.copy_overlays"
    ) as mock_copyoverlays:
        mock_copyoverlays.return_value = True
        yield mock_copyoverlays
