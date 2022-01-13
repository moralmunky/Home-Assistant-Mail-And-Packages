""" Fixtures for Mail and Packages tests. """
import datetime
import errno
import imaplib
import time
from datetime import timezone
from unittest import mock
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from tests.const import FAKE_UPDATE_DATA

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture()
def mock_update():
    """Mock email data update class values."""
    with patch(
        "custom_components.mail_and_packages.process_emails", autospec=True
    ) as mock_update:
        # value = mock.Mock()
        mock_update.return_value = FAKE_UPDATE_DATA
        yield mock_update


@pytest.fixture()
def mock_imap():
    """Mock imap class values."""
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
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_login_error:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_login_error.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.side_effect = Exception("Invalid username or password")

        yield mock_conn


@pytest.fixture()
def mock_imap_select_error():
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
        mock_conn.search.return_value = ("OK", [b""])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_search_error():
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
def mock_imap_ups_out_for_delivery_html():
    """Mock imap class values."""
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
        f = open("tests/test_emails/ups_out_for_delivery_new.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_dhl_out_for_delivery():
    """Mock imap class values."""
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
def mock_imap_fedex_out_for_delivery():
    """Mock imap class values."""
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
        f = open("tests/test_emails/fedex_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_fedex_out_for_delivery_2():
    """Mock imap class values."""
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
        f = open("tests/test_emails/fedex_out_for_delivery_2.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_usps_out_for_delivery():
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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
def mock_imap_amazon_shipped_uk_2():
    """Mock imap class values."""
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
        f = open("tests/test_emails/amazon_uk_shipped_2.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_shipped_alt():
    """Mock imap class values."""
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
def mock_imap_amazon_shipped_alt_2():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_shipped_alt_2:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_shipped_alt_2.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_shipped_alt_2.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_shipped_it():
    """Mock imap class values."""
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
def mock_imap_amazon_shipped_alt_timeformat():
    """Mock imap class values."""
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
        f = open("tests/test_emails/amazon_shipped_alt_timeformat.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_amazon_delivered():
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Mock imap class values."""
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


@pytest.fixture()
def mock_imap_amazon_the_hub_2():
    """Mock imap class values."""
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
        f = open("tests/test_emails/amazon_hub_notice_2.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture
def test_valid_ffmpeg():
    """Fixture to mock which"""
    with patch("custom_components.mail_and_packages.helpers.which") as mock_which:
        mock_which.return_value = "anything"
        yield mock_which


@pytest.fixture
def test_invalid_ffmpeg():
    """Fixture to mock which"""
    with patch("custom_components.mail_and_packages.helpers.which") as mock_which:
        mock_which.return_value = None
        yield mock_which


@pytest.fixture
def mock_copyfile_exception():
    """Fixture to mock which"""
    with patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile:
        mock_copyfile.side_effect = Exception("File not found")
        yield mock_copyfile


@pytest.fixture
def mock_copyfile():
    """Fixture to mock copyfile"""
    with patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile:
        mock_copyfile.return_value = True
        yield mock_copyfile


@pytest.fixture
def mock_listdir():
    """Fixture to mock listdir"""
    with patch("os.listdir") as mock_listdir:
        mock_listdir.return_value = [
            "testfile.gif",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir


@pytest.fixture
def mock_listdir_nogif():
    """Fixture to mock listdir"""
    with patch("os.listdir") as mock_listdir_nogif:
        mock_listdir_nogif.return_value = [
            "testfile.jpg",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir_nogif


@pytest.fixture
def mock_listdir_noimgs():
    """Fixture to mock listdir"""
    with patch("os.listdir") as mock_listdir_noimgs:
        mock_listdir_noimgs.return_value = [
            "testfile.xls",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir_noimgs


@pytest.fixture
def mock_osremove():
    """Fixture to mock remove"""
    with patch("os.remove") as mock_remove:
        mock_remove.return_value = True
        yield mock_remove


@pytest.fixture
def mock_osremove_exception():
    """Fixture to mock remove"""
    with patch("os.remove") as mock_osremove_exception:
        mock_osremove_exception.side_effect = Exception("Invalid directory")
        yield mock_osremove_exception


@pytest.fixture
def mock_osmakedir():
    """Fixture to mock makedirs"""
    with patch("os.makedirs") as mock_osmakedir:
        mock_osmakedir.return_value = True
        yield mock_osmakedir


@pytest.fixture
def mock_osmakedir_excpetion():
    """Fixture to mock makedir"""
    with patch("os.makedir") as mock_osmakedir:
        mock_osmakedir.side_effect = Exception("File not found")
        yield mock_osmakedir


@pytest.fixture
def mock_open_excpetion():
    """Fixture to mock open"""
    with patch("builtins.open") as mock_open_excpetion:
        mock_open_excpetion.side_effect = Exception("File not found")

        yield mock_open_excpetion


@pytest.fixture
def mock_os_path_splitext():
    """Fixture to mock splitext"""
    with patch("os.path.splitext") as mock_os_path_splitext:
        mock_os_path_splitext.return_value = ("test_filename", "gif")
        yield mock_os_path_splitext


@pytest.fixture
def mock_update_time():
    """Fixture to mock splitext"""
    with patch(
        "custom_components.mail_and_packages.helpers.update_time"
    ) as mock_update_time:
        mock_update_time.return_value = datetime.datetime(
            2022, 1, 6, 12, 14, 38, tzinfo=timezone.utc
        ).isoformat(timespec="minutes")
        # mock_update_time.return_value = "2022-01-06T12:14:38+00:00"
        yield mock_update_time


@pytest.fixture
def mock_image():
    """Fixture to mock splitext"""
    with patch("custom_components.mail_and_packages.helpers.Image") as mock_image:

        yield mock_image


@pytest.fixture
def mock_image_excpetion():
    """Fixture to mock splitext"""
    with patch(
        "custom_components.mail_and_packages.helpers.Image"
    ) as mock_image_excpetion:
        mock_image_excpetion.return_value = mock.Mock(autospec=True)
        mock_image_excpetion.open.side_effect = Exception("SystemError")
        yield mock_image_excpetion


@pytest.fixture
def mock_resizeimage():
    """Fixture to mock splitext"""
    with patch(
        "custom_components.mail_and_packages.helpers.resizeimage"
    ) as mock_resizeimage:

        yield mock_resizeimage


@pytest.fixture
def mock_io():
    """Fixture to mock splitext"""
    with patch("custom_components.mail_and_packages.helpers.io") as mock_io:

        yield mock_io


@pytest.fixture
def mock_os_path_isfile():
    """Fixture to mock splitext"""
    with patch("os.path.isfile") as mock_os_path_isfile:
        mock_os_path_isfile.return_value = True
        yield mock_os_path_isfile


@pytest.fixture
def mock_os_path_join():
    """Fixture to mock splitext"""
    with patch("os.path.join") as mock_path_join:

        yield mock_path_join


@pytest.fixture
def mock_os_path_split():
    """Fixture to mock split"""
    with patch("os.path.split") as mock_os_path_split:

        yield mock_os_path_split


@pytest.fixture
def mock_subprocess_call():
    """Fixture to mock splitext"""
    with patch("subprocess.call") as mock_subprocess_call:

        yield mock_subprocess_call


@pytest.fixture
def mock_copy_overlays():
    """Fixture to mock splitext"""
    with patch(
        "custom_components.mail_and_packages.helpers.copy_overlays"
    ) as mock_copy_overlays:

        yield mock_copy_overlays


@pytest.fixture()
def mock_download_img():
    """Mock email data update class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.download_img", autospec=True
    ) as mock_download_img:
        mock_download_img.return_value = True
        yield mock_download_img


@pytest.fixture()
def mock_imap_hermes_out_for_delivery():
    """Mock imap class values."""
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
    """Mock imap class values."""
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
    """Fixture to mock makedirs"""
    with patch(
        "custom_components.mail_and_packages.helpers.copy_overlays"
    ) as mock_copyoverlays:
        mock_copyoverlays.return_value = True
        yield mock_copyoverlays


@pytest.fixture
def mock_hash_file():
    """Fixture to mock makedirs"""
    with patch(
        "custom_components.mail_and_packages.helpers.hash_file"
    ) as mock_hash_file:
        mock_hash_file.side_effect = hash_side_effect
        yield mock_hash_file


def hash_side_effect(value):
    if "mail_none.gif" in value:
        return "633d7356947eec543c50b76a1852f92427f4dca9"
    else:
        return "133d7356947fec542c50b76b1856f92427f5dca9"


@pytest.fixture
def mock_getctime_today():
    """Fixture to mock os.path.getctime"""
    with patch(
        "custom_components.mail_and_packages.helpers.os.path.getctime"
    ) as mock_getctime_today:
        mock_getctime_today.return_value = time.time()
        yield mock_getctime_today


@pytest.fixture
def mock_getctime_yesterday():
    """Fixture to mock os.path.getctime"""
    with patch(
        "custom_components.mail_and_packages.helpers.os.path.getctime"
    ) as mock_getctime_yesterday:
        mock_getctime_yesterday.return_value = time.time() - 86400
        yield mock_getctime_yesterday


@pytest.fixture
def mock_hash_file_oserr():
    """Fixture to mock makedirs"""
    with patch(
        "custom_components.mail_and_packages.helpers.hash_file"
    ) as mock_hash_file_oserr:
        mock_hash_file_oserr.side_effect = OSError(errno.EEXIST, "error")
        yield mock_hash_file_oserr


@pytest.fixture
def mock_getctime_err():
    """Fixture to mock os.path.getctime"""
    with patch(
        "custom_components.mail_and_packages.helpers.os.path.getctime"
    ) as mock_getctime_err:
        mock_getctime_err.side_effect = OSError(errno.EEXIST, "error")
        yield mock_getctime_err


@pytest.fixture()
def mock_imap_usps_exception():
    """Mock imap class values."""
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
        f = open("tests/test_emails/usps_exception.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with aioresponses() as mock_aiohttp:
        mock_headers = {"content-type": "image/gif"}
        f = open("tests/test_emails/mail_none.gif", "rb")
        image_file = f.read()
        mock_aiohttp.get(
            "http://fake.website.com/not/a/real/website/image.jpg",
            status=200,
            headers=mock_headers,
            body=image_file,
        )

        yield mock_aiohttp


@pytest.fixture
def aioclient_mock_error():
    """Fixture to mock aioclient calls."""
    with aioresponses() as mock_aiohttp:
        mock_headers = {"content-type": "image/gif"}
        f = open("tests/test_emails/mail_none.gif", "rb")
        image_file = f.read()
        mock_aiohttp.get(
            "http://fake.website.com/not/a/real/website/image.jpg",
            status=404,
            headers=mock_headers,
            body=image_file,
        )

        yield mock_aiohttp


@pytest.fixture
def mock_copytree():
    """Fixture to mock copyfile"""
    with patch("custom_components.mail_and_packages.helpers.copytree") as mock_copytree:
        mock_copytree.return_value = True
        yield mock_copytree


@pytest.fixture()
def mock_imap_amazon_exception():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_exception:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_exception.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_exception.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_auspost_out_for_delivery():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_auspost_out_for_delivery:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_auspost_out_for_delivery.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/auspost_out_for_delivery.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_auspost_delivered():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_auspost_delivered:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_auspost_delivered.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/auspost_delivered.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture()
def mock_imap_search_error_none():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_search_error_none:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_search_error_none.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [None])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn

@pytest.fixture()
def mock_imap_amazon_fwd():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.imaplib"
    ) as mock_imap_amazon_fwd:
        mock_conn = mock.Mock(spec=imaplib.IMAP4_SSL)
        mock_imap_amazon_fwd.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        f = open("tests/test_emails/amazon_fwd.eml", "r")
        email_file = f.read()
        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])
        yield mock_conn


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
