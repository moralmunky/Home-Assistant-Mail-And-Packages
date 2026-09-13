"""Adds config flow for Mail and Packages."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.mail_and_packages.config_flows.options import (
    OptionsFlowStepsMixin,
)
from custom_components.mail_and_packages.config_flows.reconfig import (
    ReconfigureFlowMixin,
)
from custom_components.mail_and_packages.config_flows.schemas import (
    IMAP_SECURITY,
    _build_step_2_schema,
    _get_schema_auth,
    _get_schema_imap,
    _get_schema_step_2,
    _get_schema_step_3,
    _get_schema_step_amazon,
    _get_schema_step_forwarded_emails,
    _get_schema_step_storage,
    multi_folder_select,
)
from custom_components.mail_and_packages.config_flows.steps import (
    AMAZON_SENSORS,
    ConfigFlowStepsMixin,
)
from custom_components.mail_and_packages.config_flows.validation import (
    AMAZON_EMAIL_ERROR,
    ERROR_MAILBOX_FAIL,
    FORWARDED_EMAIL_ERROR,
    _check_amazon_forwards,
    _check_forwarded_emails,
    _get_mailboxes,
    _parse_folder_list,
    _validate_amazon_fwds,
    _validate_forwarded_emails,
    _validate_login,
    _validate_path_input,
    _validate_user_input,
)
from custom_components.mail_and_packages.const import (
    AUTH_TYPE_OAUTH_GOOGLE,
    AUTH_TYPE_OAUTH_MICROSOFT,
    AUTH_TYPE_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_IMAP_SECURITY,
    CONF_VERIFY_SSL,
    CONFIG_VER,
    DEFAULT_FOLDER,
    DEFAULT_PORT,
    DOMAIN,
    OAUTH_IMAP_DEFAULTS,
    OAUTH_SCOPES,
)
from custom_components.mail_and_packages.utils.email import validate_email_address
from custom_components.mail_and_packages.utils.image import _check_ffmpeg
from custom_components.mail_and_packages.utils.imap import login, logout

_LOGGER = logging.getLogger(__name__)

# Re-exports for test compatibility and patch targets
__all__ = [
    "AMAZON_EMAIL_ERROR",
    "AMAZON_SENSORS",
    "DEFAULT_FOLDER",
    "ERROR_MAILBOX_FAIL",
    "FORWARDED_EMAIL_ERROR",
    "IMAP_SECURITY",
    "ConfigFlowStepsMixin",
    "MailAndPackagesFlowHandler",
    "MailAndPackagesOptionsFlow",
    "OptionsFlowStepsMixin",
    "Path",
    "ReconfigureFlowMixin",
    "_build_step_2_schema",
    "_check_amazon_forwards",
    "_check_ffmpeg",
    "_check_forwarded_emails",
    "_get_mailboxes",
    "_get_schema_auth",
    "_get_schema_imap",
    "_get_schema_step_2",
    "_get_schema_step_3",
    "_get_schema_step_amazon",
    "_get_schema_step_forwarded_emails",
    "_get_schema_step_storage",
    "_parse_folder_list",
    "_validate_amazon_fwds",
    "_validate_forwarded_emails",
    "_validate_login",
    "_validate_path_input",
    "_validate_user_input",
    "login",
    "logout",
    "multi_folder_select",
    "validate_email_address",
]


@config_entries.HANDLERS.register(DOMAIN)
class MailAndPackagesFlowHandler(
    ReconfigureFlowMixin,
    ConfigFlowStepsMixin,
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Config flow for Mail and Packages."""

    VERSION = CONFIG_VER
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    DOMAIN = DOMAIN

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return MailAndPackagesOptionsFlow(config_entry)

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
        elif auth_type == AUTH_TYPE_OAUTH_MICROSOFT:
            data.update(
                {
                    "prompt": "select_account",
                }
            )
        return data

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._entry: config_entries.ConfigEntry | None = None
        self._data: dict[str, Any] = {}
        self._errors: dict[str, Any] = {}

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
                self._data[CONF_VERIFY_SSL] = True
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN]["oauth_provider"] = auth_type
                return await self.async_step_pick_implementation()

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
            self.hass.config_entries.async_update_entry(
                self._entry,
                data=self._data,
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            if self.context.get("source") == config_entries.SOURCE_REAUTH:
                return self.async_abort(reason="reauth_successful")
            _LOGGER.debug("%s reconfigured.", DOMAIN)
            return self.async_abort(reason="reconfigure_successful")
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


class MailAndPackagesOptionsFlow(OptionsFlowStepsMixin, config_entries.OptionsFlow):
    """Options flow for Mail and Packages."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry
        self._data = {**config_entry.data, **config_entry.options}
        self._errors: dict[str, Any] = {}
