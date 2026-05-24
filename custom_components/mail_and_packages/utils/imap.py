"""IMAP connection and search utilities for Mail and Packages."""

import asyncio
import logging
import re

import aioimaplib
from aioimaplib import (
    AUTH,
    IMAP4,
    IMAP4_SSL,
    NONAUTH,
    SELECTED,
    AioImapException,
    Cmd,
    Command,
    Exec,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import ssl

_LOGGER = logging.getLogger(__name__)

# Register ESEARCH command if not already present in aioimaplib
if "ESEARCH" not in aioimaplib.Commands:
    aioimaplib.Commands["ESEARCH"] = Cmd("ESEARCH", (AUTH, SELECTED), Exec.is_async)


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
) -> IMAP4_SSL | IMAP4:
    """Login to IMAP server asynchronously.

    Supports both password and OAuth2 (XOAUTH2) authentication.
    If oauth_token is provided, uses XOAUTH2 SASL mechanism.
    Otherwise falls back to standard LOGIN command.
    """
    ssl_context = (
        ssl.client_context(ssl.SSLCipherList.PYTHON_DEFAULT)
        if verify
        else ssl.create_no_verify_ssl_context()
    )
    if security == "SSL":
        account = IMAP4_SSL(host=host, port=port, ssl_context=ssl_context)
    else:
        account = IMAP4(host=host, port=port)

    await account.wait_hello_from_server()

    if account.protocol.state == NONAUTH:
        try:
            if oauth_token:
                await account.xoauth2(user, oauth_token)
            else:
                await account.login(user, pwd)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error logging in to IMAP Server: %s", err)
            raise InvalidAuth from err

    if account.protocol.state not in {AUTH, SELECTED}:
        _LOGGER.error("Error logging in to IMAP Server")
        raise InvalidAuth
    return account


async def selectfolder(account: IMAP4_SSL, folder: str) -> bool:
    """Select folder inside the mailbox asynchronously."""
    if getattr(account, "_current_folder", None) == folder:
        return True

    try:
        await account.list(folder, "*")
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error listing folder %s: %s", folder, err)
        return False

    try:
        await account.select(folder)
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error selecting folder %s: %s", folder, err)
        return False
    else:
        account._current_folder = folder  # noqa: SLF001
        return True


def build_search(
    address: list,
    date: str,
    subject: str | list[str] = "",
    header: str = "",
) -> tuple:
    """Build IMAP search query.

    Return tuple of utf8 flag and search query.
    Non-ASCII characters are stripped from subject to ensure compatibility
    with servers that only support US-ASCII charset (e.g. Microsoft Exchange).
    IMAP SUBJECT performs substring matching, so stripping non-ASCII chars
    still matches the original subject (e.g. 'Livr' matches 'Livré').

    When `header` is provided, each address is matched as either a forwarded
    email (via HEADER substring match) OR a direct email (via FROM), so the
    same config works for carriers that are forwarded through a service like
    SimpleLogin AND carriers whose emails arrive directly in the mailbox.
    IMAP HEADER does substring matching, so "mcinfo@ups.com" will match a
    header value of "UPS <mcinfo@ups.com>".
    """
    the_date = f"SINCE {date}"

    if not address:
        raise ValueError("address list must not be empty")

    # Build the address/header clause
    if header:
        # Each address matches via header (forwarded) OR FROM (direct), so
        # users with mixed setups (some carriers forwarded, others direct)
        # don't need separate configurations.
        parts = [f'OR HEADER "{header}" "{a}" FROM "{a}"' for a in address]
        if len(parts) == 1:
            addr_clause = parts[0]
        else:
            or_prefix = " ".join(["OR"] * (len(parts) - 1))
            addr_clause = f"{or_prefix} {' '.join(parts)}"
    elif len(address) == 1:
        addr_clause = f'FROM "{address[0]}"'
    else:
        joined = '" FROM "'.join(address)
        or_prefix = " ".join(["OR"] * (len(address) - 1))
        addr_clause = f'{or_prefix} FROM "{joined}"'

    # Handle multiple subjects
    subject_part = ""
    if subject:
        subjects = [subject] if isinstance(subject, str) else subject
        safe_subjects = [s.encode("ascii", "ignore").decode("ascii") for s in subjects]
        safe_subjects = [s for s in safe_subjects if s]

        if len(safe_subjects) == 1:
            subject_part = f'SUBJECT "{safe_subjects[0]}"'
        elif len(safe_subjects) > 1:
            subject_prefix = " ".join(["OR"] * (len(safe_subjects) - 1))
            subject_part = (
                f'({subject_prefix} SUBJECT "{'" SUBJECT "'.join(safe_subjects)}")'
            )

    if subject_part:
        imap_search = f"({addr_clause} {subject_part} {the_date})"
    else:
        imap_search = f"({addr_clause} {the_date})"

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    return (False, imap_search)


_ESEARCH_RE = re.compile(
    r'\(TAG\s+"[^"]+"\s+MAILBOX\s+"([^"]+)"\s+UIDVALIDITY\s+\d+\)\s+UID\s+ALL\s+(.+)'
)


def _parse_esearch_line(line_bytes: bytes) -> list[bytes]:
    """Parse a single ESEARCH line and return list of formatted UID bytes: b'folder/uid'."""
    line_str = line_bytes.decode("utf-8", "ignore")
    match = _ESEARCH_RE.search(line_str)
    if not match:
        return []
    mailbox = match.group(1)
    seq_set = match.group(2)
    uids = []
    for part in seq_set.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            try:
                start_str, end_str = part.split(":", 1)
                start, end = int(start_str), int(end_str)
                if start <= end:
                    uids.extend(str(x) for x in range(start, end + 1))
                else:
                    uids.extend(str(x) for x in range(end, start + 1))
            except ValueError:
                pass
        else:
            uids.append(part)
    return [f"{mailbox}/{uid}".encode() for uid in uids]


async def _execute_single_search(account: IMAP4_SSL, search_query: str) -> list[bytes]:  # noqa: C901
    """Execute search query. If single folder, use standard search. If multiple, use hybrid ESEARCH/fallback."""
    folders = getattr(account, "_folders", ["INBOX"])

    if len(folders) <= 1:
        res = await account.search(search_query, charset=None)
        if res.result == "OK" and res.lines[0]:
            return res.lines[0].split()
        return []

    all_uids = []

    # Check for MULTISEARCH capability safely (handling mock/AsyncMock in tests)
    is_multisearch = False
    if hasattr(account, "has_capability"):
        try:
            res = account.has_capability("MULTISEARCH")
            if asyncio.iscoroutine(res):
                res.close()
                is_multisearch = False
            else:
                is_multisearch = bool(res)
        except Exception:  # noqa: BLE001
            pass

    if is_multisearch:
        # ESEARCH IN ("folder1" "folder2") query
        folder_list = " ".join([f'"{f}"' for f in folders])
        args = ("IN", f"({folder_list})", search_query)
        try:
            res = await account.protocol.execute(
                Command(
                    "ESEARCH",
                    account.protocol.new_tag(),
                    *args,
                    loop=account.protocol.loop,
                )
            )
            if res.result == "OK":
                for line in res.lines:
                    if line:
                        all_uids.extend(_parse_esearch_line(line))
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error executing ESEARCH: %s", err)
    else:
        # Sequential select and search fallback
        for folder in folders:
            select_ok = await selectfolder(account, folder)
            if not select_ok:
                continue
            try:
                res = await account.uid_search(search_query, charset=None)
                if res.result == "OK" and res.lines[0]:
                    all_uids.extend(
                        f"{folder}/{uid.decode()}".encode()
                        for uid in res.lines[0].split()
                    )
            except (AioImapException, OSError) as err:
                _LOGGER.error("Error searching folder %s: %s", folder, err)

    return all_uids


async def email_search(  # noqa: C901
    account: IMAP4_SSL,
    address: list,
    date: str,
    subject: str | list[str] = "",
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

    if len(folders) <= 1:
        if not isinstance(subject, list) or len(subject) <= 10:
            _unused, search = build_search(address, date, subject, header)
            try:
                res = await account.search(search, charset=None)
            except (AioImapException, OSError) as err:
                _LOGGER.error("Error searching emails: %s", err)
                return ("BAD", str(err))
            else:
                return (res.result, res.lines)

        # Batch subjects in groups of 10
        all_matched_ids = []
        for i in range(0, len(subject), 10):
            batch = subject[i : i + 10]
            _unused, search = build_search(address, date, batch, header)
            try:
                res = await account.search(search, charset=None)
                if res.result == "OK" and res.lines[0]:
                    all_matched_ids.extend(res.lines[0].split())
            except (AioImapException, OSError) as err:
                _LOGGER.error("Error searching emails batch: %s", err)

        # Deduplicate and return in same format as individual search
        unique_ids = list(dict.fromkeys(all_matched_ids))
        return ("OK", [b" ".join(unique_ids)])

    # Multi-folder search logic
    if not isinstance(subject, list) or len(subject) <= 10:
        _unused, search = build_search(address, date, subject, header)
        try:
            uids = await _execute_single_search(account, search)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching emails: %s", err)
            return ("BAD", str(err))
        return ("OK", [b" ".join(uids)])

    # Batch subjects in groups of 10
    all_matched_ids = []
    for i in range(0, len(subject), 10):
        batch = subject[i : i + 10]
        _unused, search = build_search(address, date, batch, header)
        try:
            uids = await _execute_single_search(account, search)
            all_matched_ids.extend(uids)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching emails batch: %s", err)

    # Deduplicate and return in same format as individual search
    unique_ids = list(dict.fromkeys(all_matched_ids))
    return ("OK", [b" ".join(unique_ids)])


async def email_fetch(account: IMAP4_SSL, num, parts: str = "(RFC822)") -> tuple:
    """Download specified email for parsing asynchronously."""
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    num_str = num.decode() if isinstance(num, bytes) else str(num)
    if "/" in num_str:
        folder, num_str = num_str.rsplit("/", 1)
        await selectfolder(account, folder)
        try:
            res = await account.uid("FETCH", num_str, parts)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error fetching email %s: %s", num_str, err)
            return ("BAD", str(err))
        else:
            return (res.result, res.lines)

    try:
        res = await account.fetch(num_str, parts)
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (res.result, res.lines)


async def email_fetch_headers(account: IMAP4_SSL, num) -> tuple:
    """Download only the subject header of an email asynchronously."""
    num_str = num.decode() if isinstance(num, bytes) else str(num)
    if "/" in num_str:
        folder, num_str = num_str.rsplit("/", 1)
        await selectfolder(account, folder)
        try:
            res = await account.uid("FETCH", num_str, "(BODY[HEADER.FIELDS (SUBJECT)])")
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error fetching email headers %s: %s", num_str, err)
            return ("BAD", str(err))
        else:
            return (res.result, res.lines)

    try:
        res = await account.fetch(num_str, "(BODY[HEADER.FIELDS (SUBJECT)])")
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email headers %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (res.result, res.lines)


async def email_fetch_text(account: IMAP4_SSL, num, parts: str = "(BODY[1])") -> tuple:
    """Download the specific part of the email body asynchronously."""
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    num_str = num.decode() if isinstance(num, bytes) else str(num)
    if "/" in num_str:
        folder, num_str = num_str.rsplit("/", 1)
        await selectfolder(account, folder)
        try:
            res = await account.uid("FETCH", num_str, parts)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error fetching email text %s: %s", num_str, err)
            return ("BAD", str(err))
        else:
            return (res.result, res.lines)

    try:
        res = await account.fetch(num_str, parts)
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email text %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (res.result, res.lines)


async def email_fetch_batch(  # noqa: C901
    account: IMAP4_SSL, nums: list[str | bytes], parts: str = "(RFC822)"
) -> tuple:
    """Download specified emails for parsing asynchronously in a batch."""
    if not nums:
        return ("OK", [])

    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    # Check if any ID contains a folder prefix
    has_folder_prefix = False
    for num in nums:
        num_str = num.decode() if isinstance(num, bytes) else str(num)
        if "/" in num_str:
            has_folder_prefix = True
            break

    if not has_folder_prefix:
        num_strs = [
            num.decode() if isinstance(num, bytes) else str(num) for num in nums
        ]
        num_list_str = ",".join(num_strs)
        try:
            res = await account.fetch(num_list_str, parts)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error fetching emails batch %s: %s", num_list_str, err)
            return ("BAD", str(err))
        else:
            return (res.result, res.lines)

    # Group nums by their folder prefix
    folder_to_nums = {}
    for num in nums:
        num_str = num.decode() if isinstance(num, bytes) else str(num)
        if "/" in num_str:
            folder, actual_num = num_str.rsplit("/", 1)
        else:
            folder, actual_num = None, num_str
        folder_to_nums.setdefault(folder, []).append(actual_num)

    all_results = []
    overall_result = "OK"

    for folder, folder_nums in folder_to_nums.items():
        if folder is not None:
            await selectfolder(account, folder)

        num_list_str = ",".join(folder_nums)
        try:
            res = await account.uid("FETCH", num_list_str, parts)
            if res.result != "OK":
                overall_result = res.result
            all_results.extend(res.lines)
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error fetching emails batch %s: %s", num_list_str, err)
            return ("BAD", str(err))

    return (overall_result, all_results)


async def logout(account: IMAP4_SSL | IMAP4) -> None:
    """Logout from IMAP server asynchronously."""
    try:
        await account.logout()
    except (TimeoutError, AioImapException, OSError, asyncio.CancelledError) as err:
        _LOGGER.debug("Error logging out of IMAP Server: %s", err)
