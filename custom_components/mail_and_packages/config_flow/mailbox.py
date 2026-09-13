"""Mailbox discovery and IMAP login validation for Mail and Packages config flow."""

from __future__ import annotations

import contextlib
import logging
import ssl
import sys
from typing import Any

from aioimaplib import AioImapException
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from custom_components.mail_and_packages.const import (
    AUTH_TYPE_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_IMAP_SECURITY,
    CONF_VERIFY_SSL,
    DEFAULT_FOLDER,
)
from custom_components.mail_and_packages.utils.imap import InvalidAuth, decode_imap_utf7
from custom_components.mail_and_packages.utils.imap import login as default_login
from custom_components.mail_and_packages.utils.imap import logout as default_logout

_LOGGER = logging.getLogger(__name__)


def _get_target(symbol_name: str, fallback_callable: Any) -> Any:
    """Dynamically get symbol from config_flow module if imported/patched there."""
    cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
    if cf and hasattr(cf, symbol_name):
        return getattr(cf, symbol_name)
    return fallback_callable


async def _get_mailboxes(
    hass: HomeAssistant,
    conn_info: dict[str, Any] | str,
    *args: Any,
    oauth_token: str | None = None,
    **kwargs: Any,
) -> list:
    """Get list of mailbox folders from mail server."""
    login_fn = _get_target("login", default_login)
    logout_fn = _get_target("logout", default_logout)

    if isinstance(conn_info, dict):
        host = conn_info[CONF_HOST]
        port = conn_info[CONF_PORT]
        user = conn_info[CONF_USERNAME]
        pwd = conn_info.get(CONF_PASSWORD, "")
        security = conn_info[CONF_IMAP_SECURITY]
        verify = conn_info.get(CONF_VERIFY_SSL, True)
    else:
        host = conn_info
        port = args[0] if len(args) > 0 else kwargs.get("port", 993)
        user = args[1] if len(args) > 1 else kwargs.get("user", "")
        pwd = args[2] if len(args) > 2 else kwargs.get("pwd", "")
        security = args[3] if len(args) > 3 else kwargs.get("security", "SSL")
        verify = args[4] if len(args) > 4 else kwargs.get("verify", True)
        if len(args) > 5 and oauth_token is None:
            oauth_token = args[5]

    _LOGGER.debug("Getting mailboxes, login...")
    try:
        account = await login_fn(
            hass,
            host,
            port,
            user,
            pwd,
            security,
            verify,
            oauth_token=oauth_token,
        )

    except (TimeoutError, AioImapException, ConnectionRefusedError, InvalidAuth) as err:
        _LOGGER.error(
            "Unable to connect: %s (IMAP server %s:%s as %s, security: %s, oauth: %s, class: %s)",
            err if str(err) else "Authentication failed or timed out",
            host,
            port,
            user,
            security,
            oauth_token is not None,
            type(err).__name__,
        )
        return []

    _LOGGER.debug("Attempting to get mailbox list...")
    try:
        result = await account.list('""', '"*"')
        status = result.result
        folderlist = result.lines
        _LOGGER.debug("Get mailbox status: %s folder list: %s", status, folderlist)
        mailboxes = []
        if status != "OK" or not isinstance(folderlist, list):
            _LOGGER.error("Error listing mailboxes ... using default")
            mailboxes.append(DEFAULT_FOLDER)
        else:
            mailboxes = await _parse_folder_list(folderlist)
    finally:
        await logout_fn(account)

    return mailboxes


async def _parse_folder_list(folderlist: list) -> list:
    """Parse folder list from IMAP server response."""
    mailboxes = []
    with contextlib.suppress(IndexError):
        mailboxes.extend(
            decode_imap_utf7(i.decode().split(' "/" ')[1].strip('"'))
            for i in folderlist
        )

    with contextlib.suppress(IndexError):
        mailboxes.extend(
            decode_imap_utf7(i.decode().split(' "." ')[1].strip('"'))
            for i in folderlist
        )

    if len(mailboxes) == 0:
        _LOGGER.error("Problem reading mailbox folders, using default.")
        mailboxes.append(DEFAULT_FOLDER)

    return mailboxes


async def _validate_login(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> dict[str, str]:
    """Validate login credentials."""
    login_fn = _get_target("login", default_login)
    logout_fn = _get_target("logout", default_logout)

    errors = {}
    _LOGGER.debug("Testing login...")

    auth_type = user_input.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)

    # Skip login validation for OAuth2 — auth happens via the OAuth flow
    if auth_type != AUTH_TYPE_PASSWORD:
        return errors

    imap_client = None
    try:
        imap_client = await login_fn(
            hass,
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            user=user_input[CONF_USERNAME],
            pwd=user_input[CONF_PASSWORD],
            security=user_input[CONF_IMAP_SECURITY],
            verify=user_input[CONF_VERIFY_SSL],
        )
        result, data = await imap_client.select()

    except InvalidAuth:
        errors[CONF_USERNAME] = errors[CONF_PASSWORD] = "invalid_auth"
    except ssl.SSLError:
        errors["base"] = "ssl_error"
    except (TimeoutError, AioImapException, ConnectionRefusedError, OSError) as err:
        _LOGGER.error(
            "Unable to connect: %s (IMAP server %s:%s as %s, security: %s, oauth: False, class: %s)",
            err if str(err) else "Authentication failed or timed out",
            user_input[CONF_HOST],
            user_input[CONF_PORT],
            user_input[CONF_USERNAME],
            user_input[CONF_IMAP_SECURITY],
            type(err).__name__,
        )
        errors["base"] = "cannot_connect"
    else:
        if result != "OK":
            errors["base"] = "missing_inbox"
    finally:
        if imap_client is not None:
            await logout_fn(imap_client)

    return errors
