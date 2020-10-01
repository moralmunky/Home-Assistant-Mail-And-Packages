""" Fixtures for Mail and Packages tests. """
import imaplib
from tests.const import FAKE_UPDATE_DATA
import pytest
from pytest_homeassistant_custom_component.async_mock import patch
from tests.helpers.aiohttp import mock_aiohttp_client  # noqa: E402, isort:skip
from unittest import mock


pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture()
def mock_update():
    """ Mock email data update class values. """
    with patch(
        "custom_components.mail_and_packages.EmailData", autospec=True
    ) as mock_update:
        value = mock.Mock()
        value._data = FAKE_UPDATE_DATA
        value._host = "imap.test.email"
        mock_update.return_value = value
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
