"""Fixtures for Mail and Packages tests."""

import datetime
import errno
import time
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import aioimaplib
import pytest
from aioresponses import aioresponses
from homeassistant import loader
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import (
    CONF_AMAZON_DOMAIN,
    CONFIG_VER,
    DOMAIN,
)
from tests.const import (
    FAKE_CONFIG_DATA,
    FAKE_CONFIG_DATA_AMAZON_FWD_STRING,
    FAKE_CONFIG_DATA_CAPOST,
    FAKE_CONFIG_DATA_CUSTOM_IMG,
    FAKE_CONFIG_DATA_EXTERNAL,
    FAKE_CONFIG_DATA_FORWARDED_EMAILS_NO_AMAZON,
    FAKE_CONFIG_DATA_MISSING_TIMEOUT,
    FAKE_CONFIG_DATA_NO_AMAZON,
    FAKE_CONFIG_DATA_NO_PATH,
    FAKE_CONFIG_DATA_V4_MIGRATE,
    FAKE_UPDATE_DATA,
    FAKE_UPDATE_DATA_BIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"
pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    """Enable custom integration tests."""
    # Only enable if the test actually uses the hass fixture
    try:
        if "hass" in request.fixturenames:
            # Get the hass fixture value
            hass = request.getfixturevalue("hass")
            if isinstance(hass, HomeAssistant):
                # Enable custom integrations
                hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
    except (AttributeError, TypeError, KeyError):
        # Skip for tests that don't need hass or if hass is not available
        pass


@pytest.fixture
def mock_update():
    """Mock email data update class values."""
    with patch(
        "custom_components.mail_and_packages.process_emails", autospec=True
    ) as mock_update:
        # value = mock.Mock()
        mock_update.return_value = FAKE_UPDATE_DATA
        yield mock_update


@pytest.fixture(name="integration")
async def integration_fixture(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
        version=CONFIG_VER,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_no_amazon")
async def integration_fixture_no_amazon(hass):
    """Set up integration with no Amazon sensors and no custom images."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_NO_AMAZON,
        version=CONFIG_VER,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_no_path")
async def integration_fixture_2(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="imap.test.email", data=FAKE_CONFIG_DATA_NO_PATH, version=3
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_no_timeout")
async def integration_fixture_3(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_MISSING_TIMEOUT,
        version=3,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_fwd_string")
async def integration_fixture_4(hass, caplog):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_AMAZON_FWD_STRING,
        version=3,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "Migrating from version 3" in caplog.text
    assert f"Migration complete to version {CONFIG_VER}" in caplog.text

    assert CONF_AMAZON_DOMAIN in entry.data

    return entry


@pytest.fixture(name="integration_custom_img")
async def integration_fixture_5(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CUSTOM_IMG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_fake_external")
async def integration_fixture_6(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_EXTERNAL,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_v4_migration")
async def integration_fixture_7(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_V4_MIGRATE,
        version=4,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_capost")
async def integration_fixture_8(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_CAPOST,
        version=CONFIG_VER,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(name="integration_forwarded_emails_no_amazon")
async def integration_fixture_9(hass):
    """Set up the mail_and_packages integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_FORWARDED_EMAILS_NO_AMAZON,
        version=CONFIG_VER,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture
def mock_imap():
    """Mock aioimaplib class values."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.protocol.state = aioimaplib.AUTH

        # aioimaplib methods return a response object with 'result' and 'lines' attributes
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b"1"]))
        mock_conn.logout = AsyncMock(return_value=MagicMock(result="BYE"))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b'(\\HasNoChildren) "/" "INBOX"']
            )
        )

        # Search returns (result, lines)
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))

        # Configure the fetch response
        email_file = Path("tests/test_emails/informed_delivery.eml").read_bytes()
        mock_conn.fetch.return_value = MagicMock(
            result="OK", lines=[(b"1 (RFC822 {1234}", email_file)]
        )

        yield mock_conn


@pytest.fixture
def mock_imap_login_error():
    """Mock aioimaplib login failure."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.NONAUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        yield mock_conn


@pytest.fixture
def mock_imap_connect_error():
    """Mock aioimaplib connection failure."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server.side_effect = ConnectionRefusedError(
            "Unable to connect."
        )
        mock_conn.protocol.state = aioimaplib.NONAUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        yield mock_conn


@pytest.fixture
def mock_imap_select_error():
    """Mock folder select error."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b"user@fake.email authenticated (Success)"]
            )
        )
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b'(\\HasNoChildren) "/" "INBOX"']
            )
        )
        mock_conn.select.side_effect = OSError("Invalid folder")

        yield mock_conn


@pytest.fixture
def mock_imap_list_error():
    """Mock error when listing folders."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b"user@fake.email authenticated (Success)"]
            )
        )
        mock_conn.list.side_effect = OSError("List error")

        yield mock_conn


@pytest.fixture
def mock_imap_no_email():
    """Mock IMAP connection with no search hits."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.protocol.state = aioimaplib.AUTH

        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b'(\\HasNoChildren) "/" "INBOX"']
            )
        )

        # Search returns "OK" but with no message IDs to simulate an empty mailbox
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))

        mock_conn.logout = AsyncMock()

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_duplicate_orders():
    """Mock duplicate amazon orders found."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(
            return_value=MagicMock(result="OK", lines=[b"1 2"])
        )
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1 2"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        async def fetch_side_effect(email_id, parts):
            content = """From: auto-confirm@amazon.com
Subject: Delivered: Your Amazon.com order #113-4567890-1234567
Order #113-4567890-1234567"""
            return MagicMock(result="OK", lines=[(b"", content.encode())])

        mock_conn.fetch.side_effect = fetch_side_effect
        yield mock_conn


@pytest.fixture
def mock_imap_fetch_error():
    """Mock IMAP fetch error."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.fetch.side_effect = OSError("Invalid Email")

        yield mock_conn


@pytest.fixture
def mock_imap_index_error():
    """Mock imap class values correctly for async and wait_hello."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b'(\\HasNoChildren) "." "INBOX"']
            )
        )
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))

        yield mock_conn


@pytest.fixture
def mock_imap_index_error_2():
    """Mock imap class values for async compatibility and wait_hello."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[b'(\\HasNoChildren) ";" "INBOX"']
            )
        )
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))

        yield mock_conn


@pytest.fixture
def mock_imap_mailbox_format2():
    """Mock imap class values for async compatibility."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="ERR", lines=[b'(\\HasNoChildren) "." "INBOX"']
            )
        )

        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))

        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))

        yield mock_conn


@pytest.fixture
def mock_imap_mailbox_format3():
    """Mock imap class values for async compatibility."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="ERR", lines=[b'(\\HasNoChildren) "%" "INBOX"']
            )
        )

        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))

        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"0"]))

        yield mock_conn


@pytest.fixture
def mock_imap_usps_informed_digest(mock_imap):
    """Mock aioimaplib for USPS Informed Delivery."""
    email_file = Path("tests/test_emails/informed_delivery.eml").read_bytes()
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.fetch.return_value = MagicMock(
        result="OK", lines=[(b"1 (RFC822 {1234}", email_file)]
    )
    return mock_imap


@pytest.fixture
def mock_imap_usps_new_informed_digest():
    """Mock IMAP search returning USPS informed digest."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/new_informed_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_usps_informed_digest_missing():
    """Mock IMAP search returning USPS informed digest with missing mailpiece."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path(
            "tests/test_emails/informed_delivery_missing_mailpiece.eml"
        ).read_text(encoding="utf-8")
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_usps_informed_digest_no_mail():
    """Mock IMAP search returning USPS informed digest with no mail coming."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/informed_delivery_no_mail.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_usps_mail_delivered():
    """Mock IMAP search returning USPS package delivered."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.protocol.state = aioimaplib.AUTH

        # Ensure these are AsyncMocks returning objects with a .result attribute
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))

        email_file = Path("tests/test_emails/usps_mail_delivered.eml").read_text(
            encoding="utf-8"
        )
        # email_fetch in helpers.py looks for result.lines
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"1 (RFC822 {1234}", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_ups_out_for_delivery():
    """Mock IMAP search returning USPS package out for delivery."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/ups_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_ups_out_for_delivery_html():
    """Mock IMAP search returning USPS package out for delivery html format."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn

        # Mock mandatory greeting and login
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

        # Setup .list() response with explicit attributes for logging
        mock_list_response = MagicMock()
        mock_list_response.result = "OK"
        mock_list_response.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_response)

        # Standard IMAP sequence mocks
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()

        # Load the specific UPS HTML email content
        email_file = Path("tests/test_emails/ups_out_for_delivery_new.eml").read_text(
            encoding="utf-8"
        )

        # Setup .fetch() response with explicit attributes
        mock_fetch_response = MagicMock()
        mock_fetch_response.result = "OK"
        mock_fetch_response.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_response)

        yield mock_conn


@pytest.fixture
def mock_imap_dhl_out_for_delivery():
    """Mock IMAP search returning DHL package out for delivery."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.enable = AsyncMock(return_value=MagicMock(result="OK"))

        email_file = Path("tests/test_emails/dhl_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_dhl_no_utf8():
    """Mock IMAP search returning DHL package out for delivery with no UTF-8 encoding."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/dhl_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        mock_conn.enable.side_effect = Exception("BAD", ["Unsupported"])
        yield mock_conn


@pytest.fixture
def mock_imap_fedex_out_for_delivery():
    """Mock IMAP search returning FedEx package out for delivery."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.enable = AsyncMock(return_value=MagicMock(result="OK"))

        email_file = Path("tests/test_emails/fedex_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_fedex_out_for_delivery_2():
    """Mock IMAP search returning FedEx package out for delivery alternative."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_list_response = MagicMock()
        mock_list_response.result = "OK"
        mock_list_response.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_response)

        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()
        email_file = Path("tests/test_emails/fedex_out_for_delivery_2.eml").read_text(
            encoding="utf-8"
        )
        mock_fetch_response = MagicMock()
        mock_fetch_response.result = "OK"
        mock_fetch_response.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_response)

        yield mock_conn


@pytest.fixture
def mock_imap_usps_out_for_delivery():
    """Mock IMAP search returning USPS package out for delivery."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/usps_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_shipped():
    """Mock IMAP search returning Amazon package shipped."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_shipped.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_shipped_uk():
    """Mock IMAP search returning Amazon package shipped UK versionclear."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_uk_shipped.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_amazon_shipped_uk_2():
    """Mock imap class values for UK Amazon shipped email."""
    mock_conn = AsyncMock()
    mock_conn.host = "imap.test.email"

    def imap_response(result, lines):
        res = MagicMock()
        res.result = result
        res.lines = lines
        return res

    mock_conn.login.return_value = imap_response(
        "OK", [b"user@fake.email authenticated (Success)"]
    )
    mock_conn.protocol.state = aioimaplib.AUTH
    mock_conn.list.return_value = imap_response(
        "OK", [b'(\\HasNoChildren) "/" "INBOX"']
    )
    mock_conn.search.return_value = imap_response("OK", [b"1"])
    mock_conn.select.return_value = imap_response("OK", [b"1"])
    mock_conn.logout.return_value = imap_response("BYE", [b"Logging out"])

    # Load the specific UK email content
    email_path = Path("tests/test_emails/amazon_uk_shipped_2.eml")
    email_file = email_path.read_text(encoding="utf-8")

    mock_conn.fetch.return_value = imap_response(
        "OK", [(b"1 (RFC822 {1000}", email_file.encode("utf-8"))]
    )

    return mock_conn


@pytest.fixture
def mock_imap_amazon_shipped_alt():
    """Mock IMAP search with Amazon shipped email, alternative format."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn

        # Handshake and Login
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

        # List response with explicit attributes for debug logging
        mock_list_res = MagicMock()
        mock_list_res.result = "OK"
        mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_res)

        # Standard search and select mocks
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()

        # Load the specific Amazon alternative shipped email content
        email_file = Path("tests/test_emails/amazon_shipped_alt.eml").read_text(
            encoding="utf-8"
        )

        # Fetch response with explicit attributes
        mock_fetch_res = MagicMock()
        mock_fetch_res.result = "OK"
        mock_fetch_res.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_res)

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_shipped_alt_2():
    """Mock IMAP search with Amazon shipped email, 2nd alternative format."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn

        # Handshake and Login
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

        # List response with explicit attributes for debug logging
        mock_list_res = MagicMock()
        mock_list_res.result = "OK"
        mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_res)

        # Standard search and select mocks
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()

        # Load the specific second Amazon alternative shipped email content
        email_file = Path("tests/test_emails/amazon_shipped_alt_2.eml").read_text(
            encoding="utf-8"
        )

        # Fetch response with explicit attributes
        mock_fetch_res = MagicMock()
        mock_fetch_res.result = "OK"
        mock_fetch_res.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_res)

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_shipped_it():
    """Mock IMAP search with Amazon shipped email, Italian format."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_shipped_it.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_amazon_shipped_alt_timeformat():
    """Mock IMAP search with Amazon shipped email, alternative time format."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn

        # Handshake and Login
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

        # List response with explicit attributes for debug logging
        mock_list_res = MagicMock()
        mock_list_res.result = "OK"
        mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_res)

        # Standard search and select mocks
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()

        # Load the specific Amazon alternative time format email content
        email_file = Path(
            "tests/test_emails/amazon_shipped_alt_timeformat.eml"
        ).read_text(encoding="utf-8")

        # Fetch response with explicit attributes
        mock_fetch_res = MagicMock()
        mock_fetch_res.result = "OK"
        mock_fetch_res.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_res)

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_delivered():
    """Mock IMAP search with Amazon delivered email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_delivered.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_delivered_it():
    """Mock IMAP search with Amazon delivered email, italian format."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_delivered_it.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_amazon_the_hub():
    """Mock IMAP search with Amazon hub email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_hub_notice.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_amazon_the_hub_2():
    """Mock imap class values for Amazon Hub emails."""
    mock_conn = AsyncMock()
    mock_conn.host = "imap.test.email"

    def imap_response(result, lines):
        res = MagicMock()
        res.result = result
        res.lines = lines
        return res

    mock_conn.login.return_value = imap_response(
        "OK", [b"user@fake.email authenticated (Success)"]
    )
    mock_conn.protocol.state = aioimaplib.AUTH
    mock_conn.list.return_value = imap_response(
        "OK", [b'(\\HasNoChildren) "/" "INBOX"']
    )
    mock_conn.search.return_value = imap_response("OK", [b"1"])
    mock_conn.select.return_value = imap_response("OK", [])
    mock_conn.logout.return_value = imap_response("BYE", [b"Logging out"])
    email_path = Path("tests/test_emails/amazon_hub_notice_2.eml")
    email_file = email_path.read_text(encoding="utf-8")
    mock_conn.fetch.return_value = imap_response(
        "OK", [(b"1 (RFC822 {2000}", email_file.encode("utf-8"))]
    )

    return mock_conn


@pytest.fixture
def test_valid_ffmpeg():
    """Fixture to mock which."""
    with patch("custom_components.mail_and_packages.helpers.which") as mock_which:
        mock_which.return_value = "anything"
        yield mock_which


@pytest.fixture
def test_invalid_ffmpeg():
    """Fixture to mock which."""
    with patch("custom_components.mail_and_packages.helpers.which") as mock_which:
        mock_which.return_value = None
        yield mock_which


@pytest.fixture
def mock_copyfile_exception():
    """Fixture to mock copyfile."""
    with patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile:
        mock_copyfile.side_effect = OSError("File not found")
        yield mock_copyfile


@pytest.fixture
def mock_copyfile():
    """Fixture to mock copyfile."""
    with patch("custom_components.mail_and_packages.helpers.copyfile") as mock_copyfile:
        mock_copyfile.return_value = True
        yield mock_copyfile


@pytest.fixture
def mock_listdir():
    """Fixture to mock listdir."""
    with patch("os.listdir") as mock_listdir:
        mock_listdir.return_value = [
            "testfile.gif",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir


@pytest.fixture
def mock_listdir_nogif():
    """Fixture to mock listdir."""
    with patch("os.listdir") as mock_listdir_nogif:
        mock_listdir_nogif.return_value = [
            "testfile.jpg",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir_nogif


@pytest.fixture
def mock_listdir_noimgs():
    """Fixture to mock listdir."""
    with patch("os.listdir") as mock_listdir_noimgs:
        mock_listdir_noimgs.return_value = [
            "testfile.xls",
            "anotherfakefile.mp4",
            "lastfile.txt",
        ]
        yield mock_listdir_noimgs


@pytest.fixture
def mock_pathunlink():
    """Fixture to mock remove."""
    with patch("pathlib.Path.unlink", autospec=True):
        yield


@pytest.fixture
def mock_osremove():
    """Fixture to mock remove."""
    with patch("os.remove") as mock_remove:
        mock_remove.return_value = True
        yield mock_remove


@pytest.fixture
def mock_osremove_exception():
    """Fixture to mock remove."""
    with patch("os.remove") as mock_osremove_exception:
        mock_osremove_exception.side_effect = Exception("Invalid directory")
        yield mock_osremove_exception


@pytest.fixture
def mock_osmakedir():
    """Fixture to mock makedirs."""
    with patch("os.makedirs") as mock_osmakedir:
        mock_osmakedir.return_value = True
        yield mock_osmakedir


@pytest.fixture
def mock_osmakedir_excpetion():
    """Fixture to mock makedir."""
    with patch("os.makedir") as mock_osmakedir:
        mock_osmakedir.side_effect = Exception("File not found")
        yield mock_osmakedir


@pytest.fixture
def mock_open_excpetion():
    """Fixture to mock open."""
    with patch("builtins.open") as mock_open_excpetion:
        mock_open_excpetion.side_effect = Exception("File not found")

        yield mock_open_excpetion


@pytest.fixture
def mock_os_path_splitext():
    """Fixture to mock splitext."""
    with patch("os.path.splitext") as mock_os_path_splitext:
        mock_os_path_splitext.return_value = ("test_filename", "gif")
        yield mock_os_path_splitext


@pytest.fixture
def mock_update_time():
    """Fixture to mock update_time."""
    with patch(
        "custom_components.mail_and_packages.helpers.update_time"
    ) as mock_update_time:
        mock_update_time.return_value = datetime.datetime(
            2022, 1, 6, 12, 14, 38, tzinfo=datetime.UTC
        ).isoformat(timespec="minutes")
        # mock_update_time.return_value = "2022-01-06T12:14:38+00:00"
        yield mock_update_time


@pytest.fixture
def mock_image():
    """Fixture to mock Image."""
    with patch("custom_components.mail_and_packages.helpers.Image"):
        yield


@pytest.fixture
def mock_image_excpetion():
    """Fixture to mock Image."""
    with patch(
        "custom_components.mail_and_packages.helpers.Image"
    ) as mock_image_excpetion:
        mock_image_excpetion.return_value = mock.Mock(autospec=True)
        mock_image_excpetion.open.side_effect = Exception("SystemError")
        yield mock_image_excpetion


@pytest.fixture
def mock_image_save_excpetion():
    """Fixture to mock Image."""
    with patch(
        "custom_components.mail_and_packages.helpers.Image"
    ) as mock_image_save_excpetion:
        mock_image_save_excpetion.return_value = mock.Mock(autospec=True)
        mock_image_save_excpetion.Image.save.side_effect = Exception("ValueError")
        yield mock_image_save_excpetion


@pytest.fixture
def mock_resizeimage():
    """Fixture to mock splitext."""
    with (
        patch("custom_components.mail_and_packages.helpers.Image"),
        patch("custom_components.mail_and_packages.helpers.ImageOps"),
    ):
        yield


@pytest.fixture
def mock_os_path_isfile():
    """Fixture to mock isfile."""
    with patch("os.path.isfile") as mock_os_path_isfile:
        mock_os_path_isfile.return_value = True
        yield mock_os_path_isfile


@pytest.fixture
def mock_os_path_join():
    """Fixture to mock join."""
    with patch("os.path.join") as mock_os_path_join:
        mock_os_path_join.return_value = "./testfile.mp4"
        yield mock_os_path_join


@pytest.fixture
def mock_os_path_join2():
    """Fixture to mock join."""
    with patch("os.path.join") as mock_os_path_join:
        mock_os_path_join.return_value = "./testfile_grid.png"
        yield mock_os_path_join


@pytest.fixture
def mock_os_path_split():
    """Fixture to mock split."""
    with patch("os.path.split") as mock_os_path_split:
        yield mock_os_path_split


@pytest.fixture
def mock_subprocess_call():
    """Fixture to mock subprocess."""
    with patch("subprocess.call") as mock_subprocess_call:
        yield mock_subprocess_call


@pytest.fixture
def mock_subprocess_run():
    """Fixture to mock subprocess."""
    with patch("subprocess.run") as mock_subprocess_run:
        yield mock_subprocess_run


@pytest.fixture
def mock_copy_overlays():
    """Fixture to mock copy_overlays."""
    with patch(
        "custom_components.mail_and_packages.helpers.copy_overlays"
    ) as mock_copy_overlays:
        yield mock_copy_overlays


@pytest.fixture
def mock_download_img():
    """Mock email data update class values."""
    # Removed autospec=True to resolve conflict with new_callable
    with patch(
        "custom_components.mail_and_packages.helpers.download_img",
        new_callable=mock.AsyncMock,
    ) as mock_download_img:
        mock_download_img.return_value = True
        yield mock_download_img


@pytest.fixture
def mock_imap_hermes_out_for_delivery():
    """Mock IMAP search with Hermes out for delivery email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/hermes_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_evri_out_for_delivery():
    """Mock IMAP search with Evri out for delivery email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/evri_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_royal_out_for_delivery():
    """Mock IMAP search with Royal Post out for delivery email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path(
            "tests/test_emails/royal_mail_uk_out_for_delivery.eml"
        ).read_text(encoding="utf-8")
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_copyoverlays():
    """Fixture to mock copy_overlays."""
    with patch(
        "custom_components.mail_and_packages.helpers.copy_overlays",
    ) as mock_copyoverlays:
        mock_copyoverlays.return_value = True
        yield mock_copyoverlays


@pytest.fixture
def mock_hash_file():
    """Fixture to mock hash_file."""
    with patch(
        "custom_components.mail_and_packages.helpers.hash_file"
    ) as mock_hash_file:
        mock_hash_file.side_effect = hash_side_effect
        yield mock_hash_file


def hash_side_effect(value):
    """Side effect value."""
    if "mail_none.gif" in value:
        return "633d7356947eec543c50b76a1852f92427f4dca9"
    return "133d7356947fec542c50b76b1856f92427f5dca9"


@pytest.fixture
def mock_getctime_today():
    """Fixture to mock os.path.getctime."""
    with patch(
        "custom_components.mail_and_packages.helpers.os.path.getctime"
    ) as mock_getctime_today:
        mock_getctime_today.return_value = time.time()
        yield mock_getctime_today


@pytest.fixture
def mock_getctime_yesterday():
    """Fixture to mock os.path.getctime."""
    with patch(
        "custom_components.mail_and_packages.helpers.os.path.getctime"
    ) as mock_getctime_yesterday:
        mock_getctime_yesterday.return_value = time.time() - 86400
        yield mock_getctime_yesterday


@pytest.fixture
def mock_hash_file_oserr():
    """Fixture to mock hash_file."""
    with patch(
        "custom_components.mail_and_packages.helpers.hash_file"
    ) as mock_hash_file_oserr:
        mock_hash_file_oserr.side_effect = OSError(errno.EEXIST, "error")
        yield mock_hash_file_oserr


@pytest.fixture
def mock_getctime_err():
    """Fixture to mock os.path.getctime."""
    with patch("os.path.getctime") as mock_getctime_err:
        mock_getctime_err.side_effect = OSError(errno.EEXIST, "error")
        yield mock_getctime_err


@pytest.fixture
def mock_imap_usps_exception():
    """Mock IMAP search with USPS exception email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/usps_exception.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with aioresponses() as mock_aiohttp:
        mock_headers = {"content-type": "image/gif"}
        image_file = Path("tests/test_emails/mail_none.gif").read_bytes()
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
        image_file = Path("tests/test_emails/mail_none.gif").read_bytes()

        mock_aiohttp.get(
            "http://fake.website.com/not/a/real/website/image.jpg",
            status=404,
            headers=mock_headers,
            body=image_file,
        )

        yield mock_aiohttp


@pytest.fixture
def mock_copytree():
    """Fixture to mock copytree."""
    with patch("custom_components.mail_and_packages.helpers.copytree") as mock_copytree:
        mock_copytree.return_value = True
        yield mock_copytree


@pytest.fixture
def mock_imap_amazon_exception():
    """Mock IMAP search with Amazon exception email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_exception.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_auspost_out_for_delivery():
    """Mock IMAP search with AU Post out for delivery email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/auspost_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_auspost_delivered():
    """Mock IMAP search with AU Post delivered email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/auspost_delivered.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_poczta_polska_delivering():
    """Mock IMAP search with poczta polska delivering email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/poczta_polska_delivering.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_inpost_pl_out_for_delivery():
    """Mock IMAP search with inpost pl out for delivery email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/inpost_pl_out_for_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_inpost_pl_delivered():
    """Mock imap class values."""
    with patch(
        "custom_components.mail_and_packages.helpers.aioimaplib"
    ) as mock_imap_inpost_pl_delivered:
        mock_conn = mock.Mock(autospec=aioimaplib.IMAP4_SSL)
        mock_imap_inpost_pl_delivered.IMAP4_SSL.return_value = mock_conn

        mock_conn.login.return_value = (
            "OK",
            [b"user@fake.email authenticated (Success)"],
        )
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.list.return_value = (
            "OK",
            [b'(\\HasNoChildren) "/" "INBOX"'],
        )
        mock_conn.search.return_value = ("OK", [b"1"])
        mock_conn.uid.return_value = ("OK", [b"1"])

        email_file = Path("tests/test_emails/inpost_pl_delivered.eml").read_text(
            encoding="utf-8"
        )

        mock_conn.fetch.return_value = ("OK", [(b"", email_file.encode("utf-8"))])
        mock_conn.select.return_value = ("OK", [])

        yield mock_conn


@pytest.fixture
def mock_imap_dpd_com_pl_delivering():
    """Mock IMAP search with dpd.com.pl delivering email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/dpd_com_pl_delivering.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_search_error():
    """Mock IMAP search error."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.search.side_effect = OSError("Invalid SEARCH format")

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_fwd():
    """Mock IMAP search with forwarded amazon email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_fwd.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_update_amazon_image():
    """Mock email data update class values."""
    with patch(
        "custom_components.mail_and_packages.process_emails", autospec=True
    ) as mock_update:
        # value = mock.Mock()
        mock_update.return_value = FAKE_UPDATE_DATA_BIN
        yield mock_update


@pytest.fixture
def mock_imap_amazon_otp():
    """Mock IMAP search with amazon OTP email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/amazon_otp.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_capost_mail():
    """Mock IMAP search with CA Post mail."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/capost_mail.eml").read_text(
            encoding="utf-8"
        )
        # Updated to match the format of other successful mocks (adding the IMAP header)
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK",
                lines=[(b"1 (RFC822 {1234}", email_file.encode("utf-8"))],
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_ups_delivered():
    """Mock IMAP search with UPS delivered email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn

        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

        mock_list_res = MagicMock()
        mock_list_res.result = "OK"
        mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_res)

        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()

        email_file = Path("tests/test_emails/ups_delivered.eml").read_text(
            encoding="utf-8"
        )

        mock_fetch_res = MagicMock()
        mock_fetch_res.result = "OK"
        mock_fetch_res.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_res)

        yield mock_conn


@pytest.fixture
def mock_imap_ups_delivered_with_photo():
    """Mock IMAP search with UPS delivered email containing delivery photo."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/ups_delivered_with_photo.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_search_error_none():
    """Mock IMAP connection where search returns None or empty results."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_list_res = MagicMock()
        mock_list_res.result = "OK"
        mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_res)
        mock_search_res = MagicMock()
        mock_search_res.result = "OK"
        mock_search_res.lines = [None]
        mock_conn.search = AsyncMock(return_value=mock_search_res)

        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()

        yield mock_conn


@pytest.fixture
def mock_imap_usps_delivered_individual():
    """Mock IMAP search with USPS delivered email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_list_response = MagicMock()
        mock_list_response.result = "OK"
        mock_list_response.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_response)
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        email_file = Path("tests/test_emails/usps_delivered.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )
        yield mock_conn


@pytest.fixture
def mock_imap_amazon_arriving_today():
    """Mock IMAP search with amazon package arriving today email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path(
            "tests/test_emails/amazon_out_for_delivery_today.eml"
        ).read_text(encoding="utf-8")
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_amazon_arriving_tomorrow():
    """Mock aioimaplib class values for Amazon arriving tomorrow email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_list_res = MagicMock()
        mock_list_res.result = "OK"
        mock_list_res.lines = [b'(\\HasNoChildren) "/" "INBOX"']
        mock_conn.list = AsyncMock(return_value=mock_list_res)
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.logout = AsyncMock()
        email_file = Path("tests/test_emails/amazon_arriving_today2.eml").read_text(
            encoding="utf-8"
        )
        mock_fetch_res = MagicMock()
        mock_fetch_res.result = "OK"
        mock_fetch_res.lines = [(b"", email_file.encode("utf-8"))]
        mock_conn.fetch = AsyncMock(return_value=mock_fetch_res)

        yield mock_conn


@pytest.fixture
def mock_imap_walmart_delivered_with_photo():
    """Mock IMAP search with Walmart delivered email containing delivery photo."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/walmart_delivered.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_fedex_delivered_with_photo():
    """Mock IMAP search with FedEx delivered email containing delivery photo."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/fedex_delivered.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_walmart_delivering():
    """Mock IMAP search with Walmart delivering email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path("tests/test_emails/walmart_delivery.eml").read_text(
            encoding="utf-8"
        )
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_informed_delivery_forwarded_email():
    """Mock IMAP search with USPS informed delivery email from forwarded email."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.list = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.uid = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1"]))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))

        email_file = Path(
            "tests/test_emails/informed_delivery_forwarded_email.eml"
        ).read_text(encoding="utf-8")
        mock_conn.fetch = AsyncMock(
            return_value=MagicMock(
                result="OK", lines=[(b"", email_file.encode("utf-8"))]
            )
        )

        yield mock_conn


@pytest.fixture
def mock_imap_list_result_error():
    """Mock IMAP connection where list() returns a non-OK status."""
    with (
        patch("custom_components.mail_and_packages.helpers.IMAP4_SSL") as mock_imap_ssl,
        patch("custom_components.mail_and_packages.helpers.IMAP4") as mock_imap_plain,
    ):
        mock_conn = AsyncMock()
        mock_imap_ssl.return_value = mock_conn
        mock_imap_plain.return_value = mock_conn
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.protocol.state = aioimaplib.AUTH
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b""]))
        mock_conn.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
        mock_conn.logout = AsyncMock()
        # Simulate a successful connection but a failed folder list command
        mock_conn.list = AsyncMock(
            return_value=MagicMock(result="ERROR", lines=[b"Could not list folders"])
        )
        mock_conn.logout = AsyncMock()

        yield mock_conn
