"""Validation functions and mailbox utilities for Mail and Packages config flow."""

from __future__ import annotations

import logging
import sys
from pathlib import Path as DefaultPath
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.mail_and_packages.const import (
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FOLDER,
    CONF_FORWARDED_EMAILS,
    CONF_FORWARDING_HEADER,
    CONF_GENERATE_MP4,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
)
from custom_components.mail_and_packages.utils.email import (
    generate_service_email_domains,
)
from custom_components.mail_and_packages.utils.email import (
    validate_email_address as default_val_email,
)
from custom_components.mail_and_packages.utils.image import (
    _check_ffmpeg as default_check_ffmpeg,
)

_LOGGER = logging.getLogger(__name__)

ERROR_MAILBOX_FAIL = "Problem getting mailbox listing using 'INBOX' message"
AMAZON_EMAIL_ERROR = (
    "Amazon domain found in email: %s, this may cause errors when searching emails."
)
FORWARDED_EMAIL_ERROR = "A service domain was found in email: %s, this may cause errors when searching emails."  # pylint: disable=line-too-long


def _get_target(symbol_name: str, fallback_callable: Any) -> Any:
    """Dynamically get symbol from config_flow module if imported/patched there."""
    cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
    if cf and hasattr(cf, symbol_name):
        return getattr(cf, symbol_name)
    return fallback_callable


async def _check_amazon_forwards(forwards: str, domain: str) -> tuple:
    """Validate and format amazon forward emails for user input.

    Returns tuple: dict of errors, list of email addresses
    """
    emails = forwards.split(",")
    errors = []

    # Validate each email address
    for email in emails:
        email = email.strip()

        if "@" in email:
            # Check for amazon domains
            if f"@{domain}" in email:
                _LOGGER.error(
                    AMAZON_EMAIL_ERROR,
                    email,
                )

        # No forwards
        elif forwards in ["", "(none)", '""']:
            forwards = []

        else:
            _LOGGER.error("Missing '@' in email address: %s", email)
            errors.append("invalid_email_format")

    if len(errors) == 0:
        errors.append("ok")

    return errors, forwards


async def _check_forwarded_emails(user_input: dict[str, Any]) -> list[str]:
    """Validate forwarded email addresses provided by the user."""
    validate_email = _get_target("validate_email_address", default_val_email)

    forwarded_emails = user_input[CONF_FORWARDED_EMAILS]

    _LOGGER.debug("checking forwarded emails: '%s'", forwarded_emails)

    # No forwards
    if not forwarded_emails:
        _LOGGER.error(
            "Allowed forwarded emails but no forwards or '(none)' were entered.",
        )
        return ["missing_forwarded_emails"]
    if forwarded_emails == "(none)":
        return ["ok"]

    errors = []

    service_email_domains = generate_service_email_domains(
        user_input.get(CONF_AMAZON_FWDS, []),
    )

    emails = [email.strip() for email in forwarded_emails.split(",")]
    for email in emails:
        _LOGGER.debug("validating email address %s", email)
        if not validate_email(email):
            _LOGGER.error("%s does not look like a valid email address", email)
            errors.append("invalid_email_format")
            continue

        domain = email.split("@")[1]
        if domain in service_email_domains:
            _LOGGER.error(
                FORWARDED_EMAIL_ERROR,
                email,
            )
    if len(errors) == 0:
        return ["ok"]

    return errors


def _validate_path_input(
    user_input: dict, errors: dict, hass: HomeAssistant | None = None
) -> None:
    """Validate path and file inputs."""
    path_cls = _get_target("Path", DefaultPath)

    # List of (Toggle Key, File Key, Error Key)
    file_checks = [
        (CONF_CUSTOM_IMG, CONF_CUSTOM_IMG_FILE, CONF_CUSTOM_IMG_FILE),
        (
            CONF_AMAZON_CUSTOM_IMG,
            CONF_AMAZON_CUSTOM_IMG_FILE,
            CONF_AMAZON_CUSTOM_IMG_FILE,
        ),
        (CONF_UPS_CUSTOM_IMG, CONF_UPS_CUSTOM_IMG_FILE, CONF_UPS_CUSTOM_IMG_FILE),
        (
            CONF_WALMART_CUSTOM_IMG,
            CONF_WALMART_CUSTOM_IMG_FILE,
            CONF_WALMART_CUSTOM_IMG_FILE,
        ),
        (
            CONF_FEDEX_CUSTOM_IMG,
            CONF_FEDEX_CUSTOM_IMG_FILE,
            CONF_FEDEX_CUSTOM_IMG_FILE,
        ),
        (
            CONF_GENERIC_CUSTOM_IMG,
            CONF_GENERIC_CUSTOM_IMG_FILE,
            CONF_GENERIC_CUSTOM_IMG_FILE,
        ),
        (
            CONF_POST_DE_CUSTOM_IMG,
            CONF_POST_DE_CUSTOM_IMG_FILE,
            CONF_POST_DE_CUSTOM_IMG_FILE,
        ),
    ]

    for toggle, file_key, error_key in file_checks:
        if user_input.get(toggle) and file_key in user_input:
            path = user_input[file_key]
            if hass:
                path = hass.config.path(path)
            if not path_cls(path).is_file():
                errors[error_key] = "file_not_found"

    if CONF_STORAGE in user_input:
        path = user_input[CONF_STORAGE]
        if hass:
            path = hass.config.path(path)
        if not path_cls(path).exists():
            errors[CONF_STORAGE] = "path_not_found"


async def _validate_amazon_fwds(user_input: dict, errors: dict) -> None:
    """Validate amazon forwarding email addresses in user_input."""
    if CONF_AMAZON_FWDS not in user_input:
        return
    if not isinstance(user_input[CONF_AMAZON_FWDS], str):
        return
    status, amazon_list = await _check_amazon_forwards(
        user_input[CONF_AMAZON_FWDS],
        user_input[CONF_AMAZON_DOMAIN],
    )
    user_input[CONF_AMAZON_FWDS] = amazon_list
    if status[0] != "ok":
        errors[CONF_AMAZON_FWDS] = status[0]


async def _validate_forwarded_emails(user_input: dict, errors: dict) -> None:
    """Validate forwarded email address list in user_input."""
    if CONF_FORWARDED_EMAILS not in user_input:
        return
    if not isinstance(user_input[CONF_FORWARDED_EMAILS], str):
        return
    status = await _check_forwarded_emails(user_input)
    if status[0] == "ok" and user_input[CONF_FORWARDED_EMAILS] == "(none)":
        # the user changed their mind, remove the flag and config entry
        user_input[CONF_ALLOW_FORWARDED_EMAILS] = False
        del user_input[CONF_FORWARDED_EMAILS]
    elif status[0] == "ok":
        user_input[CONF_FORWARDED_EMAILS] = [
            e.strip() for e in user_input[CONF_FORWARDED_EMAILS].split(",") if e.strip()
        ]
    else:
        errors[CONF_FORWARDED_EMAILS] = status[0]


async def _validate_user_input(
    user_input: dict, hass: HomeAssistant | None = None
) -> tuple:
    """Validate user input from config flow.

    Returns tuple with error messages and modified user_input
    """
    check_ffmpeg = _get_target("_check_ffmpeg", default_check_ffmpeg)

    errors = {}

    await _validate_amazon_fwds(user_input, errors)

    # Check for forwarding header mode first — it takes precedence over address list
    forwarding_header = user_input.get(CONF_FORWARDING_HEADER, "")
    if isinstance(forwarding_header, str):
        forwarding_header = forwarding_header.strip()
    if forwarding_header and forwarding_header not in ("(none)", ""):
        # Header mode: store the header name, clear address list if present
        user_input[CONF_FORWARDING_HEADER] = forwarding_header
        user_input.pop(CONF_FORWARDED_EMAILS, None)
    else:
        # No header provided — clear the key and fall through to address list validation
        user_input.pop(CONF_FORWARDING_HEADER, None)
        await _validate_forwarded_emails(user_input, errors)

    # Check for ffmpeg if option enabled
    if user_input.get(CONF_GENERATE_MP4):
        if not await check_ffmpeg():
            errors[CONF_GENERATE_MP4] = "ffmpeg_not_found"

    # Validate file paths
    _validate_path_input(user_input, errors, hass)

    # Normalize CONF_FOLDER: if it has exactly 1 folder, store as string
    if CONF_FOLDER in user_input:
        folder_val = user_input[CONF_FOLDER]
        if isinstance(folder_val, (list, set, tuple)):
            folder_list = [f for f in folder_val if isinstance(f, str) and f]
            if not folder_list:
                user_input[CONF_FOLDER] = "INBOX"
            elif len(folder_list) == 1:
                user_input[CONF_FOLDER] = folder_list[0]
            else:
                user_input[CONF_FOLDER] = folder_list
        elif not isinstance(folder_val, str) or not folder_val:
            user_input[CONF_FOLDER] = "INBOX"

    return errors, user_input


# Re-export mailbox discovery and login validation functions
from .mailbox import (  # noqa: E402
    _get_mailboxes,
    _parse_folder_list,
    _validate_login,
)

__all__ = [
    "_check_amazon_forwards",
    "_check_forwarded_emails",
    "_get_mailboxes",
    "_parse_folder_list",
    "_validate_amazon_fwds",
    "_validate_forwarded_emails",
    "_validate_login",
    "_validate_path_input",
    "_validate_user_input",
]
