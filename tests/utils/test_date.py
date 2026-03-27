"""Tests for date utility functions."""

import datetime

import pytest

from custom_components.mail_and_packages.utils.date import (
    get_formatted_date,
    get_today,
    update_time,
)


def test_get_today():
    """Test get_today returns a date."""
    assert isinstance(get_today(), datetime.date)


def test_get_formatted_date():
    """Test get_formatted_date returns a string."""
    assert isinstance(get_formatted_date(), str)


@pytest.mark.asyncio
async def test_update_time():
    """Test update_time returns a datetime."""
    result = await update_time()
    assert isinstance(result, datetime.datetime)
    assert result.tzinfo == datetime.UTC
