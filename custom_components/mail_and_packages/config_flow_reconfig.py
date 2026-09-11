"""Reconfiguration step handlers mixin for Mail and Packages config flow."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow

from .config_flow_schemas import _get_schema_auth, _get_schema_imap
from .config_flow_validation import _validate_login
from .const import (
    AUTH_TYPE_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_IMAP_SECURITY,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    OAUTH_IMAP_DEFAULTS,
)

_LOGGER = logging.getLogger(__name__)


class ReconfigureFlowMixin:
    """Mixin for config entry reconfiguration and oauth token checking."""

    _entry: config_entries.ConfigEntry | None
    _data: dict[str, Any]
    _errors: dict[str, Any]
    context: dict[str, Any]
    hass: Any
    async_show_form: Any
    async_abort: Any
    async_step_pick_implementation: Any

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Add reconfigure step to allow to reconfigure a config entry."""
        self._entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert self._entry
        self._data = dict(self._entry.data)
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_reconfig_imap()

        return await self._show_reconfig_auth_form(user_input)

    async def _async_valid_oauth_token(self, auth_type: str) -> dict | None:
        """Return the entry's OAuth token if it is still usable, else None."""
        if not self._entry:
            return None

        try:
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN]["oauth_provider"] = auth_type
            implementation = (
                await config_entry_oauth2_flow.async_get_config_entry_implementation(
                    self.hass,
                    self._entry,
                )
            )
            session = config_entry_oauth2_flow.OAuth2Session(
                self.hass,
                self._entry,
                implementation,
            )
            await session.async_ensure_token_valid()
        except (
            aiohttp.ClientError,
            HomeAssistantError,
            TimeoutError,
            ValueError,
        ) as err:
            _LOGGER.debug("Stored OAuth token is no longer usable: %s", err)
            return None

        return session.token

    async def async_step_reconfig_imap(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Handle IMAP step for reconfigure."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)

            if auth_type != AUTH_TYPE_PASSWORD:
                token = None
                if (
                    self._entry
                    and self._entry.data.get(CONF_AUTH_TYPE) == auth_type
                    and self._entry.data.get(CONF_HOST) == self._data.get(CONF_HOST)
                    and self._entry.data.get(CONF_USERNAME)
                    == self._data.get(CONF_USERNAME)
                    and "token" in self._data
                ):
                    token = await self._async_valid_oauth_token(auth_type)

                if token is not None:
                    self._data["token"] = token
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data=self._data,
                    )
                    await self.hass.config_entries.async_reload(self._entry.entry_id)
                    _LOGGER.debug("%s reconfigured (oauth skip).", DOMAIN)
                    return self.async_abort(reason="reconfigure_successful")

                self._data[CONF_VERIFY_SSL] = True
                self.hass.data.setdefault(DOMAIN, {})
                self.hass.data[DOMAIN]["oauth_provider"] = auth_type
                return await self.async_step_pick_implementation()

            self._errors = await _validate_login(self.hass, self._data)
            if self._errors == {}:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data=self._data,
                )
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                _LOGGER.debug("%s reconfigured.", DOMAIN)
                return self.async_abort(reason="reconfigure_successful")

            return await self._show_reconfig_imap_form(user_input)

        return await self._show_reconfig_imap_form(user_input)

    async def _show_reconfig_auth_form(self, user_input: dict[str, Any] | None) -> Any:
        """Show the auth form for reconfigure."""
        defaults = {
            CONF_AUTH_TYPE: (
                self._entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
                if self._entry
                else AUTH_TYPE_PASSWORD
            ),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_get_schema_auth(user_input, defaults),
            errors=self._errors,
        )

    async def _show_reconfig_imap_form(self, user_input: dict[str, Any] | None) -> Any:
        """Show the configuration form to edit IMAP data."""
        auth_type = self._data.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
        defaults = OAUTH_IMAP_DEFAULTS.get(
            auth_type,
            {
                CONF_PORT: self._entry.data.get(CONF_PORT, DEFAULT_PORT)
                if self._entry
                else DEFAULT_PORT,
                CONF_IMAP_SECURITY: self._entry.data.get(CONF_IMAP_SECURITY, "SSL")
                if self._entry
                else "SSL",
                CONF_VERIFY_SSL: self._entry.data.get(
                    CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                )
                if self._entry
                else DEFAULT_VERIFY_SSL,
            },
        )

        if self._entry:
            defaults[CONF_HOST] = self._entry.data.get(
                CONF_HOST, defaults.get(CONF_HOST)
            )
            defaults[CONF_USERNAME] = self._entry.data.get(
                CONF_USERNAME, defaults.get(CONF_USERNAME)
            )
            defaults[CONF_PASSWORD] = self._entry.data.get(
                CONF_PASSWORD, defaults.get(CONF_PASSWORD)
            )
        defaults[CONF_AUTH_TYPE] = auth_type

        return self.async_show_form(
            step_id="reconfig_imap",
            data_schema=_get_schema_imap(user_input, defaults),
            errors=self._errors,
        )
