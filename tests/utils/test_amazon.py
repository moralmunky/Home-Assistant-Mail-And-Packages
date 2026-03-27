"""Tests for Amazon utility functions."""

import email
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.mail_and_packages.utils.amazon import (
    _extract_hub_code,
    amazon_date_regex,
    amazon_date_search,
    amazon_email_addresses,
    download_amazon_img,
    extract_order_numbers,
    get_amazon_image_urls,
    get_decoded_subject,
    get_email_body,
    search_amazon_emails,
)


def test_get_decoded_subject_error_handling():
    """Test get_decoded_subject with invalid encoding."""
    msg = email.message_from_string("Subject: =?UTF-8?Q?Test?=")
    # Mock decode_header to return a bad encoding
    with patch(
        "custom_components.mail_and_packages.utils.amazon.decode_header",
        return_value=[(b"Test", "invalid-encoding")],
    ):
        result = get_decoded_subject(msg)
        assert result == "Test"


def test_get_decoded_subject_no_subject():
    """Test get_decoded_subject with no subject."""
    msg = email.message_from_string("From: test@test.com")
    assert get_decoded_subject(msg) == ""


def test_get_email_body_error_handling():
    """Test get_email_body with decoding error."""
    msg = MagicMock()
    msg.is_multipart.side_effect = ValueError("Mocked error")
    assert get_email_body(msg) == ""


def test_extract_order_numbers_str_pattern():
    """Test extract_order_numbers with string pattern."""
    result = extract_order_numbers("Order 123-4567890-1234567", r"\d{3}-\d{7}-\d{7}")
    assert result == ["123-4567890-1234567"]


def test_amazon_email_addresses_str_input():
    """Test amazon_email_addresses with string input for fwds."""
    # When fwds is a string, it's treated as a single forwarder.
    # If the forwarder doesn't match AMAZON_DOMAINS, it gets prefixes added.
    result = amazon_email_addresses(fwds="forward.com")
    assert "order-update@forward.com" in result


@pytest.mark.asyncio
async def test_search_amazon_emails_invalid_days():
    """Test search_amazon_emails with invalid days input."""
    mock_acc = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.utils.amazon.email_search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = ("OK", [None])
        await search_amazon_emails(mock_acc, ["test@amazon.com"], "invalid")
        # Should default to DEFAULT_AMAZON_DAYS (3)
        assert mock_search.called


def test_extract_hub_code():
    """Test _extract_hub_code logic."""
    # Hub pattern: (Your pickup code is <b>)(\d{6})
    # Subject pattern: (a package to pick up)(.*)(\d{6})
    assert (
        _extract_hub_code(
            "Body",
            "(Your pickup code is <b>)(\\d{6})",
            "a package to pick up 123456",
            "(a package to pick up)(.*)(\\d{6})",
        )
        == "123456"
    )
    assert (
        _extract_hub_code(
            "Your pickup code is <b>456789",
            "(Your pickup code is <b>)(\\d{6})",
            "Subject",
            "None",
        )
        == "456789"
    )


def test_amazon_date_search_default():
    """Test amazon_date_search with default patterns."""
    # AMAZON_TIME_PATTERN_END contains "Track your"
    assert amazon_date_search("Some text Track your order") != -1


def test_amazon_date_regex_default():
    """Test amazon_date_regex with default patterns."""
    # AMAZON_TIME_PATTERN_REGEX contains "Arriving (\w+ \d+)"
    assert amazon_date_regex("Arriving March 25") == "March 25"


@pytest.mark.asyncio
async def test_get_amazon_image_urls_basic():
    """Test get_amazon_image_urls basic path."""
    mock_acc = AsyncMock()
    mock_acc.fetch.return_value = (
        "OK",
        [
            b"RFC822",
            b'Content-Type: text/html\n\n<img src="https://m.media-amazon.com/images/I/test.jpg">',
        ],
    )
    # AMAZON_IMG_PATTERN and AMAZON_IMG_LIST check
    with patch(
        "custom_components.mail_and_packages.utils.amazon.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = (
            "OK",
            [
                b"RFC822",
                b'Content-Type: text/html\n\n<img src="https://m.media-amazon.com/images/I/test.jpg">',
            ],
        )
        result = await get_amazon_image_urls("1", mock_acc)
        assert isinstance(result, list)
        # Verify it doesn't crash


def test_get_decoded_subject_non_bytes_decoded():
    """Test get_decoded_subject where decode_header returns non-bytes (Line 51)."""
    msg = MagicMock()
    msg["subject"] = "Test"
    with patch(
        "custom_components.mail_and_packages.utils.amazon.decode_header",
        return_value=[("String Subject", "utf-8")],
    ):
        assert get_decoded_subject(msg) == "String Subject"


def test_amazon_email_addresses_various_fwds():
    """Test amazon_email_addresses with various fwd types (Line 119)."""
    # Test with None (triggers Line 119)
    assert len(amazon_email_addresses(fwds=None)) >= 10
    # Test with non-list/tuple (triggers Line 119)
    assert len(amazon_email_addresses(fwds=123)) >= 10


@pytest.mark.asyncio
async def test_download_amazon_img_success(hass, tmp_path):
    """Test download_amazon_img success path (Lines 174-185)."""

    img_url = "https://example.com/test.jpg"
    img_path = str(tmp_path)
    img_name = "test.jpg"

    # Mocking aiohttp session
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"content-type": "image/jpeg"}
    mock_resp.read.return_value = b"image data"

    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_resp

    with (
        patch("aiohttp.ClientSession.get", return_value=mock_get),
        patch(
            "custom_components.mail_and_packages.utils.amazon.io_save_file",
        ) as mock_save,
    ):
        await download_amazon_img(img_url, img_path, img_name, hass)
        assert mock_save.called


@pytest.mark.asyncio
async def test_download_amazon_img_client_error(hass, tmp_path, caplog):
    """Test download_amazon_img with aiohttp error (Line 184)."""

    caplog.set_level("ERROR")
    img_url = "https://example.com/test.jpg"
    img_path = str(tmp_path)
    img_name = "test.jpg"

    # Mocking ClientSession.get to raise ClientError when called
    with patch(
        "aiohttp.ClientSession.get",
        side_effect=aiohttp.ClientError("Connection failed"),
    ):
        await download_amazon_img(img_url, img_path, img_name, hass)
        assert "Problem downloading file" in caplog.text
