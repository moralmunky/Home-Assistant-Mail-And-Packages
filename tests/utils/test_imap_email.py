"""Tests for IMAP and email utilities."""

import asyncio
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
    decode_imap_utf7,
    email_fetch,
    email_fetch_batch,
    email_fetch_headers,
    email_fetch_text,
    email_search,
    encode_imap_utf7,
    login,
    logout,
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


@pytest.mark.asyncio
async def test_login_success():
    """Test login success path."""
    mock_hass = MagicMock()
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
    mock_hass = MagicMock()
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
    mock_hass = MagicMock()
    with (
        patch(
            "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
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
    mock_hass = MagicMock()
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
    mock_hass = MagicMock()
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
    mock_acc.select.assert_called_once_with('"INBOX"')


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


def test_build_search_single_header():
    """Test build_search with header mode matches both forwarded (HEADER) and direct (FROM)."""
    utf8, search = build_search(
        ["mcinfo@ups.com"], "25-Mar-2026", header="X-SimpleLogin-Original-From"
    )
    assert 'HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com"' in search
    assert 'FROM "mcinfo@ups.com"' in search
    assert search.startswith("(OR HEADER")


def test_build_search_multiple_header():
    """Test build_search with header mode for multiple addresses uses OR pairs."""
    utf8, search = build_search(
        ["mcinfo@ups.com", "pkginfo@ups.com"],
        "25-Mar-2026",
        header="X-SimpleLogin-Original-From",
    )
    assert (
        'OR HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com" FROM "mcinfo@ups.com"'
        in search
    )
    assert (
        'OR HEADER "X-SimpleLogin-Original-From" "pkginfo@ups.com" FROM "pkginfo@ups.com"'
        in search
    )


def test_build_search_header_with_subject():
    """Test build_search with header mode includes HEADER, FROM, and SUBJECT criteria."""
    utf8, search = build_search(
        ["mcinfo@ups.com"],
        "25-Mar-2026",
        subject="UPS Ship Notification",
        header="X-SimpleLogin-Original-From",
    )
    assert 'HEADER "X-SimpleLogin-Original-From" "mcinfo@ups.com"' in search
    assert 'FROM "mcinfo@ups.com"' in search
    assert 'SUBJECT "UPS Ship Notification"' in search


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
        "custom_components.mail_and_packages.utils.imap.IMAP4_SSL",
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
async def test_logout_cancelled(caplog):
    """Test logout cancellation handling."""
    mock_acc = AsyncMock()
    mock_acc.logout.side_effect = asyncio.CancelledError()
    caplog.set_level("DEBUG")

    await logout(mock_acc)
    assert "Error logging out of IMAP Server" in caplog.text


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
    # "é" is non-ASCII and will be stripped to an empty string
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=["é"])
    assert "SUBJECT" not in search


def test_build_search_multi_subject():
    """Test build_search with multiple subjects to verify OR prefix."""
    # Covers lines 116-117
    subjects = ["One", "Two", "Three"]
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject=subjects)
    assert '(OR OR SUBJECT "One" SUBJECT "Two" SUBJECT "Three")' in search


def test_build_search_single_addr_with_subject():
    """Test build_search with single address and subject."""
    # Covers line 126
    utf8, search = build_search(["test@example.com"], "25-Mar-2026", subject="Test")
    assert '(FROM "test@example.com" SUBJECT "Test" SINCE 25-Mar-2026)' in search


@pytest.mark.asyncio
async def test_email_search_batching():
    """Test email_search batching logic for > 10 subjects."""
    # Covers lines 163-176
    mock_acc = AsyncMock()

    # Mocking two batches: first with IDs 1 2, second with ID 3
    res1 = MagicMock()
    res1.result = "OK"
    res1.lines = [b"1 2"]

    res2 = MagicMock()
    res2.result = "OK"
    res2.lines = [b"3"]

    mock_acc.search.side_effect = [res1, res2]

    # 11 subjects will trigger 2 batches (10 + 1)
    subjects = [f"Sub{i}" for i in range(11)]
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

    subjects = [f"Sub{i}" for i in range(11)]
    result = await email_search(
        mock_acc, ["test@example.com"], "25-Mar-2026", subject=subjects
    )

    assert result[0] == "OK"
    assert result[1] == [b"1 2"]


@pytest.mark.asyncio
async def test_email_search_batching_error(caplog):
    """Test email_search batching with an error in one batch."""
    # Covers lines 171-172
    mock_acc = AsyncMock()
    caplog.set_level("ERROR")

    res1 = MagicMock()
    res1.result = "OK"
    res1.lines = [b"1 2"]

    mock_acc.search.side_effect = [res1, AioImapException("Batch failed")]

    subjects = [f"Sub{i}" for i in range(11)]
    result = await email_search(
        mock_acc, ["test@example.com"], "25-Mar-2026", subject=subjects
    )

    assert result[0] == "OK"
    assert result[1] == [b"1 2"]
    assert "Error searching emails batch: Batch failed" in caplog.text


def test_build_search_multi_addr_multi_subject_parentheses():
    """Test that multi-address AND multi-subject queries use explicit parentheses.

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
    _utf8, search = build_search(addresses, "23-Apr-2026", subject=subjects)

    # FROM group appears in search
    assert (
        'OR OR FROM "TrackingUpdates@fedex.com" FROM "fedexcanada@fedex.com" FROM "noreply@fedex.com"'
        in search
    )
    # SUBJECT group must be wrapped in parentheses
    assert (
        '(OR OR SUBJECT "Your package has been delivered" SUBJECT "Your packages have been delivered" SUBJECT "Your shipment was delivered")'
        in search
    )
    # Search must be wrapped in parens and include SINCE
    assert search.startswith("(")
    assert "SINCE 23-Apr-2026)" in search


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
    mock_account.select.assert_called_once_with('"Junk"')
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
    mock_account.select.assert_called_once_with('"Junk"')
    mock_account.uid.assert_called_once_with("FETCH", "2001", "(RFC822)")


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

    mock_account.select.assert_called_once_with('"Junk"')
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

    mock_account.select.assert_called_once_with('"Junk"')
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
    mock_account.select.assert_called_once_with('"Junk"')


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

    # Case 2: Batching subjects (more than 10 subjects)
    subjects = [f"Sub{i}" for i in range(12)]
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
