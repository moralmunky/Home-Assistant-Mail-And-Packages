"""Tests for IMAP and email utilities."""

import asyncio
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioimaplib import AUTH, NONAUTH, AioImapException

from custom_components.mail_and_packages.utils.email import (
    find_text,
    find_text_matches,
    generate_service_email_domains,
    validate_email_address,
)
from custom_components.mail_and_packages.utils.imap import (
    InvalidAuth,
    _execute_single_search,
    _parse_esearch_line,
    build_search,
    clean_search_string,
    decode_folder_ref,
    decode_imap_utf7,
    email_fetch,
    email_fetch_batch,
    email_fetch_headers,
    email_fetch_text,
    email_search,
    encode_folder_ref,
    encode_imap_utf7,
    login,
    logout,
    parse_search_response,
    quote_folder,
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
    assert "tracking.usps.com" in domains


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
async def test_find_text_matches_async():
    """Test find_text_matches utility."""
    mock_account = MagicMock()
    sdata = [b"1 2 3"]  # three email IDs
    search_terms = ["1Z1234567890"]

    with patch(
        "custom_components.mail_and_packages.utils.email.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        # Email 1 and 2 match, Email 3 does not
        mock_fetch.side_effect = [
            ("OK", [b"From: test@example.com\n\nTracking 1Z1234567890"]),
            ("OK", [b"From: test@example.com\n\nTracking 1Z1234567890"]),
            ("OK", [b"From: test@example.com\n\nNo tracking info"]),
        ]

        count, matched_ids = await find_text_matches(
            sdata, mock_account, search_terms, False
        )
        assert count == 2
        assert matched_ids == [b"1", b"2"]
        assert mock_fetch.call_count == 3


@pytest.mark.asyncio
async def test_find_text_matches_body_count():
    """Test find_text_matches with body_count=True (value extraction)."""
    mock_account = MagicMock()
    sdata = [b"1 2"]
    search_terms = [r"Count: (\d+)"]

    with patch(
        "custom_components.mail_and_packages.utils.email.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        # Email 1 matches and extracts 42, Email 2 does not match
        mock_fetch.side_effect = [
            ("OK", [b"From: test@example.com\n\nCount: 42"]),
            ("OK", [b"From: test@example.com\n\nNo count here"]),
        ]

        count, matched_ids = await find_text_matches(
            sdata, mock_account, search_terms, True
        )
        assert count == 42
        assert matched_ids == [b"1"]
        assert mock_fetch.call_count == 2


@pytest.mark.asyncio
async def test_email_fetch_success():
    """Test email_fetch success path."""
    mock_imap = AsyncMock()
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [
        (b"1 (RFC822 {100}", b"From: test@example.com\nSubject: Test\n\nBody content"),
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


def _mock_hass() -> MagicMock:
    """Return a hass mock whose executor jobs can be awaited."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    return hass


@pytest.mark.asyncio
async def test_login_success():
    """Test login success path."""
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
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
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = NONAUTH

        async def side_effect(*args, **kwargs):
            mock_acc.protocol.state = AUTH

        mock_acc.xoauth2.side_effect = side_effect
        mock_imap_ssl.return_value = mock_acc

        result = await login(
            mock_hass,
            "host",
            993,
            "user",
            None,
            "SSL",
            oauth_token="token",
        )
        assert result == mock_acc
        assert mock_acc.xoauth2.called


@pytest.mark.asyncio
async def test_login_no_verify():
    """Test login without SSL verification."""
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = AUTH
        mock_imap_ssl.return_value = mock_acc

        await login(mock_hass, "host", 993, "user", "pass", "SSL", verify=False)

        context = mock_imap_ssl.call_args.kwargs["ssl_context"]
        assert context.verify_mode == ssl.CERT_NONE
        assert context.check_hostname is False


@pytest.mark.asyncio
async def test_login_builds_new_ssl_context_each_call():
    """A context must not be reused: a shared one stalls the next handshake."""
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = AUTH
        mock_imap_ssl.return_value = mock_acc

        await login(mock_hass, "host", 993, "user", "pass", "SSL")
        await login(mock_hass, "host", 993, "user", "pass", "SSL")

    first, second = (
        call.kwargs["ssl_context"] for call in mock_imap_ssl.call_args_list
    )
    assert first is not second


@pytest.mark.asyncio
async def test_login_non_ssl():
    """Test login with STARTTLS/Plain (non-SSL class)."""
    mock_hass = _mock_hass()
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
    mock_hass = _mock_hass()
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
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
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
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
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
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
    mock_acc.select.return_value = MagicMock()

    result = await selectfolder(mock_acc, "INBOX")
    assert result is True
    mock_acc.select.assert_called_once_with("INBOX")

    mock_acc.select.reset_mock()
    # Mock cache reset by setting _current_folder to None
    mock_acc._current_folder = None
    result = await selectfolder(mock_acc, "INBOX/Online Shops")
    assert result is True
    mock_acc.select.assert_called_once_with('"INBOX/Online Shops"')


@pytest.mark.asyncio
async def test_selectfolder_failure(caplog):
    """Test selectfolder failure path when select fails."""
    mock_acc = AsyncMock()
    mock_acc.select.side_effect = OSError("Select failed")
    caplog.set_level("ERROR")

    result = await selectfolder(mock_acc, "INBOX")
    assert result is False
    assert "Error selecting folder" in caplog.text


def test_build_search_empty_address_raises():
    """Test build_search raises ValueError when address list is empty."""
    with pytest.raises(ValueError, match="address list must not be empty"):
        build_search([], "25-Mar-2026", subject="Test")


def test_build_search_no_subject():
    """Test build_search without subject."""
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=None)
    assert "SUBJECT" not in search
    assert search == 'FROM "test@example.com" SINCE 25-Mar-2026'

    utf8, search_yahoo = build_search(
        ["test@example.com"], "25-Mar-2026", subject=None, is_yahoo=True
    )
    assert "SUBJECT" not in search_yahoo
    assert search_yahoo == '(FROM "test@example.com" SINCE 25-Mar-2026)'


def test_build_search_multiple_no_subject():
    """Test build_search multiple addresses no subject."""
    utf8, search = build_search(["a@b.com", "c@d.com"], "25-Mar-2026", subject=None)
    assert search == 'OR FROM "a@b.com" FROM "c@d.com" SINCE 25-Mar-2026'

    utf8, search_yahoo = build_search(
        ["a@b.com", "c@d.com"], "25-Mar-2026", subject=None, is_yahoo=True
    )
    assert search_yahoo == '((OR FROM "a@b.com" FROM "c@d.com") SINCE 25-Mar-2026)'


def test_build_search_prefix_subject():
    """Test build_search with multiple addresses and subject."""
    utf8, search = build_search(["a@b.com", "c@d.com"], "25-Mar-2026", "Test")
    assert search == 'OR FROM "a@b.com" FROM "c@d.com" SUBJECT "Test" SINCE 25-Mar-2026'

    utf8, search_yahoo = build_search(
        ["a@b.com", "c@d.com"], "25-Mar-2026", "Test", is_yahoo=True
    )
    assert (
        search_yahoo
        == '((OR FROM "a@b.com" FROM "c@d.com") SUBJECT "Test" SINCE 25-Mar-2026)'
    )


def test_build_search_triple_address():
    """Test build_search with 3 addresses for OR prefix coverage."""
    utf8, search = build_search(["a@b.com", "c@d.com", "e@f.com"], "25-Mar-2026")
    assert (
        search == 'OR OR FROM "a@b.com" FROM "c@d.com" FROM "e@f.com" SINCE 25-Mar-2026'
    )

    utf8, search_yahoo = build_search(
        ["a@b.com", "c@d.com", "e@f.com"], "25-Mar-2026", is_yahoo=True
    )
    assert (
        search_yahoo
        == '((OR OR FROM "a@b.com" FROM "c@d.com" FROM "e@f.com") SINCE 25-Mar-2026)'
    )


def test_build_search_single_header():
    """Test build_search with header mode matches both forwarded (HEADER) and direct (FROM)."""
    utf8, search = build_search(
        ["mcinfo@ups.com"], "25-Mar-2026", header="X-SimpleLogin-Original-From"
    )
    assert (
        search
        == 'OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com" SINCE 25-Mar-2026'
    )

    utf8, search_yahoo = build_search(
        ["mcinfo@ups.com"],
        "25-Mar-2026",
        header="X-SimpleLogin-Original-From",
        is_yahoo=True,
    )
    assert (
        search_yahoo
        == '((OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com") SINCE 25-Mar-2026)'
    )


def test_build_search_multiple_header():
    """Test build_search with header mode for multiple addresses uses OR pairs."""
    utf8, search = build_search(
        ["mcinfo@ups.com", "pkginfo@ups.com"],
        "25-Mar-2026",
        header="X-SimpleLogin-Original-From",
    )
    assert (
        search
        == 'OR OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com" OR HEADER "X-SimpleLogin-Original-From" "pkginfo@ups.com" FROM "pkginfo@ups.com" SINCE 25-Mar-2026'
    )

    utf8, search_yahoo = build_search(
        ["mcinfo@ups.com", "pkginfo@ups.com"],
        "25-Mar-2026",
        header="X-SimpleLogin-Original-From",
        is_yahoo=True,
    )
    assert (
        search_yahoo
        == '((OR OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com" OR HEADER "X-SimpleLogin-Original-From" "pkginfo@ups.com" FROM "pkginfo@ups.com") SINCE 25-Mar-2026)'
    )


def test_build_search_header_with_subject():
    """Test build_search with header mode includes HEADER, FROM, and SUBJECT criteria."""
    utf8, search = build_search(
        ["mcinfo@ups.com"],
        "25-Mar-2026",
        subject="UPS Ship Notification",
        header="X-SimpleLogin-Original-From",
    )
    assert (
        search
        == 'OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com" SUBJECT "UPS Ship Notification" SINCE 25-Mar-2026'
    )

    utf8, search_yahoo = build_search(
        ["mcinfo@ups.com"],
        "25-Mar-2026",
        subject="UPS Ship Notification",
        header="X-SimpleLogin-Original-From",
        is_yahoo=True,
    )
    assert (
        search_yahoo
        == '((OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com") SUBJECT "UPS Ship Notification" SINCE 25-Mar-2026)'
    )


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
    mock_hass = _mock_hass()
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.login.side_effect = OSError("Connection error")
        mock_acc.protocol.state = NONAUTH
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(OSError):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert "Error logging in to IMAP Server" in caplog.text


@pytest.mark.asyncio
async def test_login_state_fail(caplog):
    """Test login when state doesn't change (Line 55)."""
    mock_hass = _mock_hass()
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.login.return_value = MagicMock(result="OK", lines=[b"Logged in"])
        mock_acc.protocol.state = NONAUTH  # Remains NONAUTH
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(InvalidAuth):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")
        assert "Error logging in to IMAP Server" in caplog.text


@pytest.mark.asyncio
async def test_find_text_non_bytes():
    """Test find_text with non-bytes response part (Line 106)."""

    mock_acc = AsyncMock()
    sdata = ("1",)
    with patch(
        "custom_components.mail_and_packages.utils.email.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", ["not bytes"])
        result = await find_text(sdata, mock_acc, ["term"], False)
        assert result == 0


@pytest.mark.asyncio
async def test_find_text_decode_error():
    """Test find_text with decoding error (Line 117-118)."""

    mock_acc = AsyncMock()
    sdata = ("1",)
    with patch(
        "custom_components.mail_and_packages.utils.email.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        email_content = b"Content-Type: text/plain\n\nBody"
        mock_fetch.return_value = ("OK", [email_content])

        with patch("email.message.Message.get_payload", return_value=None):
            result = await find_text(sdata, mock_acc, ["term"], False)
            assert result == 0


@pytest.mark.asyncio
async def test_email_fetch_headers_success():
    """Test email_fetch_headers success path."""
    mock_imap = AsyncMock()
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [b"Subject: Test"]
    mock_imap.fetch.return_value = mock_res

    result = await email_fetch_headers(mock_imap, "1")
    assert result[0] == "OK"
    assert result[1] == [b"Subject: Test"]


@pytest.mark.asyncio
async def test_email_fetch_headers_failure(caplog):
    """Test email_fetch_headers failure path."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = OSError("Connection error")
    caplog.set_level("ERROR")

    result = await email_fetch_headers(mock_imap, "1")
    assert result[0] == "BAD"
    assert "Error fetching email headers" in caplog.text


@pytest.mark.asyncio
async def test_email_fetch_text_success():
    """Test email_fetch_text success path."""
    mock_imap = AsyncMock()
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [b"Text content"]
    mock_imap.fetch.return_value = mock_res

    result = await email_fetch_text(mock_imap, "1")
    assert result[0] == "OK"
    assert result[1] == [b"Text content"]


@pytest.mark.asyncio
async def test_email_fetch_text_me_com():
    """Test email_fetch_text for me.com."""
    mock_imap = AsyncMock()
    mock_imap.host = "imap.mail.me.com"
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = []
    mock_imap.fetch.return_value = mock_res

    await email_fetch_text(mock_imap, "1")
    mock_imap.fetch.assert_called_with("1", "BODY[]")


@pytest.mark.asyncio
async def test_email_fetch_text_failure(caplog):
    """Test email_fetch_text failure path."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = OSError("Connection error")
    caplog.set_level("ERROR")

    result = await email_fetch_text(mock_imap, "1")
    assert result[0] == "BAD"
    assert "Error fetching email text" in caplog.text


@pytest.mark.asyncio
async def test_email_fetch_batch_success():
    """Test email_fetch_batch success path."""
    mock_imap = AsyncMock()
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [b"Batch content"]
    mock_imap.fetch.return_value = mock_res

    result = await email_fetch_batch(mock_imap, ["1", "2"])
    assert result[0] == "OK"
    assert result[1] == [b"Batch content"]
    mock_imap.fetch.assert_called_with("1,2", "(RFC822)")


@pytest.mark.asyncio
async def test_email_fetch_batch_empty():
    """Test email_fetch_batch with empty list."""
    mock_imap = AsyncMock()
    result = await email_fetch_batch(mock_imap, [])
    assert result == ("OK", [])
    assert not mock_imap.fetch.called


@pytest.mark.asyncio
async def test_email_fetch_batch_me_com():
    """Test email_fetch_batch for me.com."""
    mock_imap = AsyncMock()
    mock_imap.host = "imap.mail.me.com"
    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = []
    mock_imap.fetch.return_value = mock_res

    await email_fetch_batch(mock_imap, ["1"])
    mock_imap.fetch.assert_called_with("1", "BODY[]")


@pytest.mark.asyncio
async def test_email_fetch_batch_failure(caplog):
    """Test email_fetch_batch failure path."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = OSError("Connection error")
    caplog.set_level("ERROR")

    result = await email_fetch_batch(mock_imap, ["1"])
    assert result[0] == "BAD"
    assert "Error fetching emails batch" in caplog.text


@pytest.mark.asyncio
async def test_logout_success():
    """Test logout success path."""
    mock_acc = AsyncMock()
    await logout(mock_acc)
    assert mock_acc.logout.called


@pytest.mark.asyncio
async def test_logout_timeout(caplog):
    """Test logout timeout handling."""
    mock_acc = AsyncMock()
    mock_acc.logout.side_effect = TimeoutError("Logout timed out")
    caplog.set_level("DEBUG")

    await logout(mock_acc)
    assert "Error logging out of IMAP Server" in caplog.text


@pytest.mark.asyncio
async def test_logout_cancelled():
    """Cancellation must propagate out of logout.

    logout() runs from a finally while the scan is being cancelled by its
    timeout, so swallowing CancelledError here leaves the coordinator wedged.
    """
    mock_acc = AsyncMock()
    mock_acc.logout.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await logout(mock_acc)


@pytest.mark.asyncio
async def test_logout_oserror(caplog):
    """Test logout OSError handling."""
    mock_acc = AsyncMock()
    mock_acc.logout.side_effect = OSError("Connection lost")
    caplog.set_level("DEBUG")

    await logout(mock_acc)
    assert "Error logging out of IMAP Server" in caplog.text


def test_build_search_list_subject():
    """Test build_search with a list of subjects."""
    # Covers line 104: subjects = subject
    utf8, search = build_search(
        ["test@example.com"], "25-Mar-2026", subject=["Subject 1"]
    )
    assert 'SUBJECT "Subject 1"' in search


def test_build_search_empty_safe_subjects():
    """Test build_search when subjects become empty after ASCII stripping."""
    # Covers line 112: subject_part = ""
    # "😊" is non-ASCII with no ASCII decomposition, and will be stripped to an empty string
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=["😊"])
    assert "SUBJECT" not in search


def test_build_search_multi_subject():
    """Test build_search with multiple subjects to verify OR prefix."""
    subjects = ["One", "Two", "Three"]
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=subjects)
    assert (
        search
        == 'FROM "test@example.com" OR OR SUBJECT "One" SUBJECT "Two" SUBJECT "Three" SINCE 25-Mar-2026'
    )

    utf8, search_yahoo = build_search(
        ["test@example.com"], "25-Mar-2026", subject=subjects, is_yahoo=True
    )
    assert (
        search_yahoo
        == '(FROM "test@example.com" (OR OR SUBJECT "One" SUBJECT "Two" SUBJECT "Three") SINCE 25-Mar-2026)'
    )


def test_build_search_deduplicate_subjects():
    """Test build_search deduplicates safe subjects after ASCII normalization."""
    subjects = ["Commandé:", "Commandé :", "Commandé"]
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=subjects)
    assert search == 'FROM "test@example.com" SUBJECT "Commande" SINCE 25-Mar-2026'


def test_build_search_single_addr_with_subject():
    """Test build_search with single address and subject."""
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject="Test")
    assert search == 'FROM "test@example.com" SUBJECT "Test" SINCE 25-Mar-2026'

    utf8, search_yahoo = build_search(
        ["test@example.com"], "25-Mar-2026", subject="Test", is_yahoo=True
    )
    assert search_yahoo == '(FROM "test@example.com" SUBJECT "Test" SINCE 25-Mar-2026)'


def test_build_search_with_body():
    """Test build_search with body parameter."""
    # Single body string
    utf8, search = build_search(
        ["test@example.com"], "25-Mar-2026", body="Tracking 1Z1234567890"
    )
    assert 'BODY "Tracking 1Z1234567890"' in search

    # Multiple body strings
    utf8, search = build_search(
        ["test@example.com"],
        "25-Mar-2026",
        body=["Tracking 1Z1234567890", "Order #12345"],
    )
    assert 'BODY "Tracking 1Z1234567890"' in search
    assert 'BODY "Order #12345"' in search

    # Yahoo IMAP with body
    utf8, search_yahoo = build_search(
        ["test@example.com"], "25-Mar-2026", body="Tracking 1Z1234567890", is_yahoo=True
    )
    assert 'BODY "Tracking 1Z1234567890"' in search_yahoo

    # Yahoo IMAP with multiple bodies
    utf8, search_yahoo_multi = build_search(
        ["test@example.com"],
        "25-Mar-2026",
        body=["Tracking 1Z1234567890", "Order #12345"],
        is_yahoo=True,
    )
    assert '(OR BODY "Tracking 1Z1234567890" BODY "Order #12345")' in search_yahoo_multi

    # Body with subject
    utf8, search = build_search(
        ["test@example.com"],
        "25-Mar-2026",
        subject="Test",
        body="Tracking 1Z1234567890",
    )
    assert 'SUBJECT "Test"' in search
    assert 'BODY "Tracking 1Z1234567890"' in search

    # Body with subject and Yahoo
    utf8, search_yahoo = build_search(
        ["test@example.com"],
        "25-Mar-2026",
        subject="Test",
        body="Tracking 1Z1234567890",
        is_yahoo=True,
    )
    assert 'SUBJECT "Test"' in search_yahoo
    assert 'BODY "Tracking 1Z1234567890"' in search_yahoo


def test_build_search_with_body_and_empty_body():
    """Test build_search with empty body string."""
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", body="")
    assert "BODY" not in search

    # Empty list of bodies
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", body=[])
    assert "BODY" not in search

    # None body
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", body=None)
    assert "BODY" not in search


def test_build_search_with_body_and_non_ascii():
    """Test build_search with non-ASCII body strings."""
    # Non-ASCII characters should be stripped or normalized
    utf8, search = build_search(
        ["test@example.com"], "25-Mar-2026", body="Tracking émojis 🎉"
    )
    assert 'BODY "Tracking emojis"' in search


def test_build_search_unicode_normalization():
    """Test that accented characters decompose to their base ASCII equivalents."""
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject="Livré")
    assert 'SUBJECT "Livre"' in search

    utf8, search2 = build_search(["test@example.com"], "25-Mar-2026", body="Café")
    assert 'BODY "Cafe"' in search2


def test_build_search_quotes_removed():
    """Test that double quotes are removed from search terms to prevent query corruption."""
    utf8, search = build_search(
        ["test@example.com"], "25-Mar-2026", subject='UPS "Notification"'
    )
    assert 'SUBJECT "UPS Notification"' in search

    utf8, search2 = build_search(
        ["test@example.com"], "25-Mar-2026", body='order "123"'
    )
    assert 'BODY "order 123"' in search2

    # Mixed ASCII and non-ASCII
    utf8, search = build_search(
        ["test@example.com"], "25-Mar-2026", body="Tracking 1Z1234567890 émojis"
    )
    assert 'BODY "Tracking 1Z1234567890 emojis"' in search


def test_clean_search_string_empty():
    """Test clean_search_string with empty or falsy inputs."""
    assert clean_search_string("") == ""
    assert clean_search_string(None) == ""  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_email_search_batching():
    """Test email_search batching logic for multiple subjects."""
    mock_acc = AsyncMock()

    # Mocking two batches: first with IDs 1 2, second with ID 3
    res1 = MagicMock()
    res1.result = "OK"
    res1.lines = [b"1 2"]

    res2 = MagicMock()
    res2.result = "OK"
    res2.lines = [b"3"]

    mock_acc.search.side_effect = [res1, res2]

    # 2 subjects will trigger 2 batches (1 + 1) with IMAP_SUBJECT_BATCH_SIZE = 1
    subjects = [f"Sub{i}" for i in range(2)]
    result = await email_search(
        mock_acc, ["test@example.com"], "25-Mar-2026", subject=subjects
    )

    assert result[0] == "OK"
    assert result[1] == [b"1 2 3"]
    assert mock_acc.search.call_count == 2


@pytest.mark.asyncio
async def test_email_search_batching_partially_no_results():
    """Test email_search batching where one batch returns no results."""
    mock_acc = AsyncMock()

    res1 = MagicMock()
    res1.result = "OK"
    res1.lines = [b"1 2"]

    res2 = MagicMock()
    res2.result = "OK"
    res2.lines = [None]  # No results in second batch

    mock_acc.search.side_effect = [res1, res2]

    subjects = [f"Sub{i}" for i in range(2)]
    result = await email_search(
        mock_acc, ["test@example.com"], "25-Mar-2026", subject=subjects
    )

    assert result[0] == "OK"
    assert result[1] == [b"1 2"]


@pytest.mark.asyncio
async def test_email_search_batching_error(caplog):
    """Test email_search batching with an error in one batch."""
    mock_acc = AsyncMock()
    caplog.set_level("ERROR")

    res1 = MagicMock()
    res1.result = "OK"
    res1.lines = [b"1 2"]

    mock_acc.search.side_effect = [res1, OSError("Batch failure")]

    subjects = [f"Sub{i}" for i in range(2)]
    result = await email_search(
        mock_acc, ["test@example.com"], "25-Mar-2026", subject=subjects
    )

    assert result[0] == "OK"
    assert result[1] == [b"1 2"]
    assert "Error searching emails batch: Batch failure" in caplog.text


@pytest.mark.asyncio
async def test_email_search_batching_all_error():
    """Test email_search batching when all batches fail."""
    mock_acc = AsyncMock()
    mock_acc.search.side_effect = OSError("Batch failure")

    subjects = [f"Sub{i}" for i in range(2)]
    result = await email_search(
        mock_acc, ["test@example.com"], "25-Mar-2026", subject=subjects
    )

    assert result == ("BAD", "All search batches failed")


@pytest.mark.asyncio
async def test_email_search_address_batching():
    """Test email_search batching logic for > 5 sender addresses."""
    mock_acc = AsyncMock()

    res1 = MagicMock()
    res1.result = "OK"
    res1.lines = [b"1 2"]

    res2 = MagicMock()
    res2.result = "OK"
    res2.lines = [b"3"]

    mock_acc.search.side_effect = [res1, res2]

    addresses = [f"sender{i}@example.com" for i in range(6)]
    result = await email_search(mock_acc, addresses, "25-Mar-2026", subject="Test")

    assert result[0] == "OK"
    assert result[1] == [b"1 2 3"]
    assert mock_acc.search.call_count == 2


def test_build_search_multi_addr_multi_subject_parentheses():
    """Test that multi-address AND multi-subject queries use explicit parentheses on Yahoo.

    Regression test for Yahoo IMAP misparsing where FROM OR-chain and SUBJECT
    OR-chain without explicit parentheses caused the server to match emails
    based solely on FROM address, ignoring SUBJECT criteria.
    """
    addresses = [
        "TrackingUpdates@fedex.com",
        "fedexcanada@fedex.com",
        "noreply@fedex.com",
    ]
    subjects = [
        "Your package has been delivered",
        "Your packages have been delivered",
        "Your shipment was delivered",
    ]
    # Default behavior (is_yahoo=False)
    _utf8, search = build_search(addresses, "23-Apr-2026", subject=subjects)
    assert (
        search
        == 'OR OR FROM "TrackingUpdates@fedex.com" FROM "fedexcanada@fedex.com" FROM "noreply@fedex.com" OR OR SUBJECT "Your package has been delivered" SUBJECT "Your packages have been delivered" SUBJECT "Your shipment was delivered" SINCE 23-Apr-2026'
    )

    # Yahoo compatibility behavior (is_yahoo=True)
    _utf8, search_yahoo = build_search(
        addresses, "23-Apr-2026", subject=subjects, is_yahoo=True
    )
    # FROM group must be wrapped in parentheses
    assert (
        '(OR OR FROM "TrackingUpdates@fedex.com" FROM "fedexcanada@fedex.com" FROM "noreply@fedex.com")'
        in search_yahoo
    )
    # SUBJECT group must be wrapped in parentheses
    assert (
        '(OR OR SUBJECT "Your package has been delivered" SUBJECT "Your packages have been delivered" SUBJECT "Your shipment was delivered")'
        in search_yahoo
    )
    # Search must be wrapped in parens and include SINCE
    assert search_yahoo.startswith("((")
    assert "SINCE 23-Apr-2026)" in search_yahoo


@pytest.mark.asyncio
async def test_selectfolder_caching():
    """Test that selectfolder caches the selected folder and avoids redundant select calls."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"

    # Select same folder - should return True immediately without calling select
    res = await selectfolder(mock_account, "INBOX")
    assert res is True
    mock_account.select.assert_not_called()

    # Select different folder - should call select
    mock_account._current_folder = "INBOX"
    res = await selectfolder(mock_account, "Junk")
    assert res is True
    mock_account.select.assert_called_once_with("Junk")
    assert mock_account._current_folder == "Junk"


@pytest.mark.asyncio
async def test_email_search_multisearch():
    """Test email_search using ESEARCH (MULTISEARCH) capability."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "Junk"]
    mock_account.has_capability = MagicMock(return_value=True)

    # Mock execute return value for Command ESEARCH
    mock_res = MagicMock()
    mock_res.result = "OK"
    # ESEARCH response line with folder and range
    mock_res.lines = [
        b'* ESEARCH (TAG "1" MAILBOX "INBOX" UIDVALIDITY 123) UID ALL 1001:1003',
        b'* ESEARCH (TAG "1" MAILBOX "Junk" UIDVALIDITY 123) UID ALL 2001',
    ]

    mock_protocol = AsyncMock()
    mock_protocol.execute.return_value = mock_res
    mock_protocol.new_tag.return_value = "1"
    mock_protocol.loop = asyncio.get_running_loop()
    mock_account.protocol = mock_protocol

    result = await email_search(
        mock_account, ["test@example.com"], "25-Mar-2026", subject="Test"
    )

    assert result[0] == "OK"
    # UIDs should be parsed, expanded, and formatted as folder/uid
    expected_uids = [
        b"INBOX/1001",
        b"INBOX/1002",
        b"INBOX/1003",
        b"Junk/2001",
    ]
    assert result[1] == [b" ".join(expected_uids)]


@pytest.mark.asyncio
async def test_email_search_sequential_fallback():
    """Test email_search falling back to sequential searching when MULTISEARCH is absent."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "Junk"]
    mock_account.has_capability.return_value = False

    # Mock uid_search response for each folder
    mock_res1 = MagicMock(result="OK", lines=[b"1001 1002"])
    mock_res2 = MagicMock(result="OK", lines=[b"2001"])
    mock_account.uid_search.side_effect = [mock_res1, mock_res2]

    # Mock list/select calls in selectfolder
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()

    result = await email_search(
        mock_account, ["test@example.com"], "25-Mar-2026", subject="Test"
    )

    assert result[0] == "OK"
    expected_uids = [
        b"INBOX/1001",
        b"INBOX/1002",
        b"Junk/2001",
    ]
    assert result[1] == [b" ".join(expected_uids)]


@pytest.mark.asyncio
async def test_email_fetch_folder_prefix():
    """Test email_fetch with folder-prefixed UID."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"

    # Mock list/select/uid
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"RFC822", b"body"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch(mock_account, b"Junk/2001")
    assert result[0] == "OK"
    assert result[1] == [b"RFC822", b"body"]

    # Verify selectfolder was called for Junk and uid fetch executed
    mock_account.select.assert_called_once_with("Junk")
    mock_account.uid.assert_called_once_with("FETCH", "2001", "(RFC822)")


def test_folder_ref_roundtrip():
    """encode_folder_ref/decode_folder_ref round-trip any folder name.

    The encoded form must contain no whitespace and no '/', because
    composite folder/uid IDs are space-joined then .split() at several
    call sites and rsplit('/', 1) to recover the folder.
    """
    for folder in [
        "INBOX",
        "# - Projects",
        "0 - Pending Orders",
        "# - For Family",
        "50% discount codes",
        "a/b nested",
        "tab\tname",
        "Boîte aux lettres",
    ]:
        encoded = encode_folder_ref(folder)
        assert " " not in encoded
        assert "/" not in encoded
        assert "\t" not in encoded
        assert decode_folder_ref(encoded) == folder


@pytest.mark.asyncio
async def test_email_search_sequential_fallback_spaced_folder():
    """Folder names with spaces survive the space-join/.split() round-trip.

    Regression test: multi-folder composite IDs are returned space-joined
    (mimicking a raw IMAP SEARCH response) and later .split() by consumers —
    an unencoded 'folder with spaces/uid' shatters into garbage IDs.
    """
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "# - Projects"]
    mock_account.has_capability.return_value = False

    mock_res1 = MagicMock(result="OK", lines=[b"1001 1002"])
    mock_res2 = MagicMock(result="OK", lines=[b"55"])
    mock_account.uid_search.side_effect = [mock_res1, mock_res2]
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()

    result = await email_search(
        mock_account, ["test@example.com"], "25-Mar-2026", subject="Test"
    )

    assert result[0] == "OK"
    # The joined blob must re-split into exactly one ID per matched email.
    ids = result[1][0].split()
    assert ids == [b"INBOX/1001", b"INBOX/1002", b"%23%20-%20Projects/55"]
    # And each ID's folder component must decode back to the real name.
    folder, uid = ids[2].decode().rsplit("/", 1)
    assert decode_folder_ref(folder) == "# - Projects"
    assert uid == "55"


@pytest.mark.asyncio
async def test_email_search_multisearch_spaced_folder():
    """ESEARCH responses with spaced mailbox names produce encoded IDs."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "0 - Pending Orders"]
    mock_account.has_capability = MagicMock(return_value=True)

    mock_res = MagicMock()
    mock_res.result = "OK"
    mock_res.lines = [
        b'* ESEARCH (TAG "1" MAILBOX "0 - Pending Orders" UIDVALIDITY 123) UID ALL 2001',
    ]
    mock_protocol = AsyncMock()
    mock_protocol.execute.return_value = mock_res
    mock_protocol.new_tag.return_value = "1"
    mock_protocol.loop = asyncio.get_running_loop()
    mock_account.protocol = mock_protocol

    result = await email_search(
        mock_account, ["test@example.com"], "25-Mar-2026", subject="Test"
    )

    assert result[0] == "OK"
    assert result[1][0].split() == [b"0%20-%20Pending%20Orders/2001"]


@pytest.mark.asyncio
async def test_email_fetch_spaced_folder_selects_decoded_name():
    """email_fetch on an encoded composite ID selects the REAL folder name."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"RFC822", b"body"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch(mock_account, b"%23%20-%20Projects/55")

    assert result[0] == "OK"
    # selectfolder must receive the decoded name (then IMAP-quote it since
    # it contains spaces).
    mock_account.select.assert_called_once_with('"# - Projects"')
    mock_account.uid.assert_called_once_with("FETCH", "55", "(RFC822)")


@pytest.mark.asyncio
async def test_email_fetch_batch_spaced_folder_groups_decoded():
    """email_fetch_batch groups encoded IDs by their decoded folder."""
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"
    mock_account._current_folder = None
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"RFC822", b"body"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch_batch(
        mock_account, [b"%23%20-%20Projects/55", b"%23%20-%20Projects/56"]
    )

    assert result[0] == "OK"
    mock_account.select.assert_called_once_with('"# - Projects"')
    mock_account.uid.assert_called_once_with("FETCH", "55,56", "(RFC822)")


@pytest.mark.asyncio
async def test_email_fetch_headers_spaced_folder_selects_decoded_name():
    """email_fetch_headers on an encoded composite ID selects the REAL folder."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"Subject: hi", b")"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch_headers(mock_account, b"%23%20-%20Projects/55")

    assert result[0] == "OK"
    mock_account.select.assert_called_once_with('"# - Projects"')
    mock_account.uid.assert_called_once_with(
        "FETCH", "55", "(BODY[HEADER.FIELDS (SUBJECT)])"
    )


@pytest.mark.asyncio
async def test_email_fetch_text_spaced_folder_selects_decoded_name():
    """email_fetch_text on an encoded composite ID selects the REAL folder."""
    mock_account = AsyncMock()
    mock_account.host = "imap.gmail.com"
    mock_account._current_folder = "INBOX"
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"body text", b")"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch_text(mock_account, b"%23%20-%20Projects/55")

    assert result[0] == "OK"
    mock_account.select.assert_called_once_with('"# - Projects"')
    mock_account.uid.assert_called_once_with("FETCH", "55", "(BODY[1])")


@pytest.mark.asyncio
async def test_email_fetch_headers_folder_prefix():
    """Test email_fetch_headers with folder-prefixed UID."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"

    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"Subject: Hello"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch_headers(mock_account, b"Junk/2001")
    assert result[0] == "OK"
    assert result[1] == [b"Subject: Hello"]

    mock_account.select.assert_called_once_with("Junk")
    mock_account.uid.assert_called_once_with(
        "FETCH", "2001", "(BODY[HEADER.FIELDS (SUBJECT)])"
    )


@pytest.mark.asyncio
async def test_email_fetch_text_folder_prefix():
    """Test email_fetch_text with folder-prefixed UID."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"

    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()
    mock_res = MagicMock(result="OK", lines=[b"text body"])
    mock_account.uid.return_value = mock_res

    result = await email_fetch_text(mock_account, b"Junk/2001")
    assert result[0] == "OK"
    assert result[1] == [b"text body"]

    mock_account.select.assert_called_once_with("Junk")
    mock_account.uid.assert_called_once_with("FETCH", "2001", "(BODY[1])")


@pytest.mark.asyncio
async def test_email_fetch_batch_folder_prefix():
    """Test email_fetch_batch with folder-prefixed UIDs."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"

    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()

    # Mock fetch results for different folders
    mock_res1 = MagicMock(result="OK", lines=[b"body1"])
    mock_res2 = MagicMock(result="OK", lines=[b"body2"])
    mock_account.uid.side_effect = [mock_res1, mock_res2]

    uids = [b"INBOX/1001", b"Junk/2001"]
    result = await email_fetch_batch(mock_account, uids)

    assert result[0] == "OK"
    assert result[1] == [b"body1", b"body2"]

    # Verify folder switches and UID fetches
    # 1001 should fetch in INBOX, 2001 in Junk
    assert (
        mock_account.select.call_count == 1
    )  # selectfolder called only for Junk because _current_folder was already INBOX
    mock_account.select.assert_called_once_with("Junk")


@pytest.mark.asyncio
async def test_esearch_parser_variants():
    """Test _parse_esearch_line with variations in spacing, order, and quoted/unquoted folder names."""
    # Test mailbox unquoted
    line_unquoted = (
        b'* ESEARCH (TAG "1" MAILBOX INBOX UIDVALIDITY 123) UID ALL 1001:1002'
    )
    res = _parse_esearch_line(line_unquoted)
    assert res == [b"INBOX/1001", b"INBOX/1002"]

    # Test mailbox order changed (UIDVALIDITY before MAILBOX)
    line_ordered = b'* ESEARCH (TAG "1" UIDVALIDITY 123 MAILBOX "Junk") UID ALL 2001'
    res = _parse_esearch_line(line_ordered)
    assert res == [b"Junk/2001"]

    # Test variation in spacing
    line_spacing = b'* ESEARCH  ( TAG  "1"  MAILBOX  "Inbox"  UIDVALIDITY  123 )  UID  ALL  3001,3003'
    res = _parse_esearch_line(line_spacing)
    assert res == [b"Inbox/3001", b"Inbox/3003"]


@pytest.mark.asyncio
async def test_esearch_parser_malformed():
    """Test _parse_esearch_line with malformed/missing fields fails gracefully returning empty list."""
    # Missing parenthesis
    assert _parse_esearch_line(b'* ESEARCH TAG "1" MAILBOX "INBOX" UID ALL 1001') == []

    # Missing MAILBOX
    assert (
        _parse_esearch_line(b'* ESEARCH (TAG "1" UIDVALIDITY 123) UID ALL 1001') == []
    )

    # Missing UID ALL
    assert (
        _parse_esearch_line(b'* ESEARCH (TAG "1" MAILBOX "INBOX" UIDVALIDITY 123) 1001')
        == []
    )


@pytest.mark.asyncio
async def test_email_search_sequential_fallback_no_capping(caplog):
    """Test sequential fallback has no limit and searches all configured folders without warning logging."""
    caplog.set_level("WARNING")
    mock_account = AsyncMock()
    # 12 folders configured
    mock_account._folders = [f"Folder{i}" for i in range(12)]
    mock_account.has_capability.return_value = False

    # Mock uid_search response for each folder
    mock_res = MagicMock(result="OK", lines=[b"1001"])
    mock_account.uid_search.return_value = mock_res
    mock_account.select.return_value = MagicMock()

    result = await email_search(
        mock_account, ["test@example.com"], "25-Mar-2026", subject="Test"
    )

    assert result[0] == "OK"
    # Select should be called for all 12 folders (properly quoted)
    assert mock_account.select.call_count == 12
    assert (
        "Configured folders count (12) exceeds the sequential search limit"
        not in caplog.text
    )


@pytest.mark.asyncio
async def test_esearch_parser_edge_cases():
    """Test _parse_esearch_line edge cases to increase coverage."""
    # Line 198: empty part
    assert _parse_esearch_line(
        b'* ESEARCH (TAG "1" MAILBOX INBOX UIDVALIDITY 123) UID ALL ,1001,,1002'
    ) == [
        b"INBOX/1001",
        b"INBOX/1002",
    ]

    # Line 206: reversed range (start > end)
    assert _parse_esearch_line(
        b'* ESEARCH (TAG "1" MAILBOX INBOX UIDVALIDITY 123) UID ALL 1002:1001'
    ) == [
        b"INBOX/1001",
        b"INBOX/1002",
    ]

    # Line 207-208: ValueError in range splitting
    assert (
        _parse_esearch_line(
            b'* ESEARCH (TAG "1" MAILBOX INBOX UIDVALIDITY 123) UID ALL 100a:1002'
        )
        == []
    )


@pytest.mark.asyncio
async def test_execute_single_search_single_folder():
    """Test _execute_single_search when account has <= 1 folders."""
    # Single folder case
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX"]

    # Search succeeds with result OK and lines
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1001 1002"])
    res = await _execute_single_search(mock_account, "ALL")
    assert res == [b"1001", b"1002"]

    # Search returns empty result
    mock_account.search.return_value = MagicMock(result="OK", lines=[None])
    res = await _execute_single_search(mock_account, "ALL")
    assert res == []

    # Search fails (result not OK)
    mock_account.search.return_value = MagicMock(result="BAD", lines=[])
    res = await _execute_single_search(mock_account, "ALL")
    assert res == []


@pytest.mark.asyncio
async def test_execute_single_search_capability_exception():
    """Test has_capability raising an exception inside _execute_single_search."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "Junk"]
    mock_account.has_capability = MagicMock(side_effect=Exception("Capability error"))

    # In case of exception, it should fallback to sequential search
    mock_res = MagicMock(result="OK", lines=[b"1001"])
    mock_account.uid_search.return_value = mock_res
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()

    res = await _execute_single_search(mock_account, "ALL")
    # Should perform sequential fallback
    assert len(res) == 2  # one for each folder


@pytest.mark.asyncio
async def test_execute_single_search_esearch_failure():
    """Test ESEARCH command failure raising AioImapException/OSError."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "Junk"]
    mock_account.has_capability = MagicMock(return_value=True)

    # Mock protocol execution to raise AioImapException
    mock_account.protocol.execute.side_effect = AioImapException("ESEARCH failed")

    res = await _execute_single_search(mock_account, "ALL")
    assert res == []


@pytest.mark.asyncio
async def test_execute_single_search_sequential_failures():
    """Test sequential fallback failures (selectfolder failure and uid_search failure)."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "Junk"]
    mock_account.has_capability.return_value = False

    mock_account.list.return_value = MagicMock()

    # Case 1: selectfolder returns False for INBOX, Junk works
    # We patch selectfolder to return False for INBOX and True for Junk
    with patch(
        "custom_components.mail_and_packages.utils.imap.selectfolder",
        side_effect=lambda acc, f: f != "INBOX",
    ):
        mock_res = MagicMock(result="OK", lines=[b"1001"])
        mock_account.uid_search.return_value = mock_res
        res = await _execute_single_search(mock_account, "ALL")
        assert res == [b"Junk/1001"]

    # Case 2: selectfolder succeeds, but uid_search raises OSError
    mock_account.select.return_value = MagicMock()
    mock_account.uid_search.side_effect = OSError("Socket error")
    with patch(
        "custom_components.mail_and_packages.utils.imap.selectfolder",
        return_value=True,
    ):
        res = await _execute_single_search(mock_account, "ALL")
        assert res == []


@pytest.mark.asyncio
async def test_email_search_batch_and_exceptions():
    """Test email_search batch subjects and search exceptions."""
    mock_account = AsyncMock()
    mock_account._folders = ["INBOX", "Junk"]

    # Case 1: _execute_single_search raises OSError (single search)
    with patch(
        "custom_components.mail_and_packages.utils.imap._execute_single_search",
        side_effect=OSError("Search error"),
    ):
        res = await email_search(
            mock_account, ["test@example.com"], "25-Mar-2026", subject="Test"
        )
        assert res == ("BAD", "Search error")

    # Case 2: Batching subjects (multiple subjects)
    subjects = [f"Sub{i}" for i in range(2)]
    # Mock successful returns for both batches
    with patch(
        "custom_components.mail_and_packages.utils.imap._execute_single_search",
        side_effect=[[b"INBOX/1001"], [b"INBOX/1002"]],
    ) as mock_single_search:
        res = await email_search(
            mock_account, ["test@example.com"], "25-Mar-2026", subject=subjects
        )
        assert res[0] == "OK"
        assert res[1] == [b"INBOX/1001 INBOX/1002"]
        assert mock_single_search.call_count == 2

    # Case 3: Batching subjects and one batch raises OSError
    with patch(
        "custom_components.mail_and_packages.utils.imap._execute_single_search",
        side_effect=[[b"INBOX/1001"], OSError("Batch error")],
    ):
        res = await email_search(
            mock_account, ["test@example.com"], "25-Mar-2026", subject=subjects
        )
        assert res[0] == "OK"
        # The failed batch is ignored, returns only first batch result
        assert res[1] == [b"INBOX/1001"]

    # Case 4: All multi-folder search batches fail
    with patch(
        "custom_components.mail_and_packages.utils.imap._execute_single_search",
        side_effect=OSError("All batches failed"),
    ):
        res = await email_search(
            mock_account, ["test@example.com"], "25-Mar-2026", subject=subjects
        )
        assert res == ("BAD", "All search batches failed")


@pytest.mark.asyncio
async def test_email_fetch_failures():
    """Test fetch helpers error handling when account.uid raises OSError."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()

    mock_account.uid.side_effect = OSError("Fetch failed")

    # email_fetch failure
    res = await email_fetch(mock_account, b"Junk/1001")
    assert res == ("BAD", "Fetch failed")

    # email_fetch_headers failure
    res = await email_fetch_headers(mock_account, b"Junk/1001")
    assert res == ("BAD", "Fetch failed")

    # email_fetch_text failure
    res = await email_fetch_text(mock_account, b"Junk/1001")
    assert res == ("BAD", "Fetch failed")


@pytest.mark.asyncio
async def test_email_fetch_batch_edge_cases():
    """Test email_fetch_batch edge cases including non-prefixed UIDs and errors."""
    mock_account = AsyncMock()
    mock_account._current_folder = "INBOX"
    mock_account.list.return_value = MagicMock()
    mock_account.select.return_value = MagicMock()

    # Case 1: Mixed prefixed and non-prefixed UIDs (covers line 471)
    # Grouping should assign None folder for "1001", and "Junk" for "Junk/2001"
    mock_res1 = MagicMock(result="OK", lines=[b"body1"])
    mock_res2 = MagicMock(result="OK", lines=[b"body2"])
    mock_account.uid.side_effect = [mock_res1, mock_res2]

    uids = [b"1001", b"Junk/2001"]
    res = await email_fetch_batch(mock_account, uids)
    assert res[0] == "OK"
    assert res[1] == [b"body1", b"body2"]

    # Case 2: One batch fetch returns a non-OK status (covers line 485)
    mock_res_bad = MagicMock(result="NO", lines=[b"error"])
    mock_account.uid.side_effect = [mock_res_bad]

    uids = [b"Junk/2001"]
    res = await email_fetch_batch(mock_account, uids)
    assert res[0] == "NO"

    # Case 3: Batch fetch raises AioImapException (covers lines 487-489)
    mock_account.uid.side_effect = AioImapException("Batch command failed")

    res = await email_fetch_batch(mock_account, uids)
    assert res == ("BAD", "Batch command failed")


def test_imap_utf7_encoding_decoding():
    """Test IMAP modified UTF-7 encoding and decoding helpers."""
    # Standard ASCII and simple special chars
    assert encode_imap_utf7("INBOX") == "INBOX"
    assert decode_imap_utf7("INBOX") == "INBOX"

    # Ampersand (escaped to &-)
    assert encode_imap_utf7("C&A") == "C&-A"
    assert decode_imap_utf7("C&-A") == "C&A"

    assert encode_imap_utf7("H&M") == "H&-M"
    assert decode_imap_utf7("H&-M") == "H&M"

    # Unicode / non-ASCII characters
    assert encode_imap_utf7("Testé") == "Test&AOk-"
    assert decode_imap_utf7("Test&AOk-") == "Testé"

    # Multiple unicode portions and ampersands mixed
    assert encode_imap_utf7("é&à") == "&AOk-&-&AOA-"
    assert decode_imap_utf7("&AOk-&-&AOA-") == "é&à"

    # Malformed inputs decode fallback
    assert decode_imap_utf7("&invalid") == "&invalid"
    assert decode_imap_utf7("&invalid-") == "&invalid-"

    # Unicode followed by ASCII to flush unicode buffer
    assert encode_imap_utf7("éabc") == "&AOk-abc"

    # quote_folder on already quoted folder
    assert quote_folder('"INBOX"') == '"INBOX"'

    # quote_folder on atom-safe unquoted folder
    assert quote_folder("INBOX") == "INBOX"

    # quote_folder on non-atom folder
    assert quote_folder("INBOX/Online Shops") == '"INBOX/Online Shops"'


def test_parse_search_response():
    """Test parse_search_response helper function with various inputs."""
    # Standard server response with search results
    assert parse_search_response([b"SEARCH 1 2 3"]) == [b"1", b"2", b"3"]
    # Server response with multiple lines
    assert parse_search_response([b"SEARCH 1 2", b"SEARCH 3 4"]) == [
        b"1",
        b"2",
        b"3",
        b"4",
    ]
    # Server response with no results
    assert parse_search_response([b"SEARCH"]) == []
    # Server response with status text (tagged OK response)
    assert parse_search_response([b"SEARCH completed (took 237 ms)"]) == []
    # Mocked test inputs (raw sequence numbers)
    assert parse_search_response([b"1001 1002"]) == [b"1001", b"1002"]
    # Non-search untagged response lines (should be ignored)
    assert parse_search_response([b"23 EXISTS", b"SEARCH 5 6"]) == [b"5", b"6"]
    # Empty lists or empty lines
    assert parse_search_response([]) == []
    assert parse_search_response([b"", None, b"   "]) == []


@pytest.mark.asyncio
async def test_login_timeout_error():
    """Test login propagates TimeoutError."""
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.login.side_effect = TimeoutError()
        mock_acc.protocol.state = NONAUTH
        mock_imap_ssl.return_value = mock_acc
        with pytest.raises(TimeoutError):
            await login(mock_hass, "host", 993, "user", "pass", "SSL")


@pytest.mark.asyncio
async def test_selectfolder_timeout_error():
    """Test selectfolder propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._current_folder = None
    mock_imap.select.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await selectfolder(mock_imap, "Junk")


@pytest.mark.asyncio
async def test_execute_single_search_esearch_timeout_error():
    """Test _execute_single_search with ESEARCH path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX", "Junk"]
    mock_imap.has_capability = MagicMock(return_value=True)
    mock_imap.protocol.execute.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await _execute_single_search(mock_imap, "SEARCH_QUERY")


@pytest.mark.asyncio
async def test_execute_single_search_sequential_timeout_error():
    """Test _execute_single_search with sequential path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX", "Junk"]
    mock_imap._current_folder = None
    mock_imap.has_capability.return_value = False
    mock_imap.select.return_value = MagicMock()
    mock_imap.uid_search.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await _execute_single_search(mock_imap, "SEARCH_QUERY")


@pytest.mark.asyncio
async def test_email_search_timeout_error():
    """Test email_search standard path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX"]
    mock_imap.search.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_search(mock_imap, ["test@example.com"], "25-Mar-2026")


@pytest.mark.asyncio
async def test_email_search_batch_timeout_error():
    """Test email_search batched subjects path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX"]
    mock_imap.search.side_effect = TimeoutError()
    subjects = [f"Subj {i}" for i in range(11)]
    with pytest.raises(TimeoutError):
        await email_search(
            mock_imap, ["test@example.com"], "25-Mar-2026", subject=subjects
        )


@pytest.mark.asyncio
async def test_email_search_multifolders_timeout_error():
    """Test email_search multi-folder path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX", "Junk"]
    with (
        patch(
            "custom_components.mail_and_packages.utils.imap._execute_single_search",
            side_effect=TimeoutError(),
        ),
        pytest.raises(TimeoutError),
    ):
        await email_search(mock_imap, ["test@example.com"], "25-Mar-2026")


@pytest.mark.asyncio
async def test_email_search_multifolders_batch_timeout_error():
    """Test email_search multi-folder batched subjects path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX", "Junk"]
    subjects = [f"Subj {i}" for i in range(11)]
    with (
        patch(
            "custom_components.mail_and_packages.utils.imap._execute_single_search",
            side_effect=TimeoutError(),
        ),
        pytest.raises(TimeoutError),
    ):
        await email_search(
            mock_imap, ["test@example.com"], "25-Mar-2026", subject=subjects
        )


@pytest.mark.asyncio
async def test_email_fetch_prefixed_timeout_error():
    """Test email_fetch folder-prefixed path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._current_folder = "INBOX"
    mock_imap.select.return_value = MagicMock()
    mock_imap.uid.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch(mock_imap, b"Junk/1001")


@pytest.mark.asyncio
async def test_email_fetch_timeout_error():
    """Test email_fetch standard path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch(mock_imap, b"1001")


@pytest.mark.asyncio
async def test_email_fetch_headers_prefixed_timeout_error():
    """Test email_fetch_headers folder-prefixed path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._current_folder = "INBOX"
    mock_imap.select.return_value = MagicMock()
    mock_imap.uid.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch_headers(mock_imap, b"Junk/1001")


@pytest.mark.asyncio
async def test_email_fetch_headers_timeout_error():
    """Test email_fetch_headers standard path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch_headers(mock_imap, b"1001")


@pytest.mark.asyncio
async def test_email_fetch_text_prefixed_timeout_error():
    """Test email_fetch_text folder-prefixed path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._current_folder = "INBOX"
    mock_imap.select.return_value = MagicMock()
    mock_imap.uid.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch_text(mock_imap, b"Junk/1001")


@pytest.mark.asyncio
async def test_email_fetch_text_timeout_error():
    """Test email_fetch_text standard path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch_text(mock_imap, b"1001")


@pytest.mark.asyncio
async def test_email_fetch_batch_timeout_error():
    """Test email_fetch_batch standard path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap.fetch.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch_batch(mock_imap, [b"1001", b"1002"])


@pytest.mark.asyncio
async def test_email_fetch_batch_prefixed_timeout_error():
    """Test email_fetch_batch folder-prefixed path propagates TimeoutError."""
    mock_imap = AsyncMock()
    mock_imap._current_folder = "INBOX"
    mock_imap.select.return_value = MagicMock()
    mock_imap.uid.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await email_fetch_batch(mock_imap, [b"Junk/1001", b"Junk/1002"])


@pytest.mark.asyncio
async def test_email_search_body_threshold():
    """Test that email_search only does server-side body search if <= 2 body patterns are specified."""
    mock_imap = AsyncMock()
    mock_imap._folders = ["INBOX"]
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])

    # 1 body pattern -> should include BODY in search query
    await email_search(mock_imap, ["test@example.com"], "25-Mar-2026", body="Pattern1")
    search_query = mock_imap.search.call_args.args[0]
    assert 'BODY "Pattern1"' in search_query

    # 2 body patterns -> should include BODY in search query
    mock_imap.search.reset_mock()
    await email_search(
        mock_imap, ["test@example.com"], "25-Mar-2026", body=["Pattern1", "Pattern2"]
    )
    search_query = mock_imap.search.call_args.args[0]
    assert 'BODY "Pattern1"' in search_query
    assert 'BODY "Pattern2"' in search_query

    # 3 body patterns -> should NOT include BODY in search query
    mock_imap.search.reset_mock()
    await email_search(
        mock_imap,
        ["test@example.com"],
        "25-Mar-2026",
        body=["Pattern1", "Pattern2", "Pattern3"],
    )
    search_query = mock_imap.search.call_args.args[0]
    assert "BODY" not in search_query

    # Regex body pattern -> should NOT include BODY in search query
    mock_imap.search.reset_mock()
    await email_search(
        mock_imap,
        ["test@example.com"],
        "25-Mar-2026",
        body=[r"\sYou have (\d) piece|pieces of mail\s"],
    )
    search_query = mock_imap.search.call_args.args[0]
    assert "BODY" not in search_query


@pytest.mark.asyncio
async def test_login_oauth_failed(caplog):
    """Test login with OAuth2 failure path."""
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = NONAUTH

        mock_res = MagicMock()
        mock_res.result = "NO"
        mock_res.lines = [b"AUTHENTICATIONFAILED"]

        async def side_effect(*args, **kwargs):
            return mock_res

        mock_acc.xoauth2.side_effect = side_effect
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(InvalidAuth):
            await login(
                mock_hass,
                "host",
                993,
                "user",
                None,
                "SSL",
                oauth_token="token",
            )
        assert (
            "OAuth login failed. Result: NO, Lines: [b'AUTHENTICATIONFAILED']"
            in caplog.text
        )


@pytest.mark.asyncio
async def test_email_search_yahoo_detection():
    """Test that email_search correctly detects Yahoo/AOL hosts."""
    mock_imap = AsyncMock()
    mock_imap.host = "imap.mail.yahoo.com"
    mock_imap._folders = ["INBOX"]
    mock_imap.search.return_value = MagicMock(result="OK", lines=[b"1"])

    # For Yahoo hosts, build_search gets called with is_yahoo=True
    # and subject/body searches have specific Yahoo-compatible structure.
    await email_search(mock_imap, ["test@example.com"], "25-Mar-2026", subject="Test")
    search_query = mock_imap.search.call_args.args[0]
    # In Yahoo mode, the search query is enclosed in outer parens: (FROM ... SUBJECT ... SINCE ...)
    assert search_query.startswith("(") and search_query.endswith(")")

    # Non-Yahoo host does NOT enclose the query in outer parens
    mock_imap.host = "imap.gmail.com"
    mock_imap.search.reset_mock()
    await email_search(mock_imap, ["test@example.com"], "25-Mar-2026", subject="Test")
    non_yahoo_query = mock_imap.search.call_args.args[0]
    assert not non_yahoo_query.startswith("(")


@pytest.mark.asyncio
async def test_login_oauth_timeout(caplog):
    """Test login with OAuth2 timeout path."""
    mock_hass = _mock_hass()
    with patch(
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
    ) as mock_imap_ssl:
        mock_acc = AsyncMock()
        mock_acc.protocol.state = NONAUTH
        mock_acc.xoauth2.side_effect = TimeoutError("Timeout during xoauth2")
        mock_imap_ssl.return_value = mock_acc

        with pytest.raises(TimeoutError):
            await login(
                mock_hass,
                "host",
                993,
                "user",
                None,
                "SSL",
                oauth_token="token",
            )
        assert "OAuth authentication timed out for user" in caplog.text
