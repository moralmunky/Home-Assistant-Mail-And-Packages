""" Fixtures for Mail and Packages tests. """
import imaplib
import aiohttp
from tests.const import FAKE_UPDATE_DATA
import pytest
from pytest_homeassistant_custom_component.async_mock import AsyncMock, patch

from unittest.mock import Mock

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture()
def mock_update():
    """ Mock email data update class values. """
    with patch(
        "custom_components.mail_and_packages.EmailData", autospec=True
    ) as mock_update:
        value = Mock()
        value._data = FAKE_UPDATE_DATA
        value._host = "imap.test.email"
        mock_update.return_value = value
        yield mock_update


@pytest.fixture()
def mock_imap():
    """ Mock imap class values. """
    with patch("custom_components.mail_and_packages.config_flow.imaplib") as mock_imap:
        mock_conn = Mock(spec=imaplib.IMAP4_SSL)
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
        yield mock_imap


@pytest.fixture()
def mock_imap_no_email():
    """ Mock imap class values. """
    with patch("custom_components.mail_and_packages.imaplib") as mock_imap_no_email:
        mock_conn = Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_no_email.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"0"])
        yield mock_imap_no_email


@pytest.fixture()
def mock_imap_index_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.config_flow.imaplib"
    ) as mock_imap_index_error:
        mock_conn = Mock(spec=imaplib.IMAP4_SSL)
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
def mock_imap_mailbox_error():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.config_flow.imaplib"
    ) as mock_imap_mailbox_error:
        mock_conn = Mock(spec=imaplib.IMAP4_SSL)
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
        yield mock_imap_mailbox_error


@pytest.fixture()
def mock_aiohttp():
    """ Mock imap class values. """
    with patch(
        "custom_components.mail_and_packages.aiohttp.ClientSession.get"
    ) as mock_get, patch(
        "custom_components.mail_and_packages.aiohttp.ClientSession.headers"
    ) as mock_headers:
        mock_get.return_value = 200

        mock_conn.get.return_value = 200
        mock_conn.headers.return_value = "content-type: image/jpeg"
        mock_conn.read.return_value = "123456"
        yield mock_aiohttp
