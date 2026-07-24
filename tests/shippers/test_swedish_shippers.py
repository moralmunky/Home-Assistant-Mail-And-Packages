"""Tests for Swedish carrier shippers (PostNord, Bring, DB Schenker)."""

from unittest.mock import MagicMock

import pytest

from custom_components.mail_and_packages.const import ATTR_COUNT, ATTR_TRACKING
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from tests.conftest import _generate_fetch_side_effect


@pytest.fixture
def mock_imap_postnord_delivered(mock_imap):
    """Mock IMAP connection returning PostNord delivered email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])
    email_text = (
        "From: avisering@postnord.se\n"
        "Subject: Ditt paket fran Store finns att hamta\n"
        "Date: Fri, 24 Jul 2026 12:00:00 +0200\n"
        "\n"
        "Ditt paket 1234567890123SE finns att hamta hos ditt ombud."
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_text)
    return mock_imap


@pytest.fixture
def mock_imap_bring_delivering(mock_imap):
    """Mock IMAP connection returning Bring delivering email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])
    email_text = (
        "From: no-reply@bring.com\n"
        "Subject: Din sandning ar pa vag\n"
        "Date: Fri, 24 Jul 2026 12:00:00 +0200\n"
        "\n"
        "Din sandning PARCEL1234567890NO ar pa vag till dig."
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_text)
    return mock_imap


@pytest.fixture
def mock_imap_db_schenker_delivered(mock_imap):
    """Mock IMAP connection returning DB Schenker delivered email."""
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])
    email_text = (
        "From: no-reply@dbschenker.com\n"
        "Subject: Ditt paket finns nu att hamta\n"
        "Date: Fri, 24 Jul 2026 12:00:00 +0200\n"
        "\n"
        "Ditt paket 9876543210 finns nu att hamta."
    )
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_text)
    return mock_imap


@pytest.mark.asyncio
async def test_postnord_delivered(hass, mock_imap_postnord_delivered):
    """Test PostNord delivered email parsing."""
    shipper = GenericShipper(hass, {})
    result = await shipper.process(
        mock_imap_postnord_delivered,
        "today",
        "postnord_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["1234567890123SE"]


@pytest.mark.asyncio
async def test_bring_delivering(hass, mock_imap_bring_delivering):
    """Test Bring delivering email parsing."""
    shipper = GenericShipper(hass, {})
    result = await shipper.process(
        mock_imap_bring_delivering,
        "today",
        "bring_delivering",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["PARCEL1234567890NO"]


@pytest.mark.asyncio
async def test_db_schenker_delivered(hass, mock_imap_db_schenker_delivered):
    """Test DB Schenker delivered email parsing."""
    shipper = GenericShipper(hass, {})
    result = await shipper.process(
        mock_imap_db_schenker_delivered,
        "today",
        "db_schenker_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["9876543210"]
