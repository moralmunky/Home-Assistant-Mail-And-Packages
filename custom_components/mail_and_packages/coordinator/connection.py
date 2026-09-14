"""IMAP connection helper for Mail and Packages data coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aioimaplib import IMAP4_SSL
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    UpdateFailed,
)

from custom_components.mail_and_packages.const import (
    CONF_EXCHANGE_MODE,
    CONF_FOLDER,
    CONF_IMAP_SECURITY,
    DEFAULT_EXCHANGE_MODE,
    DOMAIN,
)
from custom_components.mail_and_packages.utils.imap import (
    InvalidAuth,
    login,
    logout,
    selectfolder,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def get_imap_connection(
    hass: HomeAssistant,
    config: dict,
    timeout: int,
    config_entry: ConfigEntry | None = None,
    login_fn=login,
    selectfolder_fn=selectfolder,
    logout_fn=logout,
) -> IMAP4_SSL:
    """Establish and return an authenticated IMAP connection."""
    try:
        account = await login_fn(
            hass,
            config.get(CONF_HOST),
            config.get(CONF_PORT),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            config.get(CONF_IMAP_SECURITY),
            config.get(CONF_VERIFY_SSL),
            config.get("oauth_token"),
            timeout=timeout,
        )
    except InvalidAuth as err:
        _LOGGER.error("Authentication failed: %s", err)
        ir.async_create_issue(
            hass,
            DOMAIN,
            "auth_failed",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="auth_failed",
            data={"entry_id": config_entry.entry_id} if config_entry else None,
        )
        raise ConfigEntryAuthFailed from err
    except Exception as err:
        _LOGGER.error("Error logging into IMAP: %s", err)
        raise UpdateFailed(f"Login failed: {err}") from err

    issue_registry = ir.async_get(hass)
    if (DOMAIN, "auth_failed") in issue_registry.issues:
        ir.async_delete_issue(hass, DOMAIN, "auth_failed")

    folders = config.get(CONF_FOLDER)
    if isinstance(folders, str):
        folders = [folders]
    elif isinstance(folders, (list, tuple, set)):
        folders = [f for f in folders if isinstance(f, str) and f]
    else:
        folders = []
    if not folders:
        folders = ["INBOX"]
    account._folders = folders  # noqa: SLF001
    account._current_folder = None  # noqa: SLF001
    account._exchange_mode = bool(  # noqa: SLF001
        config.get(CONF_EXCHANGE_MODE, DEFAULT_EXCHANGE_MODE)
    )

    if folders:
        try:
            folder_ok = await selectfolder_fn(account, folders[0])
        except Exception as err:
            await logout_fn(account)
            raise UpdateFailed(f"Folder selection failed: {err}") from err

        if not folder_ok:
            _LOGGER.error("Error selecting folder: %s", folders[0])
            await logout_fn(account)
            raise UpdateFailed(f"Folder selection failed: {folders[0]}")

    return account
