"""IMAP search query batch execution routines."""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from aioimaplib import AioImapException, Command

from .imap_fetch import selectfolder as _orig_selectfolder
from .imap_query import (
    SearchBatchParams,
    _parse_esearch_line,
    build_search,
    parse_search_response,
)
from .imap_utf7 import encode_folder_ref, encode_imap_utf7, quote_folder

if TYPE_CHECKING:
    from aioimaplib import IMAP4_SSL

_LOGGER = logging.getLogger(__name__)


def _get_imap_attr(attr_name: str, default_val: object) -> object:
    """Retrieve attribute from utils.imap to respect mock patches if present."""
    imap_mod = sys.modules.get("custom_components.mail_and_packages.utils.imap")
    if imap_mod is not None and hasattr(imap_mod, attr_name):
        return getattr(imap_mod, attr_name)
    return default_val


IMAP_SUBJECT_BATCH_SIZE_DEFAULT = 1
IMAP_SUBJECT_BATCH_SIZE_EXTENDED = 10
IMAP_ADDRESS_BATCH_SIZE = 5


def get_subject_batch_size(account: "IMAP4_SSL") -> int:
    """Return subject batch size based on server capability or host."""
    # Servers with known limited or fragile compound OR query parsers (e.g. Outlook/Exchange, Yahoo/AOL)
    if getattr(account, "_exchange_mode", None) is True:
        return IMAP_SUBJECT_BATCH_SIZE_DEFAULT
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
        except Exception as err:  # noqa: BLE001
            # Fall back to default batch size if checking IMAP capability fails
            _LOGGER.debug("Capability check failed, using default batch size: %s", err)

    return IMAP_SUBJECT_BATCH_SIZE_DEFAULT


# Backward-compatible alias
_get_subject_batch_size = get_subject_batch_size


def _supports_multisearch(account: "IMAP4_SSL") -> bool:
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
    account: "IMAP4_SSL", folders: list[str], search_query: str
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
    account: "IMAP4_SSL", folders: list[str], search_query: str
) -> list[bytes]:
    """Execute search across folders sequentially."""
    selectfolder_fn = _get_imap_attr("selectfolder", _orig_selectfolder)
    all_uids = []
    for folder in folders:
        select_ok = await selectfolder_fn(account, folder)
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


async def _execute_uid_search(account: "IMAP4_SSL", query: str) -> tuple[str, list]:
    """Execute search query using UID search with fallback for mock compatibility."""
    try:
        res = await account.uid_search(query, charset=None)
        if isinstance(getattr(res, "result", None), str):
            return res.result, res.lines
    except (AttributeError, TypeError):
        pass
    res = await account.search(query, charset=None)
    return res.result, res.lines


async def _execute_single_search(
    account: "IMAP4_SSL", search_query: str
) -> list[bytes]:
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
    account: "IMAP4_SSL",
    params: SearchBatchParams,
    use_multi_folder: bool = False,
) -> tuple:
    """Execute batch searches sequentially to maintain a single in-flight command on the IMAP connection."""
    batch_queries = [
        build_search(
            addr_batch,
            params.date,
            subj_batch,
            params.body_search,
            params.header,
            is_yahoo=params.is_yahoo,
            is_exchange=params.is_exchange,
        )[1]
        for addr_batch in params.address_batches
        for subj_batch in params.subject_batches
    ]

    all_matched_ids: list[bytes] = []
    batch_success = False
    single_search_fn = _get_imap_attr("_execute_single_search", _execute_single_search)
    for query in batch_queries:
        try:
            if use_multi_folder:
                uids = await single_search_fn(account, query)
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
    account: "IMAP4_SSL",
    params: SearchBatchParams,
    search_raw: tuple,
    is_batched: bool,
) -> tuple:
    """Execute search on a single folder mailbox."""
    if not is_batched:
        _unused, search = search_raw
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
        params,
        use_multi_folder=False,
    )


async def _email_search_multi_folder(
    account: "IMAP4_SSL",
    params: SearchBatchParams,
    search_raw: tuple,
    is_batched: bool,
) -> tuple:
    """Execute search across multiple folders."""
    if not is_batched:
        _unused, search = search_raw
        try:
            single_search_fn = _get_imap_attr(
                "_execute_single_search", _execute_single_search
            )
            uids = await single_search_fn(account, search)
        except TimeoutError:
            raise
        except (AioImapException, OSError) as err:
            _LOGGER.error("Error searching emails: %s", err)
            return ("BAD", str(err))
        return ("OK", [b" ".join(uids)])

    return await _search_all_batches_sequential(
        account,
        params,
        use_multi_folder=True,
    )
