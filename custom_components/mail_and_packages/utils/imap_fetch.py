"""IMAP folder selection and email fetch utilities."""

import logging
from typing import TYPE_CHECKING

from aioimaplib import AioImapException

from .imap_utf7 import decode_folder_ref, encode_imap_utf7, quote_folder

if TYPE_CHECKING:
    from aioimaplib import IMAP4_SSL

_LOGGER = logging.getLogger(__name__)


async def selectfolder(account: "IMAP4_SSL", folder: str) -> bool:
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


async def _execute_uid_fetch(
    account: "IMAP4_SSL", num_str: str, parts: str
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


async def email_fetch(account: "IMAP4_SSL", num, parts: str = "(RFC822)") -> tuple:
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


async def email_fetch_headers(account: "IMAP4_SSL", num) -> tuple:
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


async def email_fetch_text(
    account: "IMAP4_SSL", num, parts: str = "(BODY[1])"
) -> tuple:
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
    account: "IMAP4_SSL", nums: list[str | bytes], parts: str
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
    account: "IMAP4_SSL", nums: list[str | bytes], parts: str
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
    account: "IMAP4_SSL", nums: list[str | bytes], parts: str = "(RFC822)"
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
