"""Tests for the Hermes DE shipper."""

import pytest

from custom_components.mail_and_packages.const import ATTR_COUNT, ATTR_TRACKING
from custom_components.mail_and_packages.shippers.generic import GenericShipper


@pytest.mark.asyncio
async def test_hermes_de_delivered(hass, mock_imap_hermes_de_delivered):
    """Test Hermes DE delivered email parsing."""
    shipper = GenericShipper(hass, {})
    result = await shipper.process(
        mock_imap_hermes_de_delivered,
        "today",
        "hermes_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["12345678901234"]


@pytest.mark.asyncio
async def test_hermes_de_delivering_today(hass, mock_imap_hermes_de_delivering_today):
    """Test Hermes DE delivering today email parsing."""
    shipper = GenericShipper(hass, {})
    result = await shipper.process(
        mock_imap_hermes_de_delivering_today,
        "today",
        "hermes_delivering",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["98765432109876"]
