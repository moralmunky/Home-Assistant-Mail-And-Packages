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


def resolve_entity_id(entity_registry, entry_id: str, domain: str, type_slug: str):
    """Return entity_id for a type slug regardless of HA entity naming version.

    HA changed entity ID generation between 2026.1 and 2026.4 to prefix the
    device name. Resolving via unique_id (stable across versions) avoids
    hardcoding either format in tests.
    """
    for entry in entity_registry.entities.get_entries_for_config_entry_id(entry_id):
        if entry.domain == domain and type_slug in entry.unique_id:
            return entry.entity_id
    return None


def _generate_search_side_effect(count=1, unique=False):
    """Generate search side effect.

    If unique is False (default): Returns [b"1"] on first call, then [b""] forever.
    If unique is True: Returns [b"1"], [b"2"], [b"3"]... for each call.
    """
    iterator = iter(range(1, count + 1)) if unique else iter([1])

    async def search(*args, **kwargs):
        res = MagicMock()
        res.result = "OK"
        try:
            num = next(iterator)
            res.lines = [str(num).encode()]
        except StopIteration:
            # Return empty after the first match (or after count is exhausted)
            res.lines = [b""]
        return res

    return search


def _generate_fetch_side_effect(content):
    """Generate fetch side effect to match requested UID."""

    async def fetch(email_id, parts):
        uid = email_id.decode() if isinstance(email_id, bytes) else email_id
        res = MagicMock()
        res.result = "OK"
        # Return header with matching UID and the content
        header = f"{uid} (UID {uid} BODY[TEXT] {{1234}}".encode()
        body = (
            content
            if isinstance(content, (bytes, bytearray))
            else content.encode("utf-8")
        )
        res.lines = [header, body]
        return res

    return fetch


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
        "custom_components.mail_and_packages.coordinator.MailDataUpdateCoordinator.process_emails",
        autospec=True,
    ) as mock_update:
        # value = mock.Mock()
        mock_update.side_effect = lambda *args, **kwargs: FAKE_UPDATE_DATA.copy()
        yield mock_update


@pytest.fixture(name="integration_factory")
async def integration_factory_fixture(hass):
    """Return a factory to set up the mail_and_packages integration."""

    async def _setup(data, version=CONFIG_VER):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="imap.test.email",
            data=data,
            version=version,
        )
        entry.add_to_hass(hass)
        with patch(
            "custom_components.mail_and_packages.coordinator.MailDataUpdateCoordinator.process_emails",
            return_value=FAKE_UPDATE_DATA,
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        return entry

    return _setup


@pytest.fixture(name="integration")
async def integration_fixture(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA)


@pytest.fixture(name="integration_no_amazon")
async def integration_fixture_no_amazon(integration_factory):
    """Set up integration with no Amazon sensors and no custom images."""
    return await integration_factory(FAKE_CONFIG_DATA_NO_AMAZON)


@pytest.fixture(name="integration_no_path")
async def integration_fixture_2(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_NO_PATH, 3)


@pytest.fixture(name="integration_no_timeout")
async def integration_fixture_3(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_MISSING_TIMEOUT, 3)


@pytest.fixture(name="integration_fwd_string")
async def integration_fixture_4(integration_factory, caplog):
    """Set up the mail_and_packages integration."""
    entry = await integration_factory(FAKE_CONFIG_DATA_AMAZON_FWD_STRING, 3)

    assert "Migrating from version 3" in caplog.text
    assert f"Migration complete to version {CONFIG_VER}" in caplog.text

    assert CONF_AMAZON_DOMAIN in entry.data

    return entry


@pytest.fixture(name="integration_custom_img")
async def integration_fixture_5(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_CUSTOM_IMG)


@pytest.fixture(name="integration_fake_external")
async def integration_fixture_6(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_EXTERNAL)


@pytest.fixture(name="integration_v4_migration")
async def integration_fixture_7(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_V4_MIGRATE, 4)


@pytest.fixture(name="integration_capost")
async def integration_fixture_8(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_CAPOST)


@pytest.fixture(name="integration_forwarded_emails_no_amazon")
async def integration_fixture_9(integration_factory):
    """Set up the mail_and_packages integration."""
    return await integration_factory(FAKE_CONFIG_DATA_FORWARDED_EMAILS_NO_AMAZON)


@pytest.fixture
def mock_imap():
    """Mock aioimaplib class values."""
    mock_imap_class = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
            return_value=mock_imap_class,
        ),
        patch(
            "custom_components.mail_and_packages.utils.imap.IMAP4",
            return_value=mock_imap_class,
        ),
    ):
        mock_conn = mock_imap_class
        mock_conn.protocol.state = aioimaplib.AUTH

        # aioimaplib methods return a response object with 'result' and 'lines' attributes
        mock_conn.wait_hello_from_server = AsyncMock()
        mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
        mock_conn.select = AsyncMock(return_value=("OK", [b"1"]))
        mock_conn.logout = AsyncMock(return_value=MagicMock(result="BYE"))
        mock_conn.list = AsyncMock(
            return_value=MagicMock(
                result="OK",
                lines=[b'(\\HasNoChildren) "/" "INBOX"'],
            ),
        )

        # Search returns (result, lines)
        mock_conn.search = AsyncMock(side_effect=_generate_search_side_effect())

        # Configure the fetch response (default to Informed Delivery)
        email_file = Path("tests/test_emails/informed_delivery.eml").read_bytes()
        mock_conn.fetch = AsyncMock(side_effect=_generate_fetch_side_effect(email_file))

        yield mock_conn


@pytest.fixture
def mock_imap_login_error(mock_imap):
    """Mock aioimaplib login failure."""
    mock_imap.protocol.state = aioimaplib.NONAUTH
    return mock_imap


@pytest.fixture
def mock_imap_connect_error(mock_imap):
    """Mock aioimaplib connection failure."""
    mock_imap.wait_hello_from_server.side_effect = ConnectionRefusedError(
        "Unable to connect.",
    )
    mock_imap.protocol.state = aioimaplib.NONAUTH
    return mock_imap


@pytest.fixture
def mock_imap_select_error(mock_imap):
    """Mock folder select error."""
    mock_imap.login.return_value = MagicMock(
        result="OK",
        lines=[b"user@fake.email authenticated (Success)"],
    )
    mock_imap.select.side_effect = OSError("Invalid folder")
    return mock_imap


@pytest.fixture
def mock_imap_list_error(mock_imap):
    """Mock error when listing folders."""
    mock_imap.login.return_value = MagicMock(
        result="OK",
        lines=[b"user@fake.email authenticated (Success)"],
    )
    mock_imap.list.side_effect = OSError("List error")
    return mock_imap


@pytest.fixture
def mock_imap_no_email(mock_imap):
    """Mock IMAP connection with no search hits."""
    mock_imap.select.return_value = ("OK", [b""])
    # Search returns "OK" but with no message IDs (or empty string) to simulate an empty mailbox
    mock_imap.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    return mock_imap


@pytest.fixture
def mock_imap_amazon_duplicate_orders(mock_imap):
    """Mock duplicate amazon orders found."""
    mock_imap.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1 2"]))
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1 2"])
    mock_imap.select.return_value = ("OK", [b""])

    async def fetch_side_effect(email_id, parts):
        content = """From: auto-confirm@amazon.com
Subject: Delivered: Your Amazon.com order #113-4567890-1234567
Order #113-4567890-1234567"""
        return MagicMock(
            result="OK",
            lines=[
                f"{email_id.decode()} (UID {email_id.decode()} BODY[TEXT] {{1234}}".encode(),
                content.encode(),
            ],
        )

    mock_imap.fetch.side_effect = fetch_side_effect
    return mock_imap


@pytest.fixture
def mock_imap_fetch_error(mock_imap):
    """Mock IMAP fetch error."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.fetch.side_effect = OSError("Invalid Email")
    return mock_imap


@pytest.fixture
def mock_imap_index_error(mock_imap):
    """Mock imap class values correctly for async and wait_hello."""
    mock_imap.list.return_value = MagicMock(
        result="OK",
        lines=[b'(\\HasNoChildren) "." "INBOX"'],
    )
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"0"])
    return mock_imap


@pytest.fixture
def mock_imap_index_error_2(mock_imap):
    """Mock imap class values for async compatibility and wait_hello."""
    mock_imap.list.return_value = MagicMock(
        result="OK",
        lines=[b'(\\HasNoChildren) ";" "INBOX"'],
    )
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"0"])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"0"])
    return mock_imap


@pytest.fixture
def mock_imap_mailbox_format2(mock_imap):
    """Mock imap class values for async compatibility."""
    mock_imap.list.return_value = MagicMock(
        result="ERR",
        lines=[b'(\\HasNoChildren) "." "INBOX"'],
    )
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"0"])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"0"])
    return mock_imap


@pytest.fixture
def mock_imap_mailbox_format3(mock_imap):
    """Mock imap class values for async compatibility."""
    mock_imap.list.return_value = MagicMock(
        result="ERR",
        lines=[b'(\\HasNoChildren) "%" "INBOX"'],
    )
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"0"])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"0"])
    return mock_imap


@pytest.fixture
def mock_imap_usps_informed_digest(mock_imap):
    """Mock aioimaplib for USPS Informed Delivery."""
    email_file = Path("tests/test_emails/informed_delivery.eml").read_bytes()
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_usps_new_informed_digest(mock_imap):
    """Mock IMAP search returning USPS informed digest."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/new_informed_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_usps_informed_digest_missing(mock_imap):
    """Mock IMAP search returning USPS informed digest with missing mailpiece."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path(
        "tests/test_emails/informed_delivery_missing_mailpiece.eml",
    ).read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_usps_informed_digest_no_mail(mock_imap):
    """Mock IMAP search returning USPS informed digest with no mail coming."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/informed_delivery_no_mail.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_usps_mail_delivered(mock_imap):
    """Mock IMAP search returning USPS package delivered."""
    mock_imap.select.return_value = ("OK", [b""])
    email_file = Path("tests/test_emails/usps_mail_delivered.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_ups_out_for_delivery(mock_imap):
    """Mock IMAP search returning USPS package out for delivery."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/ups_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_ups_out_for_delivery_html(mock_imap):
    """Mock IMAP search returning USPS package out for delivery html format."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/ups_out_for_delivery_new.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_dhl_out_for_delivery(mock_imap):
    """Mock IMAP search returning DHL package out for delivery."""
    mock_imap.enable = AsyncMock(return_value=MagicMock(result="OK"))
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/dhl_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_dhl_no_utf8(mock_imap):
    """Mock IMAP search returning DHL package out for delivery with no UTF-8 encoding."""
    mock_imap.enable = AsyncMock(side_effect=Exception("BAD", ["Unsupported"]))
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/dhl_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_fedex_out_for_delivery(mock_imap):
    """Mock IMAP search returning FedEx package out for delivery."""
    mock_imap.enable = AsyncMock(return_value=MagicMock(result="OK"))
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/fedex_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_fedex_out_for_delivery_2(mock_imap):
    """Mock IMAP search returning FedEx package out for delivery alternative."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/fedex_out_for_delivery_2.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_usps_out_for_delivery(mock_imap):
    """Mock IMAP search returning USPS package out for delivery."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/usps_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped(mock_imap):
    """Mock IMAP search returning Amazon package shipped."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_shipped.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped_uk(mock_imap):
    """Mock IMAP search returning Amazon package shipped UK version."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_uk_shipped.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped_uk_2(mock_imap):
    """Mock imap class values for UK Amazon shipped email."""
    mock_imap.host = "imap.test.email"
    mock_imap.login.return_value = MagicMock(
        result="OK",
        lines=[b"user@fake.email authenticated (Success)"],
    )
    mock_imap.select.return_value = MagicMock(result="OK", lines=[b"1"])

    email_path = Path("tests/test_emails/amazon_uk_shipped_2.eml")
    email_file = email_path.read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped_alt(mock_imap):
    """Mock IMAP search with Amazon shipped email, alternative format."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_shipped_alt.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped_alt_2(mock_imap):
    """Mock IMAP search with Amazon shipped email, 2nd alternative format."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_shipped_alt_2.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped_it(mock_imap):
    """Mock IMAP search with Amazon shipped email, Italian format."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_shipped_it.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_shipped_alt_timeformat(mock_imap):
    """Mock IMAP search with Amazon shipped email, alternative time format."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_shipped_alt_timeformat.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_delivered(mock_imap):
    """Mock IMAP search with Amazon delivered email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_delivered.eml").read_text(
        encoding="utf-8",
    )
    # Amazon search expects to find 10 emails in tests, so return unique IDs for 20 calls to be safe
    mock_imap.search.side_effect = _generate_search_side_effect(count=20, unique=True)
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_delivered_it(mock_imap):
    """Mock IMAP search with Amazon delivered email, italian format."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_delivered_it.eml").read_text(
        encoding="utf-8",
    )
    # Amazon search expects to find 10 emails in tests
    mock_imap.search.side_effect = _generate_search_side_effect(count=20, unique=True)
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_the_hub(mock_imap):
    """Mock IMAP search with Amazon hub email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_hub_notice.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_the_hub_2(mock_imap):
    """Mock imap class values for Amazon Hub emails."""
    mock_imap.host = "imap.test.email"
    mock_imap.login.return_value = MagicMock(
        result="OK",
        lines=[b"user@fake.email authenticated (Success)"],
    )
    mock_imap.select.return_value = MagicMock(result="OK", lines=[])

    email_path = Path("tests/test_emails/amazon_hub_notice_2.eml")
    email_file = email_path.read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def test_valid_ffmpeg():
    """Fixture to mock which."""
    with patch("custom_components.mail_and_packages.utils.image.which") as mock_which:
        mock_which.return_value = "anything"
        yield mock_which


@pytest.fixture
def test_invalid_ffmpeg():
    """Fixture to mock which."""
    with patch("custom_components.mail_and_packages.utils.image.which") as mock_which:
        mock_which.return_value = None
        yield mock_which


@pytest.fixture
def mock_copyfile_exception():
    """Fixture to mock copyfile."""
    with patch(
        "custom_components.mail_and_packages.utils.image.copyfile",
    ) as mock_copyfile:
        mock_copyfile.side_effect = OSError("File not found")
        yield mock_copyfile


@pytest.fixture
def mock_copyfile():
    """Fixture to mock copyfile."""
    with patch(
        "custom_components.mail_and_packages.utils.image.copyfile",
    ) as mock_copyfile:
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
        "custom_components.mail_and_packages.utils.date.update_time",
    ) as mock_update_time:
        mock_update_time.return_value = datetime.datetime(
            2022,
            1,
            6,
            12,
            14,
            38,
            tzinfo=datetime.UTC,
        ).isoformat(timespec="minutes")
        yield mock_update_time


@pytest.fixture
def mock_image():
    """Fixture to mock Image."""
    with patch("custom_components.mail_and_packages.utils.image.Image"):
        yield


@pytest.fixture
def mock_image_excpetion():
    """Fixture to mock Image."""
    with patch(
        "custom_components.mail_and_packages.utils.image.Image",
    ) as mock_image_excpetion:
        mock_image_excpetion.return_value = mock.Mock(autospec=True)
        mock_image_excpetion.open.side_effect = Exception("SystemError")
        yield mock_image_excpetion


@pytest.fixture
def mock_image_save_excpetion():
    """Fixture to mock Image."""
    with patch(
        "custom_components.mail_and_packages.utils.image.Image",
    ) as mock_image_save_excpetion:
        mock_image_save_excpetion.return_value = mock.Mock(autospec=True)
        mock_image_save_excpetion.Image.save.side_effect = Exception("ValueError")
        yield mock_image_save_excpetion


@pytest.fixture
def mock_resizeimage():
    """Fixture to mock splitext."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Image"),
        patch("custom_components.mail_and_packages.utils.image.ImageOps"),
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
        "custom_components.mail_and_packages.utils.image.copy_overlays",
    ) as mock_copy_overlays:
        yield mock_copy_overlays


@pytest.fixture
def mock_download_img():
    """Mock email data update class values."""
    with patch(
        "custom_components.mail_and_packages.utils.amazon.download_amazon_img",
        new_callable=mock.AsyncMock,
    ) as mock_download_img:
        mock_download_img.return_value = True
        yield mock_download_img


@pytest.fixture
def mock_imap_hermes_out_for_delivery(mock_imap):
    """Mock IMAP search with Hermes out for delivery email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/hermes_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_evri_out_for_delivery(mock_imap):
    """Mock IMAP search with Evri out for delivery email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/evri_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_royal_out_for_delivery(mock_imap):
    """Mock IMAP search with Royal Post out for delivery email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/royal_mail_uk_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_copyoverlays():
    """Fixture to mock copy_overlays."""
    with patch(
        "custom_components.mail_and_packages.utils.image.copy_overlays",
    ) as mock_copyoverlays:
        mock_copyoverlays.return_value = True
        yield mock_copyoverlays


@pytest.fixture
def mock_hash_file():
    """Fixture to mock hash_file."""
    with patch(
        "custom_components.mail_and_packages.utils.image.hash_file",
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
        "custom_components.mail_and_packages.utils.image.os.path.getctime",
    ) as mock_getctime_today:
        mock_getctime_today.return_value = time.time()
        yield mock_getctime_today


@pytest.fixture
def mock_getctime_yesterday():
    """Fixture to mock os.path.getctime."""
    with patch(
        "custom_components.mail_and_packages.utils.image.os.path.getctime",
    ) as mock_getctime_yesterday:
        mock_getctime_yesterday.return_value = time.time() - 86400
        yield mock_getctime_yesterday


@pytest.fixture
def mock_hash_file_oserr():
    """Fixture to mock hash_file."""
    with patch(
        "custom_components.mail_and_packages.utils.image.hash_file",
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
def mock_imap_usps_exception(mock_imap):
    """Mock IMAP search with USPS exception email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/usps_exception.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


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
def mock_imap_amazon_exception(mock_imap):
    """Mock IMAP search with Amazon exception email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_exception.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_auspost_out_for_delivery(mock_imap):
    """Mock IMAP search with AU Post out for delivery email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/auspost_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_auspost_delivered(mock_imap):
    """Mock IMAP search with AU Post delivered email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/auspost_delivered.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_poczta_polska_delivering(mock_imap):
    """Mock IMAP search with poczta polska delivering email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/poczta_polska_delivering.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_inpost_pl_out_for_delivery(mock_imap):
    """Mock IMAP search with inpost pl out for delivery email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/inpost_pl_out_for_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_inpost_pl_delivered(mock_imap):
    """Mock imap class values."""
    mock_imap.login.return_value = MagicMock(
        result="OK",
        lines=[b"user@fake.email authenticated (Success)"],
    )
    mock_imap.list.return_value = MagicMock(
        result="OK",
        lines=[b'(\\HasNoChildren) "/" "INBOX"'],
    )
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.select.return_value = ("OK", [])

    email_file = Path("tests/test_emails/inpost_pl_delivered.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_dpd_com_pl_delivering(mock_imap):
    """Mock IMAP search with dpd.com.pl delivering email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/dpd_com_pl_delivering.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_search_error(mock_imap):
    """Mock IMAP search error."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.side_effect = OSError("Invalid SEARCH format")
    return mock_imap


@pytest.fixture
def mock_imap_amazon_fwd(mock_imap):
    """Mock IMAP search with forwarded amazon email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_fwd.eml").read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_update_amazon_image():
    """Mock email data update class values."""
    with patch(
        "custom_components.mail_and_packages.coordinator.MailDataUpdateCoordinator.process_emails",
        autospec=True,
    ) as mock_update:
        # value = mock.Mock()
        mock_update.side_effect = lambda *args, **kwargs: FAKE_UPDATE_DATA_BIN.copy()
        yield mock_update


@pytest.fixture
def mock_imap_amazon_otp(mock_imap):
    """Mock IMAP search with amazon OTP email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_otp.eml").read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_capost_mail(mock_imap):
    """Mock IMAP search with CA Post mail."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/capost_mail.eml").read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_ups_delivered(mock_imap):
    """Mock IMAP search with UPS delivered email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/ups_delivered.eml").read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_ups_delivered_with_photo(mock_imap):
    """Mock IMAP search with UPS delivered email containing delivery photo."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/ups_delivered_with_photo.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_search_error_none(mock_imap):
    """Mock IMAP connection where search returns None or empty results."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search = AsyncMock(return_value=MagicMock(result="OK", lines=[None]))
    return mock_imap


@pytest.fixture
def mock_imap_usps_delivered_individual(mock_imap):
    """Mock IMAP search with USPS delivered email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/usps_delivered.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_arriving_today(mock_imap):
    """Mock IMAP search with amazon package arriving today email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_out_for_delivery_today.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_amazon_arriving_tomorrow(mock_imap):
    """Mock aioimaplib class values for Amazon arriving tomorrow email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/amazon_arriving_today2.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_walmart_delivered_with_photo(mock_imap):
    """Mock IMAP search with Walmart delivered email containing delivery photo."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/walmart_delivered.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_fedex_delivered_with_photo(mock_imap):
    """Mock IMAP search with FedEx delivered email containing delivery photo."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/fedex_delivered.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_walmart_delivering(mock_imap):
    """Mock IMAP search with Walmart delivering email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path("tests/test_emails/walmart_delivery.eml").read_text(
        encoding="utf-8",
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_informed_delivery_forwarded_email(mock_imap):
    """Mock IMAP search with USPS informed delivery email from forwarded email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    email_file = Path(
        "tests/test_emails/informed_delivery_forwarded_email.eml",
    ).read_text(encoding="utf-8")
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)
    return mock_imap


@pytest.fixture
def mock_imap_list_result_error(mock_imap):
    """Mock IMAP connection where list() returns a non-OK status."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b""]))
    # Simulate a successful connection but a failed folder list command
    mock_imap.list.return_value = MagicMock(
        result="ERROR",
        lines=[b"Could not list folders"],
    )
    return mock_imap
