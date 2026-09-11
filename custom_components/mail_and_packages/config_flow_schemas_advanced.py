"""Advanced step schemas (Amazon, forwarded emails, custom images, storage) for config flow."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers import selector

from .const import (
    AMAZON_DOMAINS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FORWARDED_EMAILS,
    CONF_FORWARDING_HEADER,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_DOMAIN,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
    DEFAULT_FORWARDED_EMAILS,
    DEFAULT_FORWARDING_HEADER,
    DEFAULT_GENERIC_CUSTOM_IMG_FILE,
    DEFAULT_POST_DE_CUSTOM_IMG_FILE,
    DEFAULT_STORAGE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
)

CUSTOM_IMAGE_CONFIGS = [
    (CONF_CUSTOM_IMG, CONF_CUSTOM_IMG_FILE, DEFAULT_CUSTOM_IMG_FILE),
    (
        CONF_AMAZON_CUSTOM_IMG,
        CONF_AMAZON_CUSTOM_IMG_FILE,
        DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    ),
    (CONF_UPS_CUSTOM_IMG, CONF_UPS_CUSTOM_IMG_FILE, DEFAULT_UPS_CUSTOM_IMG_FILE),
    (
        CONF_WALMART_CUSTOM_IMG,
        CONF_WALMART_CUSTOM_IMG_FILE,
        DEFAULT_WALMART_CUSTOM_IMG_FILE,
    ),
    (CONF_FEDEX_CUSTOM_IMG, CONF_FEDEX_CUSTOM_IMG_FILE, DEFAULT_FEDEX_CUSTOM_IMG_FILE),
    (
        CONF_GENERIC_CUSTOM_IMG,
        CONF_GENERIC_CUSTOM_IMG_FILE,
        DEFAULT_GENERIC_CUSTOM_IMG_FILE,
    ),
    (
        CONF_POST_DE_CUSTOM_IMG,
        CONF_POST_DE_CUSTOM_IMG_FILE,
        DEFAULT_POST_DE_CUSTOM_IMG_FILE,
    ),
]


def _get_schema_step_3(user_input: dict, default_dict: dict) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> str:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    schema = {}
    for flag, field, default in CUSTOM_IMAGE_CONFIGS:
        if user_input.get(flag):
            schema[vol.Optional(field, default=_get_default(field, default))] = (
                cv.string
            )

    return vol.Schema(schema)


def _get_schema_step_amazon(
    user_input: list | dict | None,
    default_dict: dict,
    forwarding_header: str = "",
) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any:
        """Get default value for key."""
        value = user_input.get(key, default_dict.get(key, fallback_default))
        if isinstance(value, list):
            value = ", ".join(value)
        return value

    schema_dict: dict = {
        vol.Required(
            CONF_AMAZON_DOMAIN,
            default=_get_default(CONF_AMAZON_DOMAIN, DEFAULT_AMAZON_DOMAIN),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=AMAZON_DOMAINS,
                custom_value=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key=CONF_AMAZON_DOMAIN,
            )
        ),
    }
    if not forwarding_header or forwarding_header == "(none)":
        schema_dict[
            vol.Optional(CONF_AMAZON_FWDS, default=_get_default(CONF_AMAZON_FWDS))
        ] = cv.string
    schema_dict[
        vol.Optional(CONF_AMAZON_DAYS, default=_get_default(CONF_AMAZON_DAYS))
    ] = int
    return vol.Schema(schema_dict)


def _get_schema_step_forwarded_emails(
    user_input: list | dict | None,
    default_dict: dict,
) -> vol.Schema:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> Any:
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

    def _get_default(key: str, fallback_default: Any = None) -> Any:
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
