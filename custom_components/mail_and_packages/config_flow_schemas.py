"""Schemas for Mail and Packages config flow."""

from __future__ import annotations

import logging
import sys
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, selector

from .config_flow_mailbox import _get_mailboxes as default_get_mailboxes
from .const import (
    AUTH_TYPE_OAUTH_GOOGLE,
    AUTH_TYPE_OAUTH_MICROSOFT,
    AUTH_TYPE_PASSWORD,
    CONF_ALLOW_EXTERNAL,
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AUTH_TYPE,
    CONF_CUSTOM_DAYS,
    CONF_CUSTOM_IMG,
    CONF_DURATION,
    CONF_EXCHANGE_MODE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FOLDER,
    CONF_GENERATE_GRID,
    CONF_GENERATE_MP4,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_IMAP_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_SCAN_INTERVAL,
    CONF_UPS_CUSTOM_IMG,
    CONF_USPS_PLACEHOLDER,
    CONF_VERIFY_SSL,
    CONF_WALMART_CUSTOM_IMG,
    DEFAULT_CUSTOM_DAYS,
    DEFAULT_EXCHANGE_MODE,
    DEFAULT_USPS_PLACEHOLDER,
    DEFAULT_VERIFY_SSL,
)
from .helpers import get_resources

_LOGGER = logging.getLogger(__name__)

IMAP_SECURITY = ["none", "SSL"]


class multi_folder_select(cv.multi_select):
    """Multi select validator that allows a single string and converts it to a list, stripping quotes."""

    def __call__(self, value: Any) -> list[Any]:
        """Validate and format the folder selection value."""
        if isinstance(value, str):
            value = [value.strip('"')]
        elif isinstance(value, (list, tuple, set)):
            value = [v.strip('"') if isinstance(v, str) else v for v in value]
        return super().__call__(value)


def _get_schema_auth(user_input: list | dict | None, default_dict: dict) -> Any:
    """Get the first schema for auth type."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any:
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
                            value=AUTH_TYPE_PASSWORD, label="Password"
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


def _get_schema_imap(user_input: list | dict | None, default_dict: dict) -> Any:
    """Get the secondary schema for IMAP configuration."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any:
        return user_input.get(key, default_dict.get(key, fallback_default))

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
                CONF_IMAP_SECURITY, default=_get_default(CONF_IMAP_SECURITY)
            ): vol.In(IMAP_SECURITY),
            vol.Optional(
                CONF_VERIFY_SSL,
                default=_get_default(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): cv.boolean,
        }
    )

    return vol.Schema(schema)


def _get_target(symbol_name: str, fallback_callable: Any) -> Any:
    """Dynamically get symbol from config_flow module if imported/patched there."""
    cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
    if cf and hasattr(cf, symbol_name):
        return getattr(cf, symbol_name)
    return fallback_callable


async def _get_schema_step_2(
    data: dict,
    user_input: list | dict | None,
    default_dict: dict,
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry | None = None,
) -> Any:
    get_mailboxes_fn = _get_target("_get_mailboxes", default_get_mailboxes)

    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    oauth_token = None
    auth_type = data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
    uses_oauth = auth_type in (AUTH_TYPE_OAUTH_MICROSOFT, AUTH_TYPE_OAUTH_GOOGLE) or (
        "token" in data or "access_token" in data
    )
    if entry and uses_oauth:
        try:
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    hass, entry
                )
            )
            session = config_entry_oauth2_flow.OAuth2Session(
                hass, entry, implementation
            )
            await session.async_ensure_token_valid()
            oauth_token = session.token.get("access_token")
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error refreshing OAuth token: %s", err)

    if not oauth_token:
        oauth_token = (
            data["token"].get("access_token")
            if "token" in data and isinstance(data["token"], dict)
            else data.get("access_token")
        )

    mailboxes = await get_mailboxes_fn(
        hass,
        data,
        oauth_token=oauth_token,
    )

    default_folder = _get_default(CONF_FOLDER)
    if isinstance(default_folder, str):
        default_folder = [default_folder.strip('"')]
    elif isinstance(default_folder, (list, tuple, set)):
        default_folder = [
            f.strip('"') for f in default_folder if isinstance(f, str) and f
        ]
    else:
        default_folder = []

    default_folder = [f for f in default_folder if f in mailboxes]
    if not default_folder and "INBOX" in mailboxes:
        default_folder = ["INBOX"]

    return _build_step_2_schema(mailboxes, default_folder, _get_default)


def _build_step_2_schema(
    mailboxes: list[str],
    default_folder: list[str],
    get_default: Any,
) -> vol.Schema:
    """Build voluptuous schema for step 2 configuration."""
    return vol.Schema(
        {
            vol.Required(CONF_FOLDER, default=default_folder): multi_folder_select(
                {m: m for m in mailboxes}
            ),
            vol.Required(
                CONF_RESOURCES,
                default=get_default(CONF_RESOURCES),
            ): cv.multi_select(get_resources()),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=get_default(CONF_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5)),
            vol.Optional(
                CONF_CUSTOM_DAYS,
                default=get_default(CONF_CUSTOM_DAYS, DEFAULT_CUSTOM_DAYS),
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                CONF_IMAP_TIMEOUT,
                default=get_default(CONF_IMAP_TIMEOUT),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Optional(
                CONF_DURATION,
                default=get_default(CONF_DURATION),
            ): vol.Coerce(int),
            **{
                vol.Optional(
                    key,
                    default=get_default(key, default_val),
                ): cv.boolean
                for key, default_val in [
                    (CONF_ALLOW_FORWARDED_EMAILS, False),
                    (CONF_EXCHANGE_MODE, DEFAULT_EXCHANGE_MODE),
                    (CONF_GENERATE_GRID, False),
                    (CONF_GENERATE_MP4, False),
                    (CONF_USPS_PLACEHOLDER, DEFAULT_USPS_PLACEHOLDER),
                    (CONF_ALLOW_EXTERNAL, False),
                    (CONF_CUSTOM_IMG, False),
                    (CONF_AMAZON_CUSTOM_IMG, False),
                    (CONF_UPS_CUSTOM_IMG, False),
                    (CONF_WALMART_CUSTOM_IMG, False),
                    (CONF_FEDEX_CUSTOM_IMG, False),
                    (CONF_GENERIC_CUSTOM_IMG, False),
                    (CONF_POST_DE_CUSTOM_IMG, False),
                ]
            },
        },
    )


# Re-export advanced schemas from config_flow_schemas_advanced
from .config_flow_schemas_advanced import (  # noqa: E402
    CUSTOM_IMAGE_CONFIGS,
    _get_schema_step_3,
    _get_schema_step_amazon,
    _get_schema_step_forwarded_emails,
    _get_schema_step_storage,
)

__all__ = [
    "CUSTOM_IMAGE_CONFIGS",
    "IMAP_SECURITY",
    "_build_step_2_schema",
    "_get_schema_auth",
    "_get_schema_imap",
    "_get_schema_step_2",
    "_get_schema_step_3",
    "_get_schema_step_amazon",
    "_get_schema_step_forwarded_emails",
    "_get_schema_step_storage",
    "multi_folder_select",
]
