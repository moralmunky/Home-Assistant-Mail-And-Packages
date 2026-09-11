"""IMAP search query building and parsing utilities."""

import logging
import re
import unicodedata
from dataclasses import dataclass

from .imap_utf7 import decode_imap_utf7, encode_folder_ref

_LOGGER = logging.getLogger(__name__)


def clean_search_string(val: str) -> str:
    """Clean search string for IMAP search compatibility.

    Normalizes Unicode characters to NFKD decomposed form, strips non-ASCII
    characters to ensure compatibility with US-ASCII only IMAP servers,
    and removes any double quotes to prevent syntax corruption.
    """
    if not val:
        return ""
    normalized = unicodedata.normalize("NFKD", val)
    cleaned = normalized.encode("ascii", "ignore").decode("ascii")
    return cleaned.replace('"', "").strip()


def _build_address_clause(
    address: list,
    header: str = "",
    is_yahoo: bool = False,
    is_exchange: bool = False,
) -> str:
    """Build FROM / HEADER address search clause."""
    if header:
        if is_exchange:
            parts = [f'OR HEADER "{header}" "{a}" FROM "{a}"' for a in address]
            if len(parts) == 1:
                return parts[0]
            or_prefix = " ".join(["OR"] * (len(parts) - 1))
            return f"{or_prefix} {' '.join(parts)}"

        parts = [f'(OR HEADER "{header}" "{a}" FROM "{a}")' for a in address]
        if len(parts) == 1:
            return parts[0]
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
    is_exchange: bool = False,
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

    addr_clause = _build_address_clause(address, header, is_yahoo, is_exchange)
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
                _LOGGER.debug("Could not parse ESEARCH range: %s", part)
        else:
            uids.append(part)
    return [f"{encode_folder_ref(mailbox)}/{uid}".encode() for uid in uids]


@dataclass
class SearchBatchParams:
    """Parameters for IMAP search batch operations."""

    address_batches: list[list[str]]
    subject_batches: list[list[str] | str]
    date: str
    body_search: str | list[str]
    header: str
    is_yahoo: bool
    is_exchange: bool = False
