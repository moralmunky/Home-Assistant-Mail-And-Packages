"""Tests for IMAP and email utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioimaplib import AUTH, NONAUTH, AioImapException

from custom_components.mail_and_packages.utils.email import (
    find_text,
    generate_service_email_domains,
    validate_email_address,
)
from custom_components.mail_and_packages.utils.imap import (
    InvalidAuth,
    build_search,
    email_fetch,
    email_search,
    login,
    selectfolder,
)


def test_validate_email_address(caplog):
    """Test validate_email_address utility."""
    caplog.set_level("ERROR")
    assert validate_email_address("test@example.com") is True
    assert validate_email_address("invalid-email") is False
    assert "does not look like a valid email address" in caplog.text


def test_generate_service_email_domains():
    """Test generate_service_email_domains utility."""
    amazon_fwds = ["test@amazon.com", "other@amazon.co.uk"]
    domains = generate_service_email_domains(amazon_fwds)
    assert "amazon.com" in domains
    assert "amazon.co.uk" in domains
    # USPS is in SENSOR_DATA default emails
    assert "usps.com" in domains


@pytest.mark.asyncio
async def test_find_text_async():
    """Test find_text utility."""
    mock_account = MagicMock()
    # find_text(sdata, account, search_terms, body_count)
    sdata = [b"1 2"]  # two email IDs
    search_terms = ["1Z1234567890"]

    with patch(
        "custom_components.mail_and_packages.utils.email.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        # Each fetch returns (status, [response_part])
        mock_fetch.return_value = (
            "OK",
            [b"From: test@example.com\n\nTracking 1Z1234567890"],
        )

        result = await find_text(sdata, mock_account, search_terms, False)
        assert result == 2  # 1 match in each of 2 emails
        assert mock_fetch.call_count == 2


@pytest.mark.asyncio
async def test_find_text_body_count():
    """Test find_text with body_count=True (value extraction)."""
    mock_account = MagicMock()
    sdata = [b"1"]
    search_terms = [r"Count: (\d+)"]

    with patch(
        "custom_components.mail_and_packages.utils.email.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", [b"From: test@example.com\n\nCount: 42"])

        result = await find_text(sdata, mock_account, search_terms, True)
        assert result == 42


@pytest.mark.asyncio
async def test_email_fetch_success():
    """Test email_fetch success path."""
    mock_imap = AsyncMock()
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [
        (b"1 (RFC822 {100}", b"From: test@example.com\nSubject: Test\n\nBody content")
    ]
    mock_imap.fetch.return_value = mock_res

    result = await email_fetch(mock_imap, "1")
    assert result[0] == "OK"
    assert b"From: test@example.com" in result[1][0][1]


@pytest.mark.asyncio
async def test_email_fetch_failure(caplog):
    """Test email_fetch failure path."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = OSError("Connection error")
    caplog.set_level("ERROR")

    result = await email_fetch(mock_imap, "1")
    assert result[0] == "BAD"
    assert "Error fetching email" in caplog.text


@pytest.mark.asyncio
async def test_email_fetch_me_com():
    """Test email_fetch for me.com."""
    mock_imap = AsyncMock()
    mock_imap.host = "imap.mail.me.com"
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = []
    mock_imap.fetch.return_value = mock_res

    await email_fetch(mock_imap, "1")
    # Verify parts is BODY[]
    mock_imap.fetch.assert_called_with("1", "BODY[]")


@pytest.mark.asyncio
async def test_login_success():
    """Test login success path."""
    mock_hass = MagicMock()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = NONAUTH

        # After login it should be AUTH or SELECTED
        async def side_effect(*args, **kwargs):
            mock_acc.protocol.state = AUTH

        mock_acc.login.side_effect = side_effect
        mock_imap_ssl.return_value = mock_acc

        result = await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert result == mock_acc
        assert mock_acc.login.called


@pytest.mark.asyncio
async def test_login_oauth_success():
    """Test login with OAuth2 success path."""
    mock_hass = MagicMock()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = NONAUTH

        async def side_effect(*args, **kwargs):
            mock_acc.protocol.state = AUTH

        mock_acc.xoauth2.side_effect = side_effect
        mock_imap_ssl.return_value = mock_acc

        result = await login(
            mock_hass, "host", 993, "user", None, "SSL", oauth_token="token"
        )
        assert result == mock_acc
        assert mock_acc.xoauth2.called


@pytest.mark.asyncio
async def test_login_no_verify():
    """Test login without SSL verification."""
    mock_hass = MagicMock()
    with (
        patch(
            "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
        ) as mock_imap_ssl,
        patch("homeassistant.util.ssl.create_no_verify_ssl_context") as mock_ssl_ctx,
    ):
        mock_acc = AsyncMock()
        mock_acc.protocol.state = AUTH
        mock_imap_ssl.return_value = mock_acc

        await login(mock_hass, "host", 993, "user", "pass", "SSL", verify=False)
        assert mock_ssl_ctx.called


@pytest.mark.asyncio
async def test_login_non_ssl():
    """Test login with STARTTLS/Plain (non-SSL class)."""
    mock_hass = MagicMock()
    with patch("custom_components.mail_and_packages.utils.imap.IMAP4") as mock_imap:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = AUTH
        mock_imap.return_value = mock_acc

        result = await login(mock_hass, "host", 143, "user", "pass", "STARTTLS")
        assert result == mock_acc
        assert mock_imap.called


@pytest.mark.asyncio
async def test_login_failure_no_auth(caplog):
    """Test login failure when state doesn't change to AUTH."""
    mock_hass = MagicMock()
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = NONAUTH
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(InvalidAuth):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert "Error logging in to IMAP Server" in caplog.text


@pytest.mark.asyncio
async def test_login_protocol_auth_state():
    """Test login when protocol state is already AUTH."""
    mock_hass = MagicMock()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = AUTH
        mock_imap_ssl.return_value = mock_acc

        result = await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert result == mock_acc
        assert not mock_acc.login.called


@pytest.mark.asyncio
async def test_login_protocol_state_error():
    """Test login when protocol state is unexpected."""
    mock_hass = MagicMock()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = "UNKNOWN"
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(InvalidAuth):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")


@pytest.mark.asyncio
async def test_selectfolder_success():
    """Test selectfolder success branch."""
    mock_acc = AsyncMock()
    mock_acc.list.return_value = MagicMock()
    mock_acc.select.return_value = MagicMock()

    result = await selectfolder(mock_acc, "INBOX")
    assert result is True
    assert mock_acc.select.called


@pytest.mark.asyncio
async def test_selectfolder_failure(caplog):
    """Test selectfolder failure path."""
    mock_acc = AsyncMock()
    mock_acc.list.side_effect = OSError("List failed")
    caplog.set_level("ERROR")

    result = await selectfolder(mock_acc, "INBOX")
    assert result is False
    assert "Error listing folder" in caplog.text


@pytest.mark.asyncio
async def test_selectfolder_select_error(caplog):
    """Test selectfolder when select fails."""
    mock_acc = AsyncMock()
    mock_acc.list.return_value = MagicMock()
    mock_acc.select.side_effect = OSError("Select failed")
    caplog.set_level("ERROR")

    result = await selectfolder(mock_acc, "INBOX")
    assert result is False
    assert "Error selecting folder" in caplog.text


def test_build_search_no_subject():
    """Test build_search without subject."""
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=None)
    assert "SUBJECT" not in search
    assert 'FROM "test@example.com"' in search


def test_build_search_multiple_no_subject():
    """Test build_search multiple addresses no subject."""
    utf8, search = build_search(["a@b.com", "c@d.com"], "25-Mar-2026", subject=None)
    assert 'OR FROM "a@b.com" FROM "c@d.com"' in search
    assert "SUBJECT" not in search


def test_build_search_prefix_subject():
    """Test build_search with multiple addresses and subject."""
    utf8, search = build_search(["a@b.com", "c@d.com"], "25-Mar-2026", "Test")
    assert 'OR FROM "a@b.com" FROM "c@d.com"' in search
    assert 'SUBJECT "Test"' in search


def test_build_search_triple_address():
    """Test build_search with 3 addresses for OR prefix coverage."""
    utf8, search = build_search(["a@b.com", "c@d.com", "e@f.com"], "25-Mar-2026")
    assert 'OR OR FROM "a@b.com" FROM "c@d.com" FROM "e@f.com"' in search


@pytest.mark.asyncio
async def test_email_search_success():
    """Test email_search success."""
    mock_acc = AsyncMock()
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [b"1 2 3"]
    mock_acc.search.return_value = mock_res

    result = await email_search(mock_acc, ["test@example.com"], "25-Mar-2026")
    assert result[0] == "OK"
    assert result[1] == [b"1 2 3"]


@pytest.mark.asyncio
async def test_email_search_failure(caplog):
    """Test email_search failure."""
    mock_acc = AsyncMock()
    mock_acc.search.side_effect = OSError("Search failed")
    caplog.set_level("ERROR")

    result = await email_search(mock_acc, ["test@example.com"], "25-Mar-2026")
    assert result[0] == "BAD"
    assert "Error searching emails" in caplog.text


@pytest.mark.asyncio
async def test_email_search_error_branch(caplog):
    """Test email_search error logging branch."""
    mock_acc = AsyncMock()
    mock_acc.search.side_effect = AioImapException("Search error")
    caplog.set_level("ERROR")

    result = await email_search(mock_acc, ["a@b.com"], "25-Mar-2026")
    assert result[0] == "BAD"
    assert "Error searching emails" in caplog.text


@pytest.mark.asyncio
async def test_login_exception(caplog):
    """Test login with exception (Line 51)."""
    mock_hass = MagicMock()
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.login.side_effect = OSError("Connection error")
        mock_acc.protocol.state = NONAUTH
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(InvalidAuth):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert "Error logging in to IMAP Server" in caplog.text


@pytest.mark.asyncio
async def test_login_state_fail(caplog):
    """Test login when state doesn't change (Line 55)."""
    mock_hass = MagicMock()
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL"
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.login.return_value = MagicMock(result="OK", lines=[b"Logged in"])
        mock_acc.protocol.state = NONAUTH  # Remains NONAUTH
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(InvalidAuth):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert "Error logging in to IMAP Server" in caplog.text
