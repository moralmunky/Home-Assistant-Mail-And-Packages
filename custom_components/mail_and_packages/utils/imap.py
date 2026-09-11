"""IMAP connection and search utilities for Mail and Packages."""

import asyncio
import logging
import re
import ssl as ssl_lib

import aioimaplib
from aioimaplib import (
    AUTH,
    IMAP4,
    IMAP4_SSL,
    NONAUTH,
    SELECTED,
    AioImapException,
    Cmd,
    Exec,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.mail_and_packages.const import DEFAULT_IMAP_TIMEOUT

from .imap_fetch import (
    _execute_uid_fetch,
    _fetch_batch_multi_folder,
    _fetch_batch_single_folder,
    _group_nums_by_folder,
    email_fetch,
    email_fetch_batch,
    email_fetch_headers,
    email_fetch_text,
    selectfolder,
)
from .imap_query import (
    SearchBatchParams,
    _build_address_clause,
    _build_body_clause,
    _build_subject_clause,
    _parse_esearch_line,
    build_search,
    clean_search_string,
    parse_search_response,
)
from .imap_search import (
    IMAP_ADDRESS_BATCH_SIZE,
    IMAP_SUBJECT_BATCH_SIZE_DEFAULT,
    IMAP_SUBJECT_BATCH_SIZE_EXTENDED,
    _email_search_multi_folder,
    _email_search_single_folder,
    _execute_multisearch,
    _execute_sequential_search,
    _execute_single_search,
    _execute_uid_search,
    _get_subject_batch_size,
    _search_all_batches_sequential,
    _supports_multisearch,
    get_subject_batch_size,
)
from .imap_utf7 import (
    _is_imap_atom,
    decode_folder_ref,
    decode_imap_utf7,
    encode_folder_ref,
    encode_imap_utf7,
    quote_folder,
)

_LOGGER = logging.getLogger(__name__)

# Register ESEARCH command if not already present in aioimaplib
if "ESEARCH" not in aioimaplib.Commands:
    aioimaplib.Commands["ESEARCH"] = Cmd("ESEARCH", (AUTH, SELECTED), Exec.is_async)


def _build_ssl_context(verify: bool) -> ssl_lib.SSLContext:
    """Build a new SSLContext for a single IMAP connection.

    The context must not be shared between connections. aioimaplib holds it for
    the lifetime of the transport, and a context that has already served a
    closed connection never completes the next handshake, so the server
    greeting never arrives and the caller waits forever.
    """
    context = ssl_lib.create_default_context()
    if not verify:
        context.check_hostname = False
        context.verify_mode = ssl_lib.CERT_NONE
    return context


class InvalidAuth(HomeAssistantError):
    """Raise exception for invalid credentials."""


async def login(
    hass: HomeAssistant,
    host: str,
    port: int,
    user: str,
    pwd: str,
    security: str,
    verify: bool = True,
    oauth_token: str | None = None,
    timeout: float = DEFAULT_IMAP_TIMEOUT,
) -> IMAP4_SSL | IMAP4:
    """Login to IMAP server asynchronously.

    Supports both password and OAuth2 (XOAUTH2) authentication.
    If oauth_token is provided, uses XOAUTH2 SASL mechanism.
    Otherwise falls back to standard LOGIN command.
    """
    ssl_context = await hass.async_add_executor_job(_build_ssl_context, verify)
    if security == "SSL":
        account = IMAP4_SSL(
            host=host, port=port, ssl_context=ssl_context, timeout=timeout
        )
    else:
        account = IMAP4(host=host, port=port, timeout=timeout)

    await asyncio.wait_for(account.wait_hello_from_server(), timeout=min(timeout, 15.0))

    if account.protocol.state == NONAUTH:
        try:
            if oauth_token:
                try:
                    res = await asyncio.wait_for(
                        account.xoauth2(user, oauth_token),
                        timeout=min(timeout, 15.0),
                    )
                    if account.protocol.state not in {AUTH, SELECTED}:
                        _LOGGER.error(
                            "OAuth login failed. Result: %s, Lines: %s",
                            getattr(res, "result", None),
                            getattr(res, "lines", None),
                        )
                except TimeoutError:
                    _LOGGER.warning("OAuth authentication timed out for %s", user)
                    raise
            else:
                await account.login(user, pwd)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error logging in to IMAP Server: %s", err)
            raise

    if account.protocol.state not in {AUTH, SELECTED}:
        _LOGGER.error(
            "Error logging in to IMAP Server. State: %s", account.protocol.state
        )
        raise InvalidAuth
    return account


async def email_search(
    account: IMAP4_SSL,
    address: list,
    date: str,
    subject: str | list[str] = "",
    body: str | list[str] = "",
    header: str = "",
) -> tuple:
    """Search emails with from/header, subject, and date asynchronously.

    Always uses charset=None to avoid sending CHARSET in the IMAP SEARCH
    command, ensuring compatibility with servers like Microsoft Exchange
    that only support US-ASCII.

    When `header` is provided, searches via HEADER criterion instead of FROM,
    matching the original sender in forwarding-service headers.

    If multiple subjects are provided, they are searched in batches of 10
    to keep the search query length safe.
    """
    folders = getattr(account, "_folders", ["INBOX"])
    is_yahoo = False
    is_exchange = getattr(account, "_exchange_mode", None) is True
    if hasattr(account, "host") and isinstance(account.host, str):
        host_lower = account.host.lower()
        is_yahoo = "yahoo" in host_lower or "aol" in host_lower
        if any(h in host_lower for h in ("outlook", "office365")):
            is_exchange = True

    body_search = body
    if isinstance(body, list):
        body_search = list(dict.fromkeys(b for b in body if b))
        if len(body_search) == 1:
            body_search = body_search[0]

    if isinstance(body_search, str) and (
        len(body_search.split()) > 2
        or any(re.search(r"[()|\[\]?*+^$\\]", b) for b in [body_search])
    ):
        body_search = ""
    elif isinstance(body_search, list):
        bodies = [b for part in body_search for b in part.split()]
        if len(bodies) > 2 or any(re.search(r"[()|\[\]?*+^$\\]", b) for b in bodies):
            body_search = ""

    subject_search = subject
    if isinstance(subject, list):
        cleaned_subjects = [clean_search_string(s) for s in subject]
        subject_search = list(dict.fromkeys(s for s in cleaned_subjects if s))

    address_batches = (
        [
            address[i : i + IMAP_ADDRESS_BATCH_SIZE]
            for i in range(0, len(address), IMAP_ADDRESS_BATCH_SIZE)
        ]
        if isinstance(address, list) and len(address) > IMAP_ADDRESS_BATCH_SIZE
        else [address]
    )

    subject_batch_size = _get_subject_batch_size(account)
    subject_batches = (
        [
            subject_search[i : i + subject_batch_size]
            for i in range(0, len(subject_search), subject_batch_size)
        ]
        if isinstance(subject_search, list) and len(subject_search) > subject_batch_size
        else [subject_search]
    )

    is_batched = len(address_batches) > 1 or len(subject_batches) > 1

    params = SearchBatchParams(
        address_batches=address_batches,
        subject_batches=subject_batches,
        date=date,
        body_search=body_search,
        header=header,
        is_yahoo=is_yahoo,
        is_exchange=is_exchange,
    )

    search_raw = (
        ("", "")
        if is_batched
        else build_search(
            address,
            date,
            subject_search,
            body_search,
            header,
            is_yahoo=is_yahoo,
            is_exchange=is_exchange,
        )
    )

    if len(folders) <= 1:
        return await _email_search_single_folder(
            account,
            params,
            search_raw,
            is_batched,
        )

    return await _email_search_multi_folder(
        account,
        params,
        search_raw,
        is_batched,
    )


async def logout(account: IMAP4_SSL | IMAP4) -> None:
    """Logout from IMAP server asynchronously."""
    try:
        await account.logout()
    except asyncio.CancelledError:
        # Runs from a finally during timeout teardown; suppressing cancellation
        # here leaves the coordinator wedged until Home Assistant restarts.
        raise
    except (TimeoutError, AioImapException, OSError) as err:
        _LOGGER.debug("Error logging out of IMAP Server: %s", err)


__all__ = [
    "IMAP_ADDRESS_BATCH_SIZE",
    "IMAP_SUBJECT_BATCH_SIZE_DEFAULT",
    "IMAP_SUBJECT_BATCH_SIZE_EXTENDED",
    "InvalidAuth",
    "SearchBatchParams",
    "_build_address_clause",
    "_build_body_clause",
    "_build_ssl_context",
    "_build_subject_clause",
    "_email_search_multi_folder",
    "_email_search_single_folder",
    "_execute_multisearch",
    "_execute_sequential_search",
    "_execute_single_search",
    "_execute_uid_fetch",
    "_execute_uid_search",
    "_fetch_batch_multi_folder",
    "_fetch_batch_single_folder",
    "_get_subject_batch_size",
    "_group_nums_by_folder",
    "_is_imap_atom",
    "_parse_esearch_line",
    "_search_all_batches_sequential",
    "_supports_multisearch",
    "build_search",
    "clean_search_string",
    "decode_folder_ref",
    "decode_imap_utf7",
    "email_fetch",
    "email_fetch_batch",
    "email_fetch_headers",
    "email_fetch_text",
    "email_search",
    "encode_folder_ref",
    "encode_imap_utf7",
    "get_subject_batch_size",
    "login",
    "logout",
    "parse_search_response",
    "quote_folder",
    "selectfolder",
]
