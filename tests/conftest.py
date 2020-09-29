""" Fixtures for Mail and Packages tests. """
import functools
import imaplib
from tests.const import FAKE_UPDATE_DATA
import pytest
from pytest_homeassistant_custom_component.async_mock import AsyncMock, patch
from tests.helpers.aiohttp import mock_aiohttp_client  # noqa: E402, isort:skip
from unittest import mock
from aiohttp.test_utils import make_mocked_request


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
def mock_imap_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "BAD",
            [b"user@fake.email invalid (Failure)"],
        )

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
def mock_imap_mailbox_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_mailbox_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_mailbox_error.IMAP4_SSL.return_value = mock_conn

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

