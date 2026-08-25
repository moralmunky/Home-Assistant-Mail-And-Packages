"""IMAP connection and search utilities for Mail and Packages."""

import asyncio
import binascii
import logging
import re
import ssl as ssl_lib
import unicodedata
from urllib.parse import quote, unquote

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

from custom_components.mail_and_packages.const import DEFAULT_IMAP_TIMEOUT

_LOGGER = logging.getLogger(__name__)

IMAP_SUBJECT_BATCH_SIZE_DEFAULT = 1
IMAP_SUBJECT_BATCH_SIZE_EXTENDED = 10
IMAP_ADDRESS_BATCH_SIZE = 5


def _get_subject_batch_size(account: IMAP4_SSL) -> int:
    """Return subject batch size based on server capability or host."""
    # Servers with known limited or fragile compound OR query parsers (e.g. Outlook/Exchange, Yahoo/AOL)
    if hasattr(account, "host") and isinstance(account.host, str):
        host_lower = account.host.lower()
        if any(h in host_lower for h in ("outlook", "office365", "yahoo", "aol")):
            return IMAP_SUBJECT_BATCH_SIZE_DEFAULT
        # Fast-track known capable servers like Gmail
        if "gmail" in host_lower or "google" in host_lower:
            return IMAP_SUBJECT_BATCH_SIZE_EXTENDED

    # Capability check fallback (e.g. Gmail custom extension X-GM-EXT-1)
    if hasattr(account, "has_capability") and callable(account.has_capability):
        try:
            res = account.has_capability("X-GM-EXT-1")
            if asyncio.iscoroutine(res):
                res.close()
                return IMAP_SUBJECT_BATCH_SIZE_DEFAULT
            if res:
                return IMAP_SUBJECT_BATCH_SIZE_EXTENDED
        except Exception:  # noqa: BLE001
            pass

    return IMAP_SUBJECT_BATCH_SIZE_DEFAULT


# Register ESEARCH command if not already present in aioimaplib
if "ESEARCH" not in aioimaplib.Commands:
    aioimaplib.Commands["ESEARCH"] = Cmd("ESEARCH", (AUTH, SELECTED), Exec.is_async)


def encode_imap_utf7(s: str) -> str:
    """Encode a string into IMAP modified UTF-7."""
    res = []
    unicode_buffer = []

    def flush_unicode():
        if unicode_buffer:
            u_str = "".join(unicode_buffer)
            encoded_bytes = u_str.encode("utf-16be")
            b64 = (
                binascii.b2a_base64(encoded_bytes)
                .decode("ascii")
                .rstrip("\n=")
                .replace("/", ",")
            )
            res.append(f"&{b64}-")
            unicode_buffer.clear()

    for char in s:
        ord_c = ord(char)
        if 0x20 <= ord_c <= 0x7E:
            if char == "&":
                flush_unicode()
                res.append("&-")
            else:
                if unicode_buffer:
                    flush_unicode()
                res.append(char)
        else:
            unicode_buffer.append(char)

    flush_unicode()
    return "".join(res)


def decode_imap_utf7(s: str) -> str:
    """Decode a string from IMAP modified UTF-7."""
    res = []
    i = 0
    n = len(s)
    while i < n:
        char = s[i]
        if char == "&":
            end = s.find("-", i + 1)
            if end == -1:
                res.append("&")
                i += 1
            elif end == i + 1:
                res.append("&")
                i += 2
            else:
                b64_part = s[i + 1 : end]
                b64_part = b64_part.replace(",", "/")
                pad = len(b64_part) % 4
                if pad:
                    b64_part += "=" * (4 - pad)
                try:
                    decoded_bytes = binascii.a2b_base64(b64_part)
                    res.append(decoded_bytes.decode("utf-16be"))
                except (binascii.Error, UnicodeDecodeError, ValueError):
                    res.append(s[i : end + 1])
                i = end + 1
        else:
            res.append(char)
            i += 1

    return "".join(res)


_ATOM_SPECIALS = frozenset('(){%*"\\] ')


def _is_imap_atom(s: str) -> bool:
    """Check if the string is a valid IMAP atom."""
    return bool(s) and all(0x20 < ord(c) < 0x7F and c not in _ATOM_SPECIALS for c in s)


def quote_folder(folder: str) -> str:
    """Ensure folder name is properly quoted for IMAP commands."""
    if folder.startswith('"') and folder.endswith('"'):
        return folder
    return folder if _is_imap_atom(folder) else f'"{folder}"'


def encode_folder_ref(folder: str) -> str:
    """Percent-encode a folder name for use in a composite ``folder/uid`` ID.

    Multi-folder searches tag each UID with its source folder as
    ``folder/uid``. Those composite IDs are space-joined and re-split on
    whitespace at several call sites, and split on ``/`` to recover the
    folder — so the folder component must contain neither whitespace nor
    ``/``. A folder named ``# - Projects`` would otherwise shatter into
    ``#``, ``-``, ``Projects/55`` when the joined ID list is ``.split()``.
    ``quote(..., safe="")`` escapes both (and ``%`` itself, keeping the
    round-trip lossless for any folder name).
    """
    return quote(folder, safe="")


def decode_folder_ref(folder: str) -> str:
    """Decode the percent-encoded folder component of a composite ID.

    Takes the already-split folder component (everything before the final
    ``/`` of a ``folder/uid`` ID), not the full composite ID.
    """
    return unquote(folder)


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


async def selectfolder(account: IMAP4_SSL, folder: str) -> bool:
    """Select folder inside the mailbox asynchronously."""
    if getattr(account, "_current_folder", None) == folder:
        return True

    encoded_folder = encode_imap_utf7(folder)
    quoted_folder = quote_folder(encoded_folder)

    try:
        await account.select(quoted_folder)
    except TimeoutError:
        raise
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error selecting folder %s: %s", folder, err)
        return False
    else:
        account._current_folder = folder  # noqa: SLF001
        return True


def clean_search_string(val: str) -> str:
    """Clean search string for IMAP search compatibility.

    Normalizes Unicode characters to NFKD decomposed form, strips non-ASCII
    characters to ensure compatibility with US-ASCII only IMAP servers,
    and removes any double quotes and colons to prevent syntax corruption.
    """
    if not val:
        return ""
    normalized = unicodedata.normalize("NFKD", val)
    cleaned = normalized.encode("ascii", "ignore").decode("ascii")
    return cleaned.replace('"', "").replace(":", "").strip()


def _build_address_clause(
    address: list, header: str = "", is_yahoo: bool = False
) -> str:
    """Build FROM / HEADER address search clause."""
    if header:
        parts = [f'OR HEADER "{header}" "{a}" FROM "{a}"' for a in address]
        if len(parts) == 1:
            return f"({parts[0]})" if is_yahoo else parts[0]
        or_prefix = " ".join(["OR"] * (len(parts) - 1))
        return (
            f"({or_prefix} {' '.join(parts)})"
            if is_yahoo
            else f"{or_prefix} {' '.join(parts)}"
        )

    if len(address) == 1:
        return f'FROM "{address[0]}"'

    joined = '" FROM "'.join(address)
    or_prefix = " ".join(["OR"] * (len(address) - 1))
    return (
        f'({or_prefix} FROM "{joined}")' if is_yahoo else f'{or_prefix} FROM "{joined}"'
    )


def _build_subject_clause(subject: str | list[str] = "", is_yahoo: bool = False) -> str:
    """Build SUBJECT search clause."""
    if not subject:
        return ""
    subjects = [subject] if isinstance(subject, str) else subject
    safe_subjects = [clean_search_string(s) for s in subjects]
    safe_subjects = list(dict.fromkeys(s for s in safe_subjects if s))

    if len(safe_subjects) == 1:
        return f'SUBJECT "{safe_subjects[0]}"'
    if len(safe_subjects) > 1:
        subject_prefix = " ".join(["OR"] * (len(safe_subjects) - 1))
        subject_joined = '" SUBJECT "'.join(safe_subjects)
        return (
            f'({subject_prefix} SUBJECT "{subject_joined}")'
            if is_yahoo
            else f'{subject_prefix} SUBJECT "{subject_joined}"'
        )
    return ""


def _build_body_clause(body: str | list[str] = "", is_yahoo: bool = False) -> str:
    """Build BODY search clause."""
    if not body:
        return ""
    bodies = [body] if isinstance(body, str) else body
    safe_bodies = [clean_search_string(b) for b in bodies]
    safe_bodies = [b for b in safe_bodies if b]

    if len(safe_bodies) == 1:
        return f'BODY "{safe_bodies[0]}"'
    if len(safe_bodies) > 1:
        body_prefix = " ".join(["OR"] * (len(safe_bodies) - 1))
        body_joined = '" BODY "'.join(safe_bodies)
        return (
            f'({body_prefix} BODY "{body_joined}")'
            if is_yahoo
            else f'{body_prefix} BODY "{body_joined}"'
        )
    return ""


def build_search(
    address: list,
    date: str,
    subject: str | list[str] = "",
    body: str | list[str] = "",
    header: str = "",
    is_yahoo: bool = False,
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

    addr_clause = _build_address_clause(address, header, is_yahoo)
    subject_part = _build_subject_clause(subject, is_yahoo)
    body_part = _build_body_clause(body, is_yahoo)

    criteria_parts = [p for p in (subject_part, body_part) if p]
    if criteria_parts:
        search_criteria = " ".join(criteria_parts)
        imap_search = (
            f"({addr_clause} {search_criteria} {the_date})"
            if is_yahoo
            else f"{addr_clause} {search_criteria} {the_date}"
        )
    else:
        imap_search = (
            f"({addr_clause} {the_date})" if is_yahoo else f"{addr_clause} {the_date}"
        )

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    return (False, imap_search)


def parse_search_response(lines: list[bytes]) -> list[bytes]:
    """Parse IMAP SEARCH response lines and return list of UID/ID bytes.

    Handles both standard server responses (prefixed with b"SEARCH")
    and mocked test inputs (which often contain raw UIDs directly).
    Filters out the SEARCH keyword, tagged OK/status responses,
    and any non-numeric tokens.
    """
    uids = []
    for line in lines:
        if not line:
            continue
        parts = line.split()
        if not parts:
            continue

        if parts[0] == b"SEARCH":
            # Check if this is a search result line, e.g. b"SEARCH 1001 1002"
            # (as opposed to b"SEARCH completed")
            if len(parts) > 1 and parts[1].isdigit():
                uids.extend(parts[1:])
        # Check if this line is just a list of numeric UIDs (mock/test compatibility)
        # and ignore status/existence responses like b"23 EXISTS"
        elif all(p.isdigit() for p in parts):
            uids.extend(parts)

    return uids


def _parse_esearch_line(line_bytes: bytes) -> list[bytes]:
    """Parse a single ESEARCH line and return list of formatted UID bytes: b'folder/uid'."""
    line_str = line_bytes.decode("utf-8", "ignore")

    # Extract the correlator inside parentheses
    start_paren = line_str.find("(")
    end_paren = line_str.find(")", start_paren) if start_paren != -1 else -1
    if start_paren == -1 or end_paren == -1:
        return []

    correlator = line_str[start_paren + 1 : end_paren]

    # Extract mailbox name (could be quoted or unquoted)
    mailbox_match = re.search(r'MAILBOX\s+"([^"]+)"', correlator)
    if not mailbox_match:
        mailbox_match = re.search(r"MAILBOX\s+(\S+)", correlator)
    if not mailbox_match:
        return []
    mailbox = mailbox_match.group(1)
    mailbox = decode_imap_utf7(mailbox)

    # Extract the sequence set after 'UID ALL' anywhere in the line
    seq_match = re.search(r"UID\s+ALL\s+(\S+)", line_str)
    if not seq_match:
        return []
    seq_set = seq_match.group(1)

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
    return [f"{encode_folder_ref(mailbox)}/{uid}".encode() for uid in uids]


def _supports_multisearch(account: IMAP4_SSL) -> bool:
    """Check if account supports MULTISEARCH capability safely."""
    if not hasattr(account, "has_capability"):
        return False
    try:
        res = account.has_capability("MULTISEARCH")
        if asyncio.iscoroutine(res):
            res.close()
            return False
        return bool(res)
    except Exception:  # noqa: BLE001
        return False


async def _execute_multisearch(
    account: IMAP4_SSL, folders: list[str], search_query: str
) -> list[bytes]:
    """Execute ESEARCH across multiple folders."""
    all_uids = []
    folder_list = " ".join([quote_folder(encode_imap_utf7(f)) for f in folders])
    args = ("IN", f"({folder_list})", search_query)
    try:
        timeout = getattr(account, "timeout", None)
        if not isinstance(timeout, (int, float)):
            timeout = None
        res = await account.protocol.execute(
            Command(
                "ESEARCH",
                account.protocol.new_tag(),
                *args,
                loop=account.protocol.loop,
                timeout=timeout,
            )
        )
        if res.result == "OK":
            for line in res.lines:
                if line:
                    all_uids.extend(_parse_esearch_line(line))
    except TimeoutError:
        raise
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error executing ESEARCH: %s", err)
    return all_uids


async def _execute_sequential_search(
    account: IMAP4_SSL, folders: list[str], search_query: str
) -> list[bytes]:
    """Execute search across folders sequentially."""
    all_uids = []
    for folder in folders:
        select_ok = await selectfolder(account, folder)
        if not select_ok:
            continue
        try:
            res = await account.uid_search(search_query, charset=None)
            if res.result == "OK" and res.lines:
                parsed = parse_search_response(res.lines)
                all_uids.extend(
                    f"{encode_folder_ref(folder)}/{uid.decode()}".encode()
                    for uid in parsed
                )
        except TimeoutError:
            raise
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching folder %s: %s", folder, err)
    return all_uids


async def _execute_uid_search(account: IMAP4_SSL, query: str) -> tuple[str, list]:
    """Execute search query using UID search with fallback for mock compatibility."""
    try:
        res = await account.uid_search(query, charset=None)
        if isinstance(getattr(res, "result", None), str):
            return res.result, res.lines
    except (AttributeError, TypeError):
        pass
    res = await account.search(query, charset=None)
    return res.result, res.lines


async def _execute_uid_fetch(
    account: IMAP4_SSL, num_str: str, parts: str
) -> tuple[str, list]:
    """Execute fetch using UID fetch with fallback for mock compatibility."""
    try:
        res = await account.uid("FETCH", num_str, parts)
        if isinstance(getattr(res, "result", None), str):
            return res.result, res.lines
    except (AttributeError, TypeError):
        pass
    res = await account.fetch(num_str, parts)
    return res.result, res.lines


async def _execute_single_search(account: IMAP4_SSL, search_query: str) -> list[bytes]:
    """Execute search query. If single folder, use standard search. If multiple, use hybrid ESEARCH/fallback."""
    folders = getattr(account, "_folders", ["INBOX"])

    if len(folders) <= 1:
        result, lines = await _execute_uid_search(account, search_query)
        if result == "OK" and lines:
            return parse_search_response(lines)
        return []

    if _supports_multisearch(account):
        return await _execute_multisearch(account, folders, search_query)
    return await _execute_sequential_search(account, folders, search_query)


async def _search_all_batches_sequential(
    account: IMAP4_SSL,
    address_batches: list[list[str]],
    subject_batches: list[list[str] | str],
    date: str,
    body_search: str | list[str],
    header: str,
    is_yahoo: bool,
    use_multi_folder: bool = False,
) -> tuple:
    """Execute batch searches sequentially to maintain a single in-flight command on the IMAP connection."""
    batch_queries = [
        build_search(
            addr_batch,
            date,
            subj_batch,
            body_search,
            header,
            is_yahoo=is_yahoo,
        )[1]
        for addr_batch in address_batches
        for subj_batch in subject_batches
    ]

    all_matched_ids: list[bytes] = []
    batch_success = False
    for query in batch_queries:
        try:
            if use_multi_folder:
                uids = await _execute_single_search(account, query)
                batch_success = True
                all_matched_ids.extend(uids)
            else:
                result, lines = await _execute_uid_search(account, query)
                if result == "OK":
                    batch_success = True
                    if lines:
                        parsed = parse_search_response(lines)
                        all_matched_ids.extend(parsed)
        except TimeoutError:
            raise
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching emails batch: %s", err)

    if not batch_success and not all_matched_ids:
        return ("BAD", "All search batches failed")

    unique_ids = list(dict.fromkeys(all_matched_ids))
    return ("OK", [b" ".join(unique_ids)])


async def _email_search_single_folder(
    account: IMAP4_SSL,
    address_batches: list[list[str]],
    subject_batches: list[list[str] | str],
    date: str,
    body_search: str | list[str],
    header: str,
    is_yahoo: bool,
    is_batched: bool,
    address: list,
    subject_search: list | str,
) -> tuple:
    """Execute search on a single folder mailbox."""
    if not is_batched:
        _unused, search = build_search(
            address, date, subject_search, body_search, header, is_yahoo=is_yahoo
        )
        try:
            result, lines = await _execute_uid_search(account, search)
        except TimeoutError:
            raise
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching emails: %s", err)
            return ("BAD", str(err))
        parsed = parse_search_response(lines)
        return (result, [b" ".join(parsed)])

    return await _search_all_batches_sequential(
        account,
        address_batches,
        subject_batches,
        date,
        body_search,
        header,
        is_yahoo,
        use_multi_folder=False,
    )


async def _email_search_multi_folder(
    account: IMAP4_SSL,
    address_batches: list[list[str]],
    subject_batches: list[list[str] | str],
    date: str,
    body_search: str | list[str],
    header: str,
    is_yahoo: bool,
    is_batched: bool,
    address: list,
    subject_search: list | str,
) -> tuple:
    """Execute search across multiple folders."""
    if not is_batched:
        _unused, search = build_search(
            address, date, subject_search, body_search, header, is_yahoo=is_yahoo
        )
        try:
            uids = await _execute_single_search(account, search)
        except TimeoutError:
            raise
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching emails: %s", err)
            return ("BAD", str(err))
        return ("OK", [b" ".join(uids)])

    return await _search_all_batches_sequential(
        account,
        address_batches,
        subject_batches,
        date,
        body_search,
        header,
        is_yahoo,
        use_multi_folder=True,
    )


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
    if hasattr(account, "host") and isinstance(account.host, str):
        host_lower = account.host.lower()
        is_yahoo = "yahoo" in host_lower or "aol" in host_lower

    body_search = body
    if body:
        bodies = [body] if isinstance(body, str) else body
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

    if len(folders) <= 1:
        return await _email_search_single_folder(
            account,
            address_batches,
            subject_batches,
            date,
            body_search,
            header,
            is_yahoo,
            is_batched,
            address,
            subject_search,
        )

    return await _email_search_multi_folder(
        account,
        address_batches,
        subject_batches,
        date,
        body_search,
        header,
        is_yahoo,
        is_batched,
        address,
        subject_search,
    )


async def email_fetch(account: IMAP4_SSL, num, parts: str = "(RFC822)") -> tuple:
    """Download specified email for parsing asynchronously."""
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    num_str = num.decode() if isinstance(num, bytes) else str(num)
    if "/" in num_str:
        folder, num_str = num_str.rsplit("/", 1)
        await selectfolder(account, decode_folder_ref(folder))

    try:
        result, lines = await _execute_uid_fetch(account, num_str, parts)
    except TimeoutError:
        raise
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (result, lines)


async def email_fetch_headers(account: IMAP4_SSL, num) -> tuple:
    """Download only the subject header of an email asynchronously."""
    num_str = num.decode() if isinstance(num, bytes) else str(num)
    if "/" in num_str:
        folder, num_str = num_str.rsplit("/", 1)
        await selectfolder(account, decode_folder_ref(folder))

    try:
        result, lines = await _execute_uid_fetch(
            account, num_str, "(BODY[HEADER.FIELDS (SUBJECT)])"
        )
    except TimeoutError:
        raise
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email headers %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (result, lines)


async def email_fetch_text(account: IMAP4_SSL, num, parts: str = "(BODY[1])") -> tuple:
    """Download the specific part of the email body asynchronously."""
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    num_str = num.decode() if isinstance(num, bytes) else str(num)
    if "/" in num_str:
        folder, num_str = num_str.rsplit("/", 1)
        await selectfolder(account, decode_folder_ref(folder))

    try:
        result, lines = await _execute_uid_fetch(account, num_str, parts)
    except TimeoutError:
        raise
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email text %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (result, lines)


async def _fetch_batch_single_folder(
    account: IMAP4_SSL, nums: list[str | bytes], parts: str
) -> tuple:
    """Fetch a batch of emails from the currently active folder."""
    num_strs = [num.decode() if isinstance(num, bytes) else str(num) for num in nums]
    num_list_str = ",".join(num_strs)
    try:
        result, lines = await _execute_uid_fetch(account, num_list_str, parts)
    except TimeoutError:
        raise
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching emails batch %s: %s", num_list_str, err)
        return ("BAD", str(err))
    else:
        return (result, lines)


def _group_nums_by_folder(nums: list[str | bytes]) -> dict[str | None, list[str]]:
    """Group composite and standard email UIDs by their folder reference."""
    folder_to_nums: dict[str | None, list[str]] = {}
    for num in nums:
        num_str = num.decode() if isinstance(num, bytes) else str(num)
        if "/" in num_str:
            folder, actual_num = num_str.rsplit("/", 1)
            folder = decode_folder_ref(folder)
        else:
            folder, actual_num = None, num_str
        folder_to_nums.setdefault(folder, []).append(actual_num)
    return folder_to_nums


async def _fetch_batch_multi_folder(
    account: IMAP4_SSL, nums: list[str | bytes], parts: str
) -> tuple:
    """Fetch emails grouped across multiple folders."""
    folder_to_nums = _group_nums_by_folder(nums)
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
        except TimeoutError:
            raise
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error fetching emails batch %s: %s", num_list_str, err)
            return ("BAD", str(err))

    return (overall_result, all_results)


async def email_fetch_batch(
    account: IMAP4_SSL, nums: list[str | bytes], parts: str = "(RFC822)"
) -> tuple:
    """Download specified emails for parsing asynchronously in a batch."""
    if not nums:
        return ("OK", [])

    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    has_folder_prefix = any(
        "/" in (n.decode() if isinstance(n, bytes) else str(n)) for n in nums
    )

    if not has_folder_prefix:
        return await _fetch_batch_single_folder(account, nums, parts)

    return await _fetch_batch_multi_folder(account, nums, parts)


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
