"""IMAP connection and search utilities for Mail and Packages."""

import logging

from aioimaplib import AUTH, IMAP4, IMAP4_SSL, NONAUTH, SELECTED, AioImapException
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import ssl

_LOGGER = logging.getLogger(__name__)


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
        return True


def build_search(address: list, date: str, subject: str = "") -> tuple:
    """Build IMAP search query.

    Return tuple of utf8 flag and search query.
    Non-ASCII characters are stripped from subject to ensure compatibility
    with servers that only support US-ASCII charset (e.g. Microsoft Exchange).
    IMAP SUBJECT performs substring matching, so stripping non-ASCII chars
    still matches the original subject (e.g. 'Livr' matches 'Livré').
    """
    the_date = f"SINCE {date}"
    imap_search = None
    prefix_list = None
    email_list = None

    if len(address) == 1:
        email_list = address[0]
    else:
        email_list = '" FROM "'.join(address)
        prefix_list = " ".join(["OR"] * (len(address) - 1))

    _LOGGER.debug("DEBUG subject: %s", subject)

    if subject is not None:
        # Strip non-ASCII characters for IMAP server compatibility
        safe_subject = subject.encode("ascii", "ignore").decode("ascii")
        if prefix_list is not None:
            imap_search = f'({prefix_list} FROM "{email_list}" SUBJECT "{safe_subject}" {the_date})'
        else:
            imap_search = f'(FROM "{email_list}" SUBJECT "{safe_subject}" {the_date})'
    elif prefix_list is not None:
        imap_search = f'({prefix_list} FROM "{email_list}" {the_date})'
    else:
        imap_search = f'(FROM "{email_list}" {the_date})'

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    return (False, imap_search)


async def email_search(
    account: IMAP4_SSL, address: list, date: str, subject: str = ""
) -> tuple:
    """Search emails with from, subject, and date asynchronously.

    Always uses charset=None to avoid sending CHARSET in the IMAP SEARCH
    command, ensuring compatibility with servers like Microsoft Exchange
    that only support US-ASCII.
    """
    _unused, search = build_search(address, date, subject)

    try:
        res = await account.search(search, charset=None)
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error searching emails: %s", err)
        return ("BAD", str(err))
    else:
        return (res.result, res.lines)


async def email_fetch(account: IMAP4_SSL, num, parts: str = "(RFC822)") -> tuple:
    """Download specified email for parsing asynchronously."""
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    num_str = num.decode() if isinstance(num, bytes) else str(num)

    try:
        res = await account.fetch(num_str, parts)
    except (AioImapException, OSError) as err:
        _LOGGER.error("Error fetching email %s: %s", num_str, err)
        return ("BAD", str(err))
    else:
        return (res.result, res.lines)
