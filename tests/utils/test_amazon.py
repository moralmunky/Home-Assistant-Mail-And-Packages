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
    filter_amazon_strings,
    get_amazon_image_urls,
    get_decoded_subject,
    get_email_body,
    search_amazon_emails,
)
from custom_components.mail_and_packages.utils.cache import EmailCache


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
    # If the forwarder matches AMAZON_DOMAINS, it gets prefixes added.
    result = amazon_email_addresses(fwds="amazon.com")
    assert "order-update@amazon.com" in result

    # If it doesn't match and has no @, it should be discarded.
    result = amazon_email_addresses(fwds="forward.com")
    assert "order-update@forward.com" not in result


def test_amazon_email_addresses_comma_separated_domains():
    """Comma-separated amazon_domain values should expand into per-domain addresses."""
    result = amazon_email_addresses(domain="amazon.com,amazon.de")
    assert "order-update@amazon.com" in result
    assert "versandbestaetigung@amazon.de" in result
    assert not any("," in address for address in result)


def test_amazon_date_regex_ankunft():
    """German Ankunft arrival wording should be parsed."""
    assert amazon_date_regex("Ankunft heute") == "heute"


@pytest.mark.asyncio
async def test_search_amazon_emails_invalid_days():
    """Test search_amazon_emails with invalid days input."""
    mock_acc = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.utils.amazon.email_search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = ("OK", [None])
        await search_amazon_emails(
            mock_acc, ["test@amazon.com"], "invalid", domain="amazon.com"
        )
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
            b'Content-Type: text/html\n\n<img src="https://us-prod-temp.s3.amazonaws.com/test.jpg">',
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
                b'Content-Type: text/html\n\n<img src="https://us-prod-temp.s3.amazonaws.com/test.jpg">',
            ],
        )
        result = await get_amazon_image_urls("1", mock_acc)
        assert isinstance(result, list)
        assert "https://us-prod-temp.s3.amazonaws.com/test.jpg" in result


def test_get_decoded_subject_non_bytes_decoded():
    """Test get_decoded_subject where decode_header returns non-bytes (Line 51)."""
    msg = MagicMock()
    msg["subject"] = "Test"
    with patch(
        "custom_components.mail_and_packages.utils.amazon.decode_header",
        return_value=[("String Subject", "utf-8")],
    ):
        assert get_decoded_subject(msg) == "String Subject"


def test_get_decoded_subject_multiple_encoded_parts():
    """Test get_decoded_subject joins multi-part encoded headers."""
    msg = email.message_from_string(
        "Subject: =?UTF-8?Q?Ihre_Sendung?= =?UTF-8?Q?_ist_unterwegs_=F0=9F=9A=9A?="
    )
    assert get_decoded_subject(msg) == "Ihre Sendung ist unterwegs \U0001f69a"


def test_get_decoded_subject_from_html_title():
    """Test get_decoded_subject falls back to HTML title when Subject is missing."""
    msg = email.message_from_string(
        "From: test@test.com\n"
        "Content-Type: text/html; charset=utf-8\n"
        "\n"
        "<html><head><title>Package delivered</title></head>"
        "<body>Your order arrived.</body></html>"
    )
    assert get_decoded_subject(msg) == "Package delivered"


def test_amazon_email_addresses_various_fwds():
    """Test amazon_email_addresses with various fwd types."""
    # Prefixes are not language-filtered so English + localized local-parts
    # (AMAZON_EMAIL + AMAZON_SHIPMENT_TRACKING) are all expanded.
    none_result = amazon_email_addresses(fwds=None)
    assert "order-update@amazon.com" in none_result
    assert "shipment-tracking@amazon.com" in none_result
    assert "versandbestaetigung@amazon.com" in none_result
    # Non-list/tuple fwds are ignored the same as None
    assert amazon_email_addresses(fwds=123) == none_result


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


@pytest.mark.asyncio
async def test_search_amazon_emails_with_cache():
    """Test search_amazon_emails with EmailCache (Line 194)."""
    mock_acc = AsyncMock()
    cache = EmailCache(mock_acc)
    # Populate cache with a subject that matches AMAZON_SHIPMENT_SUBJECT "Shipped:"
    cache._cache_headers["1"] = (
        "OK",
        [b"Subject: Shipped: Your Amazon.com order"],
    )

    with patch(
        "custom_components.mail_and_packages.utils.amazon.email_search",
        new_callable=AsyncMock,
    ) as mock_search:
        mock_search.return_value = ("OK", [b"1"])
        result = await search_amazon_emails(
            mock_acc, ["test@amazon.com"], 1, domain="amazon.com", cache=cache
        )
        assert result == [b"1"]


def test_filter_amazon_strings_branches():
    """Test all branches of filter_amazon_strings."""

    # Test with unmapped domain (.co.uk)
    # Should only return base English strings
    test_list = ["order-update@", "versandbestaetigung@"]
    result = filter_amazon_strings(test_list, "amazon.co.uk")
    assert result == ["order-update@"]

    # Test with mapped domain (.de)
    # Should only return German strings
    result = filter_amazon_strings(test_list, "amazon.de")
    assert result == ["versandbestaetigung@"]

    # Test with amazon.ca
    # Should return both English and French strings
    test_list = ["order-update@", "confirmation-commande@"]
    result = filter_amazon_strings(test_list, "amazon.ca")
    assert "order-update@" in result
    assert "confirmation-commande@" in result

    # Test with amazon.com
    # Should only return English strings (no Spanish fallback anymore)
    test_list = ["order-update@", "confirmar-envio@"]
    result = filter_amazon_strings(test_list, "amazon.com")
    assert result == ["order-update@"]


@pytest.mark.asyncio
async def test_get_amazon_image_urls_with_cache():
    """Test get_amazon_image_urls with EmailCache (Line 243)."""
    mock_acc = AsyncMock()
    cache = EmailCache(mock_acc)
    # Populate cache with a domain in AMAZON_IMG_LIST
    cache._cache_rfc822["1"] = (
        "OK",
        [
            b"RFC822",
            b'Content-Type: text/html\n\n<img src="https://us-prod-temp.s3.amazonaws.com/test.jpg">',
        ],
    )

    result = await get_amazon_image_urls("1", mock_acc, cache=cache)
    assert "https://us-prod-temp.s3.amazonaws.com/test.jpg" in result


def test_amazon_email_addresses_forwarder_variations():
    """Test amazon_email_addresses with full emails, standard domains, and invalid domains."""
    # Case 1: Full email address from personal domain
    # Should be preserved as-is.
    fwds = ["my-forwarder@gmail.com"]
    result = amazon_email_addresses(fwds=fwds)
    assert "my-forwarder@gmail.com" in result
    assert "order-update@my-forwarder@gmail.com" not in result

    # Case 2: Standard Amazon domain (no @)
    # Should have prefixes prepended.
    fwds = ["amazon.com"]
    result = amazon_email_addresses(fwds=fwds)
    assert "order-update@amazon.com" in result
    assert "amazon.com" not in result

    # Case 3: Non-Amazon domain without @
    # Should be discarded (not in AMAZON_DOMAINS).
    fwds = ["example.com"]
    result = amazon_email_addresses(fwds=fwds)
    assert "order-update@example.com" not in result
    assert "example.com" not in result


def test_get_email_body_multipart_no_text_plain_non_message_payload():
    """Test get_email_body with a multipart message that lacks a text/plain part."""
    msg = MagicMock(spec=email.message.Message)

    msg.is_multipart.return_value = True

    # Mock walk() to return nothing that matches text/plain
    part = MagicMock(spec=email.message.Message)
    part.get_content_type.return_value = "text/html"
    msg.walk.return_value = [msg, part]

    # Mock get_payload(0) to return a string instead of a Message object
    msg.get_payload.side_effect = lambda i=None, decode=False: (
        "string payload" if i == 0 else ["part1"]
    )

    # This should trigger line 75: return str(payload)
    result = get_email_body(msg)
    assert result == "string payload"


def test_get_email_body_attribute_error():
    """Test get_email_body handles AttributeError during payload decoding."""
    msg = MagicMock(spec=email.message.Message)

    msg.is_multipart.return_value = False
    # Triggers AttributeError on get_payload(decode=True).decode(...)
    msg.get_payload.return_value = None

    assert get_email_body(msg) == ""


@pytest.mark.asyncio
async def test_download_amazon_img_non_200_status(hass, tmp_path):
    """Test download_amazon_img returns early when HTTP status is not 200 (line 220)."""
    img_url = "https://example.com/test.jpg"
    img_path = str(tmp_path)
    img_name = "test.jpg"

    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_resp
    mock_get.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("aiohttp.ClientSession.get", return_value=mock_get),
        patch(
            "custom_components.mail_and_packages.utils.amazon.io_save_file",
        ) as mock_save,
    ):
        await download_amazon_img(img_url, img_path, img_name, hass)
        mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_download_amazon_img_non_image_content_type(hass, tmp_path):
    """Test download_amazon_img returns early when content-type is not image (line 223)."""
    img_url = "https://example.com/test.jpg"
    img_path = str(tmp_path)
    img_name = "test.jpg"

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {"content-type": "text/html"}
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_resp
    mock_get.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("aiohttp.ClientSession.get", return_value=mock_get),
        patch(
            "custom_components.mail_and_packages.utils.amazon.io_save_file",
        ) as mock_save,
    ):
        await download_amazon_img(img_url, img_path, img_name, hass)
        mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_download_amazon_img_content_length_too_large(hass, tmp_path, caplog):
    """Test download_amazon_img returns early when content-length exceeds limit (lines 226-230)."""
    img_url = "https://example.com/test.jpg"
    img_path = str(tmp_path)
    img_name = "test.jpg"

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.headers = {
        "content-type": "image/jpeg",
        "content-length": str(11 * 1024 * 1024),  # 11 MB > 10 MB limit
    }
    mock_get = MagicMock()
    mock_get.__aenter__.return_value = mock_resp
    mock_get.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("aiohttp.ClientSession.get", return_value=mock_get),
        patch(
            "custom_components.mail_and_packages.utils.amazon.io_save_file",
        ) as mock_save,
    ):
        await download_amazon_img(img_url, img_path, img_name, hass)
        mock_save.assert_not_called()

    assert "Amazon image too large to download" in caplog.text


def test_amazon_email_addresses_with_fwds_list():
    """Test amazon_email_addresses with list containing full email and domain substring."""
    result = amazon_email_addresses(fwds=["forwarder@example.com", "amazon.de"])
    assert "forwarder@example.com" in result
    assert "versandbestaetigung@amazon.de" in result


@pytest.mark.asyncio
async def test_search_amazon_emails_single_and_multi_domain():
    """Test search_amazon_emails with single domain and multi-domain."""
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.utils.amazon.email_search",
        new_callable=AsyncMock,
        return_value=("OK", [b"1 2"]),
    ) as mock_search:
        res_single = await search_amazon_emails(
            account=mock_account,
            address_list=["order-update@amazon.de"],
            days=3,
            domain="amazon.de",
        )
        assert res_single == [b"1", b"2"]

        res_multi = await search_amazon_emails(
            account=mock_account,
            address_list=["order-update@amazon.com"],
            days=3,
            domain="amazon.com,amazon.de",
        )
        assert res_multi == [b"1", b"2"]
        assert mock_search.call_count == 2


def test_amazon_email_addresses_fr():
    """Test amazon_email_addresses for amazon.fr includes all required French senders."""
    addresses = amazon_email_addresses(domain="amazon.fr")
    assert "confirmation-commande@amazon.fr" in addresses
    assert "order-update@amazon.fr" in addresses
    assert "shipment-tracking@amazon.fr" in addresses
    assert "pickup-point@amazon.fr" in addresses


def test_filter_amazon_strings_fr():
    """Test filter_amazon_strings for amazon.fr retains French subject strings."""
    subjects = [
        "Expédié",
        "En cours de livraison",
        "Livré",
        "Livrés",
        "Livraison",
        "Commandé",
        "Shipped:",
    ]
    filtered = filter_amazon_strings(subjects, "amazon.fr")
    assert "Expédié" in filtered
    assert "En cours de livraison" in filtered
    assert "Livré" in filtered
    assert "Livrés" in filtered
    assert "Livraison" in filtered
    assert "Commandé" in filtered
    assert "Shipped:" not in filtered


def test_amazon_date_regex_fr():
    """Test amazon_date_regex for French date formats."""
    assert amazon_date_regex("Arrivée : aujourd'hui") == "aujourd'hui"
    assert amazon_date_regex("Arrivée : 14 août") == "14 août"
    assert amazon_date_regex("Livraison : aujourd'hui") == "aujourd'hui"
    assert amazon_date_regex("Livraison : 15 août") == "15 août"
