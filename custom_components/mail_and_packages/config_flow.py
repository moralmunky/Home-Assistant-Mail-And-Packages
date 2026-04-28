"""Adds config flow for Mail and Packages."""

import contextlib
import logging
import ssl
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aioimaplib import AioImapException
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, selector

from .const import (
    AUTH_TYPE_OAUTH_GOOGLE,
    AUTH_TYPE_OAUTH_MICROSOFT,
    AUTH_TYPE_PASSWORD,
    CONF_ALLOW_EXTERNAL,
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_AUTH_TYPE,
    CONF_CUSTOM_DAYS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FOLDER,
    CONF_FORWARDED_EMAILS,
    CONF_FORWARDING_HEADER,
    CONF_GENERATE_GRID,
    CONF_GENERATE_MP4,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_VERIFY_SSL,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    CONFIG_VER,
    DEFAULT_ALLOW_EXTERNAL,
    DEFAULT_ALLOW_FORWARDED_EMAILS,
    DEFAULT_AMAZON_CUSTOM_IMG,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_AMAZON_DOMAIN,
    DEFAULT_AMAZON_FWDS,
    DEFAULT_CUSTOM_DAYS,
    DEFAULT_CUSTOM_IMG,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FEDEX_CUSTOM_IMG,
    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
    DEFAULT_FOLDER,
    DEFAULT_FORWARDED_EMAILS,
    DEFAULT_FORWARDING_HEADER,
    DEFAULT_GENERIC_CUSTOM_IMG,
    DEFAULT_GENERIC_CUSTOM_IMG_FILE,
    DEFAULT_GIF_DURATION,
    DEFAULT_IMAGE_SECURITY,
    DEFAULT_IMAP_TIMEOUT,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STORAGE,
    DEFAULT_UPS_CUSTOM_IMG,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
    DOMAIN,
    OAUTH_IMAP_DEFAULTS,
    OAUTH_SCOPES,
)
from .helpers import get_resources
from .utils.email import generate_service_email_domains, validate_email_address
from .utils.image import _check_ffmpeg
from .utils.imap import InvalidAuth, login, logout

ERROR_MAILBOX_FAIL = "Problem getting mailbox listing using 'INBOX' message"
IMAP_SECURITY = ["none", "SSL"]
AMAZON_SENSORS = ["amazon_packages", "amazon_delivered", "amazon_exception"]
_LOGGER = logging.getLogger(__name__)
AMAZON_EMAIL_ERROR = (
    "Amazon domain found in email: %s, this may cause errors when searching emails."
)
FORWARDED_EMAIL_ERROR = "A service domain was found in email: %s, this may cause errors when searching emails."  # pylint: disable=line-too-long


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
    """Validate forwarded email addresses provided by the user.

    Use Voluptuous to make sure that none of the forwarded email addresses use domains
    that match any of the Mail service domains, as this was known to cause issues when
    searching for Amazon emails.

    Args:
        user_input (dict[str, Any]): The user input dictionary.

    Returns:
        list[str]: A list of error codes (e.g. "missing_forwarded_emails") or "ok" if the
                   email addresses are valid

    """
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
        if not validate_email_address(email):
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


def _validate_path_input(user_input: dict, errors: dict) -> None:
    """Validate path and file inputs."""
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
    ]

    for toggle, file_key, error_key in file_checks:
        if user_input.get(toggle) and file_key in user_input:
            if not Path(user_input[file_key]).is_file():
                errors[error_key] = "file_not_found"

    if CONF_STORAGE in user_input:
        if not Path(user_input[CONF_STORAGE]).exists():
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


async def _validate_user_input(user_input: dict) -> tuple:
    """Validate user input from config flow.

    Returns tuple with error messages and modified user_input
    """
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
    if user_input[CONF_GENERATE_MP4]:
        if not await _check_ffmpeg():
            errors[CONF_GENERATE_MP4] = "ffmpeg_not_found"

    # Validate file paths
    _validate_path_input(user_input, errors)

    return errors, user_input


async def _get_mailboxes(
    hass: HomeAssistant,
    host: str,
    port: int,
    user: str,
    pwd: str,
    security: str,
    verify: bool,
    oauth_token: str | None = None,
) -> list:
    """Get list of mailbox folders from mail server."""
    _LOGGER.debug("Getting mailboxes, login...")
    try:
        account = await login(
            hass,
            host,
            port,
            user,
            pwd,
            security,
            verify,
            oauth_token=oauth_token,
        )

    except (TimeoutError, AioImapException, ConnectionRefusedError) as err:
        _LOGGER.error("Unable to connect: %s", err)
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
        await logout(account)

    return mailboxes


async def _parse_folder_list(folderlist: list) -> list:
    """Parse folder list from IMAP server response."""
    mailboxes = []
    with contextlib.suppress(IndexError):
        mailboxes.extend(i.decode().split(' "/" ')[1] for i in folderlist)

    with contextlib.suppress(IndexError):
        mailboxes.extend(i.decode().split(' "." ')[1] for i in folderlist)

    if len(mailboxes) == 0:
        _LOGGER.error("Problem reading mailbox folders, using default.")
        mailboxes.append(DEFAULT_FOLDER)

    return mailboxes


def _get_schema_auth(user_input: list, default_dict: list) -> Any:
    """Get the first schema for auth type."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_AUTH_TYPE,
                default=_get_default(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=AUTH_TYPE_PASSWORD,
                            label="Password",
                        ),
                        selector.SelectOptionDict(
                            value=AUTH_TYPE_OAUTH_MICROSOFT,
                            label="OAuth2 - Microsoft (Outlook/Exchange)",
                        ),
                        selector.SelectOptionDict(
                            value=AUTH_TYPE_OAUTH_GOOGLE,
                            label="OAuth2 - Google (Gmail)",
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="auth_type",
                ),
            ),
        },
    )


def _get_schema_imap(user_input: list, default_dict: list) -> Any:
    """Get the secondary schema for IMAP configuration."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        return user_input.get(key, default_dict.get(key, fallback_default))

    # Determine if password field should be shown based on chosen auth_type
    auth_type = _get_default(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
    schema = {
        vol.Required(CONF_HOST, default=_get_default(CONF_HOST)): cv.string,
        vol.Required(CONF_PORT, default=_get_default(CONF_PORT, 993)): cv.port,
        vol.Required(CONF_USERNAME, default=_get_default(CONF_USERNAME)): cv.string,
    }

    if auth_type == AUTH_TYPE_PASSWORD:
        schema[vol.Required(CONF_PASSWORD, default=_get_default(CONF_PASSWORD, ""))] = (
            cv.string
        )

    schema.update(
        {
            vol.Required(
                CONF_IMAP_SECURITY,
                default=_get_default(CONF_IMAP_SECURITY),
            ): vol.In(IMAP_SECURITY),
            vol.Optional(
                CONF_VERIFY_SSL,
                default=_get_default(CONF_VERIFY_SSL, False),
            ): cv.boolean,
        },
    )

    return vol.Schema(schema)


async def _get_schema_step_2(
    data: list,
    user_input: list,
    default_dict: list,
    hass: HomeAssistant,
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_FOLDER, default=_get_default(CONF_FOLDER)): vol.In(
                await _get_mailboxes(
                    hass,
                    data[CONF_HOST],
                    data[CONF_PORT],
                    data[CONF_USERNAME],
                    data.get(CONF_PASSWORD, ""),
                    data[CONF_IMAP_SECURITY],
                    data[CONF_VERIFY_SSL],
                    data.get("token", {}).get("access_token"),
                ),
            ),
            vol.Required(
                CONF_RESOURCES,
                default=_get_default(CONF_RESOURCES),
            ): cv.multi_select(get_resources()),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=_get_default(CONF_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5)),
            vol.Optional(
                CONF_CUSTOM_DAYS,
                default=_get_default(CONF_CUSTOM_DAYS, DEFAULT_CUSTOM_DAYS),
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                CONF_IMAP_TIMEOUT,
                default=_get_default(CONF_IMAP_TIMEOUT),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(
                CONF_DURATION,
                default=_get_default(CONF_DURATION),
            ): vol.Coerce(int),
            vol.Optional(
                CONF_ALLOW_FORWARDED_EMAILS,
                default=_get_default(CONF_ALLOW_FORWARDED_EMAILS, False),
            ): cv.boolean,
            vol.Optional(
                CONF_GENERATE_GRID,
                default=_get_default(CONF_GENERATE_GRID, False),
            ): cv.boolean,
            vol.Optional(
                CONF_GENERATE_MP4,
                default=_get_default(CONF_GENERATE_MP4, False),
            ): cv.boolean,
            vol.Optional(
                CONF_ALLOW_EXTERNAL,
                default=_get_default(CONF_ALLOW_EXTERNAL, False),
            ): cv.boolean,
            vol.Optional(
                CONF_CUSTOM_IMG,
                default=_get_default(CONF_CUSTOM_IMG, False),
            ): cv.boolean,
            vol.Optional(
                CONF_AMAZON_CUSTOM_IMG,
                default=_get_default(CONF_AMAZON_CUSTOM_IMG, False),
            ): cv.boolean,
            vol.Optional(
                CONF_UPS_CUSTOM_IMG,
                default=_get_default(CONF_UPS_CUSTOM_IMG, False),
            ): cv.boolean,
            vol.Optional(
                CONF_WALMART_CUSTOM_IMG,
                default=_get_default(CONF_WALMART_CUSTOM_IMG, False),
            ): cv.boolean,
            vol.Optional(
                CONF_FEDEX_CUSTOM_IMG,
                default=_get_default(CONF_FEDEX_CUSTOM_IMG, False),
            ): cv.boolean,
            vol.Optional(
                CONF_GENERIC_CUSTOM_IMG,
                default=_get_default(CONF_GENERIC_CUSTOM_IMG, False),
            ): cv.boolean,
        },
    )


def _get_schema_step_3(user_input: dict, default_dict: dict) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> str:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    schema = {}

    # Only show custom image file field if custom image is enabled
    if user_input.get(CONF_CUSTOM_IMG):
        schema[
            vol.Optional(
                CONF_CUSTOM_IMG_FILE,
                default=_get_default(CONF_CUSTOM_IMG_FILE, DEFAULT_CUSTOM_IMG_FILE),
            )
        ] = cv.string

    # Only show Amazon custom image file field if Amazon custom image is enabled
    if user_input.get(CONF_AMAZON_CUSTOM_IMG):
        schema[
            vol.Optional(
                CONF_AMAZON_CUSTOM_IMG_FILE,
                default=_get_default(
                    CONF_AMAZON_CUSTOM_IMG_FILE,
                    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
                ),
            )
        ] = cv.string

    # Only show UPS custom image file field if UPS custom image is enabled
    if user_input.get(CONF_UPS_CUSTOM_IMG):
        schema[
            vol.Optional(
                CONF_UPS_CUSTOM_IMG_FILE,
                default=_get_default(
                    CONF_UPS_CUSTOM_IMG_FILE,
                    DEFAULT_UPS_CUSTOM_IMG_FILE,
                ),
            )
        ] = cv.string

    # Only show Walmart custom image file field if Walmart custom image is enabled
    if user_input.get(CONF_WALMART_CUSTOM_IMG):
        schema[
            vol.Optional(
                CONF_WALMART_CUSTOM_IMG_FILE,
                default=_get_default(
                    CONF_WALMART_CUSTOM_IMG_FILE,
                    DEFAULT_WALMART_CUSTOM_IMG_FILE,
                ),
            )
        ] = cv.string

    # Only show FedEx custom image file field if FedEx custom image is enabled
    if user_input.get(CONF_FEDEX_CUSTOM_IMG):
        schema[
            vol.Optional(
                CONF_FEDEX_CUSTOM_IMG_FILE,
                default=_get_default(
                    CONF_FEDEX_CUSTOM_IMG_FILE,
                    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
                ),
            )
        ] = cv.string

    # Only show Generic custom image file field if Generic custom image is enabled
    if user_input.get(CONF_GENERIC_CUSTOM_IMG):
        schema[
            vol.Optional(
                CONF_GENERIC_CUSTOM_IMG_FILE,
                default=_get_default(
                    CONF_GENERIC_CUSTOM_IMG_FILE,
                    DEFAULT_GENERIC_CUSTOM_IMG_FILE,
                ),
            )
        ] = cv.string

    return vol.Schema(schema)


def _get_schema_step_amazon(
    user_input: list,
    default_dict: list,
    forwarding_header: str = "",
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    schema_dict: dict = {
        vol.Required(
            CONF_AMAZON_DOMAIN,
            default=_get_default(CONF_AMAZON_DOMAIN),
        ): cv.string,
    }

    if not forwarding_header or forwarding_header == "(none)":
        schema_dict[
            vol.Optional(
                CONF_AMAZON_FWDS,
                default=_get_default(CONF_AMAZON_FWDS),
            )
        ] = cv.string

    schema_dict[
        vol.Optional(CONF_AMAZON_DAYS, default=_get_default(CONF_AMAZON_DAYS))
    ] = int

    return vol.Schema(schema_dict)


def _get_schema_step_forwarded_emails(
    user_input: list,
    default_dict: list,
) -> vol.Schema:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> list:
        """Get default value for key."""
        value = user_input.get(key, default_dict.get(key, fallback_default))
        if isinstance(value, list):
            value = ", ".join(value)
        return value

    return vol.Schema(
        {
            vol.Optional(
                CONF_FORWARDING_HEADER,
                default=_get_default(CONF_FORWARDING_HEADER, DEFAULT_FORWARDING_HEADER),
            ): cv.string,
            vol.Optional(
                CONF_FORWARDED_EMAILS,
                default=_get_default(CONF_FORWARDED_EMAILS, DEFAULT_FORWARDED_EMAILS),
            ): cv.string,
        },
    )


def _get_schema_step_storage(user_input: dict, default_dict: dict) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(
                CONF_STORAGE,
                default=_get_default(CONF_STORAGE, DEFAULT_STORAGE),
            ): cv.string,
        },
    )


async def _validate_login(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> dict[str, str]:
    """Validate login credentials."""
    errors = {}
    _LOGGER.debug("Testing login...")

    auth_type = user_input.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)

    # Skip login validation for OAuth2 — auth happens via the OAuth flow
    if auth_type != AUTH_TYPE_PASSWORD:
        return errors

    imap_client = None
    try:
        imap_client = await login(
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
    except (TimeoutError, AioImapException, ConnectionRefusedError) as err:
        _LOGGER.error("Unable to connect: %s", err)
        errors["base"] = "cannot_connect"
    else:
        if result != "OK":
            errors["base"] = "missing_inbox"
    finally:
        if imap_client is not None:
            await logout(imap_client)

    return errors


@config_entries.HANDLERS.register(DOMAIN)
class MailAndPackagesFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Config flow for Mail and Packages."""

    VERSION = CONFIG_VER
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
        scopes = OAUTH_SCOPES.get(auth_type, "")
        data = {"scope": scopes}
        if auth_type == AUTH_TYPE_OAUTH_GOOGLE:
            data.update(
                {
                    "access_type": "offline",
                    "prompt": "consent",
                }
            )
        return data

    def __init__(self):
        """Initialize."""
        super().__init__()
        self._entry = None
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_imap_config()

        return await self._show_auth_form(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._data.update(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        self._errors = {}
        auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)

        if user_input is not None:
            self._data.update(user_input)
            if auth_type != AUTH_TYPE_PASSWORD:
                return await self.async_step_pick_implementation()

            self._errors = await _validate_login(self.hass, self._data)
            if not self._errors:
                return self.async_update_reload_and_abort(
                    self._entry,
                    data=self._data,
                )

        if auth_type != AUTH_TYPE_PASSWORD:
            return self.async_show_form(step_id="reauth_confirm")

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=self._data.get(CONF_USERNAME)): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=self._errors
        )

    async def async_step_imap_config(self, user_input=None):
        """Handle IMAP config step after auth selection."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)

            if auth_type != AUTH_TYPE_PASSWORD:
                # OAuth2 flow: store provider and auto-fill IMAP defaults
                self._data[CONF_VERIFY_SSL] = True
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN]["oauth_provider"] = auth_type
                return await self.async_step_pick_implementation()

            # Password flow: validate login
            self._errors = await _validate_login(
                self.hass,
                self._data,
            )
            if self._errors == {}:
                return await self.async_step_config_2()

            return await self._show_imap_form(user_input)

        return await self._show_imap_form(user_input)

    async def async_oauth_create_entry(
        self,
        data: dict,
    ) -> config_entries.ConfigFlowResult:
        """Handle OAuth2 completion — store token and continue to step 2."""
        self._data.update(data)
        if self._entry:
            if self.source == config_entries.SOURCE_REAUTH:
                return self.async_update_reload_and_abort(
                    self._entry,
                    data=self._data,
                )
            return await self.async_step_reconfig_2()
        return await self.async_step_config_2()

    async def _show_auth_form(self, user_input):
        """Show the authentication form."""
        defaults = {CONF_AUTH_TYPE: AUTH_TYPE_PASSWORD}
        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema_auth(user_input, defaults),
            errors=self._errors,
        )

    async def _show_imap_form(self, user_input):
        """Show the configuration form to edit IMAP configuration data."""
        auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
        defaults = OAUTH_IMAP_DEFAULTS.get(
            auth_type,
            {
                CONF_PORT: DEFAULT_PORT,
                CONF_IMAP_SECURITY: "SSL",
                CONF_VERIFY_SSL: False,
            },
        )
        defaults[CONF_AUTH_TYPE] = auth_type

        return self.async_show_form(
            step_id="imap_config",
            data_schema=_get_schema_imap(user_input, defaults),
            errors=self._errors,
        )

    async def async_step_config_2(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            _LOGGER.debug("RESOURCES: %s", self._data[CONF_RESOURCES])
            if len(self._errors) == 0:
                if self._data[CONF_ALLOW_FORWARDED_EMAILS]:
                    return await self.async_step_config_forwarded_emails()
                if any(
                    sensor in self._data[CONF_RESOURCES] for sensor in AMAZON_SENSORS
                ):
                    return await self.async_step_config_amazon()
                has_custom_image = (
                    self._data.get(CONF_CUSTOM_IMG)
                    or self._data.get(CONF_AMAZON_CUSTOM_IMG)
                    or self._data.get(CONF_UPS_CUSTOM_IMG)
                    or self._data.get(CONF_WALMART_CUSTOM_IMG)
                    or self._data.get(CONF_FEDEX_CUSTOM_IMG)
                    or self._data.get(CONF_GENERIC_CUSTOM_IMG)
                )
                if has_custom_image:
                    return await self.async_step_config_3()

                return self.async_create_entry(
                    title=self._data[CONF_HOST],
                    data=self._data,
                )
            return await self._show_config_2(user_input)

        return await self._show_config_2(user_input)

    async def _show_config_2(self, user_input):
        """Step 2 setup."""
        # Defaults
        defaults = {
            CONF_FOLDER: DEFAULT_FOLDER,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_CUSTOM_DAYS: DEFAULT_CUSTOM_DAYS,
            CONF_PATH: self.hass.config.path() + DEFAULT_PATH,
            CONF_DURATION: DEFAULT_GIF_DURATION,
            CONF_IMAGE_SECURITY: DEFAULT_IMAGE_SECURITY,
            CONF_IMAP_TIMEOUT: DEFAULT_IMAP_TIMEOUT,
            CONF_GENERATE_GRID: False,
            CONF_GENERATE_MP4: False,
            CONF_ALLOW_EXTERNAL: DEFAULT_ALLOW_EXTERNAL,
            CONF_CUSTOM_IMG: DEFAULT_CUSTOM_IMG,
            CONF_AMAZON_CUSTOM_IMG: DEFAULT_AMAZON_CUSTOM_IMG,
            CONF_UPS_CUSTOM_IMG: DEFAULT_UPS_CUSTOM_IMG,
            CONF_WALMART_CUSTOM_IMG: DEFAULT_WALMART_CUSTOM_IMG,
            CONF_FEDEX_CUSTOM_IMG: DEFAULT_FEDEX_CUSTOM_IMG,
            CONF_GENERIC_CUSTOM_IMG: DEFAULT_GENERIC_CUSTOM_IMG,
            CONF_ALLOW_FORWARDED_EMAILS: DEFAULT_ALLOW_FORWARDED_EMAILS,
        }

        return self.async_show_form(
            step_id="config_2",
            data_schema=await _get_schema_step_2(
                self._data,
                user_input,
                defaults,
                self.hass,
            ),
            errors=self._errors,
        )

    async def async_step_config_3(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return await self.async_step_config_storage()
            return await self._show_config_3(user_input)

        return await self._show_config_3(user_input)

    async def _show_config_3(self, user_input=None):  # pylint: disable=unused-argument
        """Step 3 setup."""
        # Defaults
        defaults = {
            CONF_CUSTOM_IMG_FILE: DEFAULT_CUSTOM_IMG_FILE,
            CONF_AMAZON_CUSTOM_IMG_FILE: DEFAULT_AMAZON_CUSTOM_IMG_FILE,
            CONF_UPS_CUSTOM_IMG_FILE: DEFAULT_UPS_CUSTOM_IMG_FILE,
            CONF_WALMART_CUSTOM_IMG_FILE: DEFAULT_WALMART_CUSTOM_IMG_FILE,
            CONF_FEDEX_CUSTOM_IMG_FILE: DEFAULT_FEDEX_CUSTOM_IMG_FILE,
            CONF_GENERIC_CUSTOM_IMG_FILE: DEFAULT_GENERIC_CUSTOM_IMG_FILE,
        }

        return self.async_show_form(
            step_id="config_3",
            data_schema=_get_schema_step_3(self._data, defaults),
            errors=self._errors,
        )

    async def async_step_config_amazon(self, user_input=None):
        """Configure form step amazon."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                if (
                    self._data.get(CONF_CUSTOM_IMG)
                    or self._data.get(CONF_AMAZON_CUSTOM_IMG)
                    or self._data.get(CONF_UPS_CUSTOM_IMG)
                    or self._data.get(CONF_WALMART_CUSTOM_IMG)
                    or self._data.get(CONF_GENERIC_CUSTOM_IMG)
                ):
                    return await self.async_step_config_3()
                return await self.async_step_config_storage()

            return await self._show_config_amazon(user_input)

        return await self._show_config_amazon(user_input)

    async def _show_config_amazon(self, user_input):
        """Step 3 setup."""
        # Defaults
        defaults = {
            CONF_AMAZON_DOMAIN: DEFAULT_AMAZON_DOMAIN,
            CONF_AMAZON_FWDS: DEFAULT_AMAZON_FWDS,
            CONF_AMAZON_DAYS: DEFAULT_AMAZON_DAYS,
        }

        return self.async_show_form(
            step_id="config_amazon",
            data_schema=_get_schema_step_amazon(
                user_input,
                defaults,
                forwarding_header=self._data.get(CONF_FORWARDING_HEADER, ""),
            ),
            errors=self._errors,
        )

    async def async_step_config_forwarded_emails(self, user_input=None):
        """Configure form step forwarded emails."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                if any(
                    sensor in self._data[CONF_RESOURCES] for sensor in AMAZON_SENSORS
                ):
                    return await self.async_step_config_amazon()
                if self._data[CONF_CUSTOM_IMG]:
                    return await self.async_step_config_3()

                return await self.async_step_config_storage()

            return await self._show_config_forwarded_emails(user_input)

        return await self._show_config_forwarded_emails(user_input)

    async def _show_config_forwarded_emails(self, user_input):
        """Configure forwarded emails setup."""
        # Defaults
        defaults = {
            CONF_FORWARDED_EMAILS: DEFAULT_FORWARDED_EMAILS,
        }

        return self.async_show_form(
            step_id="config_forwarded_emails",
            data_schema=_get_schema_step_forwarded_emails(user_input, defaults),
            errors=self._errors,
        )

    async def async_step_config_storage(self, user_input=None):
        """Configure form step storage."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return self.async_create_entry(
                    title=self._data[CONF_HOST],
                    data=self._data,
                )
            return await self._show_config_storage(user_input)

        return await self._show_config_storage(user_input)

    async def _show_config_storage(self, user_input):
        """Step 3 setup."""
        # Defaults
        defaults = {
            CONF_STORAGE: DEFAULT_STORAGE,
        }

        return self.async_show_form(
            step_id="config_storage",
            data_schema=_get_schema_step_storage(user_input, defaults),
            errors=self._errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Add reconfigure step to allow to reconfigure a config entry."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert self._entry
        self._data = dict(self._entry.data)
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_reconfig_imap()

        return await self._show_reconfig_auth_form(user_input)

    async def async_step_reconfig_imap(self, user_input=None):
        """Handle IMAP step for reconfigure."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)

            if auth_type != AUTH_TYPE_PASSWORD:
                self._data[CONF_VERIFY_SSL] = True
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN]["oauth_provider"] = auth_type
                return await self.async_step_pick_implementation()

            self._errors = await _validate_login(self.hass, self._data)
            if self._errors == {}:
                return await self.async_step_reconfig_2()

            return await self._show_reconfig_imap_form(user_input)

        return await self._show_reconfig_imap_form(user_input)

    async def _show_reconfig_auth_form(self, user_input):
        """Show the auth form for reconfigure."""
        defaults = {
            CONF_AUTH_TYPE: self._entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_schema_auth(user_input, defaults),
            errors=self._errors,
        )

    async def _show_reconfig_imap_form(self, user_input):
        """Show the configuration form to edit IMAP data."""
        auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
        defaults = OAUTH_IMAP_DEFAULTS.get(
            auth_type,
            {
                CONF_PORT: self._entry.data.get(CONF_PORT, DEFAULT_PORT),
                CONF_IMAP_SECURITY: self._entry.data.get(CONF_IMAP_SECURITY, "SSL"),
                CONF_VERIFY_SSL: self._entry.data.get(CONF_VERIFY_SSL, False),
            },
        )

        defaults[CONF_HOST] = self._entry.data.get(CONF_HOST, defaults.get(CONF_HOST))
        defaults[CONF_USERNAME] = self._entry.data.get(
            CONF_USERNAME,
            defaults.get(CONF_USERNAME),
        )
        defaults[CONF_PASSWORD] = self._entry.data.get(
            CONF_PASSWORD,
            defaults.get(CONF_PASSWORD),
        )
        defaults[CONF_AUTH_TYPE] = auth_type

        return self.async_show_form(
            step_id="reconfig_imap",
            data_schema=_get_schema_imap(user_input, defaults),
            errors=self._errors,
        )

    async def async_step_reconfig_2(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        _LOGGER.debug("Loading step 2...")
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(user_input)
            if len(self._errors) == 0:
                if self._data.get(CONF_ALLOW_FORWARDED_EMAILS, False):
                    return await self.async_step_reconfig_forwarded_emails()

                if any(
                    sensor in self._data.get(CONF_RESOURCES, [])
                    for sensor in AMAZON_SENSORS
                ):
                    return await self.async_step_reconfig_amazon()
                has_custom_image = (
                    self._data.get(CONF_CUSTOM_IMG)
                    or self._data.get(CONF_AMAZON_CUSTOM_IMG)
                    or self._data.get(CONF_UPS_CUSTOM_IMG)
                    or self._data.get(CONF_WALMART_CUSTOM_IMG)
                    or self._data.get(CONF_FEDEX_CUSTOM_IMG)
                    or self._data.get(CONF_GENERIC_CUSTOM_IMG)
                )
                if has_custom_image:
                    return await self.async_step_reconfig_3()

                return await self.async_step_reconfig_storage()

            return await self._show_reconfig_2(user_input)

        return await self._show_reconfig_2(user_input)

    async def _show_reconfig_2(self, user_input):
        """Step 2 setup."""
        return self.async_show_form(
            step_id="reconfig_2",
            data_schema=await _get_schema_step_2(
                self._data,
                user_input,
                self._data,
                self.hass,
            ),
            errors=self._errors,
        )

    async def async_step_reconfig_3(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return await self.async_step_reconfig_storage()

            return await self._show_reconfig_3(user_input)

        return await self._show_reconfig_3(user_input)

    async def _show_reconfig_3(self, user_input=None):  # pylint: disable=unused-argument
        """Step 3 setup."""
        # Defaults
        defaults = {
            CONF_CUSTOM_IMG_FILE: DEFAULT_CUSTOM_IMG_FILE,
            CONF_AMAZON_CUSTOM_IMG_FILE: DEFAULT_AMAZON_CUSTOM_IMG_FILE,
            CONF_UPS_CUSTOM_IMG_FILE: DEFAULT_UPS_CUSTOM_IMG_FILE,
            CONF_WALMART_CUSTOM_IMG_FILE: DEFAULT_WALMART_CUSTOM_IMG_FILE,
            CONF_FEDEX_CUSTOM_IMG_FILE: DEFAULT_FEDEX_CUSTOM_IMG_FILE,
            CONF_GENERIC_CUSTOM_IMG_FILE: DEFAULT_GENERIC_CUSTOM_IMG_FILE,
        }

        return self.async_show_form(
            step_id="reconfig_3",
            data_schema=_get_schema_step_3(self._data, defaults),
            errors=self._errors,
        )

    async def async_step_reconfig_amazon(self, user_input=None):
        """Configure form step amazon."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                has_custom_image = (
                    self._data.get(CONF_CUSTOM_IMG)
                    or self._data.get(CONF_AMAZON_CUSTOM_IMG)
                    or self._data.get(CONF_UPS_CUSTOM_IMG)
                    or self._data.get(CONF_WALMART_CUSTOM_IMG)
                    or self._data.get(CONF_FEDEX_CUSTOM_IMG)
                    or self._data.get(CONF_GENERIC_CUSTOM_IMG)
                )
                if has_custom_image:
                    return await self.async_step_reconfig_3()

                return await self.async_step_reconfig_storage()

            return await self._show_reconfig_amazon(user_input)

        return await self._show_reconfig_amazon(user_input)

    async def _show_reconfig_amazon(self, user_input):
        """Step 3 setup."""
        if self._data.get(CONF_AMAZON_FWDS, []) == []:
            self._data[CONF_AMAZON_FWDS] = "(none)"

        return self.async_show_form(
            step_id="reconfig_amazon",
            data_schema=_get_schema_step_amazon(
                user_input,
                self._data,
                forwarding_header=self._data.get(CONF_FORWARDING_HEADER, ""),
            ),
            errors=self._errors,
        )

    async def async_step_reconfig_forwarded_emails(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Configure form step forwarded emails."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                if any(
                    sensor in self._data.get(CONF_RESOURCES, [])
                    for sensor in AMAZON_SENSORS
                ):
                    return await self.async_step_reconfig_amazon()
                if self._data.get(CONF_CUSTOM_IMG, False):
                    return await self.async_step_reconfig_3()
                return await self.async_step_reconfig_storage()
            return await self._show_reconfig_forwarded_emails(user_input)
        return await self._show_reconfig_forwarded_emails(user_input)

    async def _show_reconfig_forwarded_emails(self, user_input=None):
        """Step forwarded emails."""
        if self._data.get(CONF_FORWARDED_EMAILS, []) == []:
            self._data[CONF_FORWARDED_EMAILS] = "(none)"

        return self.async_show_form(
            step_id="reconfig_forwarded_emails",
            data_schema=_get_schema_step_forwarded_emails(user_input, self._data),
            errors=self._errors,
        )

    async def async_step_reconfig_storage(self, user_input=None):
        """Configure form step storage."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data=self._data,
                )
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                _LOGGER.debug("%s reconfigured.", DOMAIN)
                return self.async_abort(reason="reconfigure_successful")

            return await self._show_reconfig_storage(user_input)

        return await self._show_reconfig_storage(user_input)

    async def _show_reconfig_storage(self, user_input):
        """Step 3 setup."""
        return self.async_show_form(
            step_id="reconfig_storage",
            data_schema=_get_schema_step_storage(user_input, self._data),
            errors=self._errors,
        )
