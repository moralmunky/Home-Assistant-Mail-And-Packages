"""Options flow steps mixin for Mail and Packages."""

from __future__ import annotations

import sys
from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_RESOURCES

from custom_components.mail_and_packages.const import (
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FOLDER,
    CONF_FORWARDED_EMAILS,
    CONF_FORWARDING_HEADER,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    CONF_SCAN_INTERVAL,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
)
from custom_components.mail_and_packages.utils.image import (
    _check_ffmpeg as default_check_ffmpeg,
)

from .schemas import (
    _get_schema_step_2,
    _get_schema_step_3,
    _get_schema_step_amazon,
    _get_schema_step_forwarded_emails,
    _get_schema_step_storage,
)
from .steps import AMAZON_SENSORS
from .validation import _validate_user_input

OPTIONS_KEYS = {
    CONF_FOLDER,
    CONF_SCAN_INTERVAL,
    CONF_RESOURCES,
    CONF_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_FORWARDED_EMAILS,
    CONF_FORWARDING_HEADER,
    CONF_AMAZON_FWDS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_DAYS,
    CONF_STORAGE,
    "generate_mp4",
    "generate_grid",
    "gif_duration",
    "custom_days",
    "allow_external",
    "image_security",
    "imap_timeout",
    "image_name",
    "image_path",
    "usps_placeholder",
}


def _get_target(symbol_name: str, fallback_callable: Any) -> Any:
    """Dynamically get symbol from config_flow module if imported/patched there."""
    cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
    if cf and hasattr(cf, symbol_name):
        return getattr(cf, symbol_name)
    return fallback_callable


class OptionsFlowStepsMixin:
    """Mixin providing steps for the options flow."""

    _entry: config_entries.ConfigEntry
    _data: dict[str, Any]
    _errors: dict[str, Any]
    hass: Any
    async_show_form: Any
    async_create_entry: Any

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            if self._data.get("generate_mp4", False):
                check_ffmpeg = _get_target("_check_ffmpeg", default_check_ffmpeg)
                if not await check_ffmpeg():
                    self._errors["generate_mp4"] = "ffmpeg_not_found"
            if len(self._errors) == 0:
                if self._data.get(CONF_ALLOW_FORWARDED_EMAILS, False):
                    return await self.async_step_options_forwarded_emails()
                if any(
                    sensor in self._data[CONF_RESOURCES] for sensor in AMAZON_SENSORS
                ):
                    return await self.async_step_options_amazon()
                if self._data.get(CONF_CUSTOM_IMG, False):
                    return await self.async_step_options_3()
                return await self.async_step_options_storage()

            return await self._show_options_2(user_input)

        return await self._show_options_2(user_input)

    async def _show_options_2(self, user_input: dict[str, Any] | None) -> Any:
        """Step 2 of options."""
        if self._data.get(CONF_AMAZON_FWDS) == []:
            self._data[CONF_AMAZON_FWDS] = "(none)"

        return self.async_show_form(
            step_id="init",
            data_schema=await _get_schema_step_2(
                self._data, user_input, self._data, self.hass, self._entry
            ),
            errors=self._errors,
        )

    async def async_step_options_forwarded_emails(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Configure forwarded emails."""
        self._errors = {}
        if user_input is not None:
            if user_input.get(CONF_FORWARDED_EMAILS) == "(none)":
                user_input[CONF_FORWARDED_EMAILS] = []
            self._data.update(user_input)
            if len(self._errors) == 0:
                if any(
                    sensor in self._data[CONF_RESOURCES] for sensor in AMAZON_SENSORS
                ):
                    return await self.async_step_options_amazon()
                if self._data.get(CONF_CUSTOM_IMG, False):
                    return await self.async_step_options_3()
                return await self.async_step_options_storage()
        return await self._show_options_forwarded_emails(user_input)

    async def _show_options_forwarded_emails(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step forwarded emails."""
        if self._data.get(CONF_FORWARDED_EMAILS, []) == []:
            self._data[CONF_FORWARDED_EMAILS] = "(none)"

        return self.async_show_form(
            step_id="options_forwarded_emails",
            data_schema=_get_schema_step_forwarded_emails(user_input, self._data),
            errors=self._errors,
        )

    async def async_step_options_amazon(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Configure amazon options."""
        self._errors = {}
        if user_input is not None:
            if user_input.get(CONF_AMAZON_FWDS) == "(none)":
                user_input[CONF_AMAZON_FWDS] = []
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data, self.hass)
            if len(self._errors) == 0:
                if self._data.get(CONF_CUSTOM_IMG, False):
                    return await self.async_step_options_3()
                return await self.async_step_options_storage()
            return await self._show_options_amazon(user_input)
        return await self._show_options_amazon(user_input)

    async def _show_options_amazon(self, user_input: dict[str, Any] | None) -> Any:
        """Step Amazon setup."""
        if self._data.get(CONF_AMAZON_FWDS) == []:
            self._data[CONF_AMAZON_FWDS] = "(none)"

        return self.async_show_form(
            step_id="options_amazon",
            data_schema=_get_schema_step_amazon(
                user_input,
                self._data,
                forwarding_header=self._data.get(CONF_FORWARDING_HEADER, ""),
            ),
            errors=self._errors,
        )

    async def async_step_options_3(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Configure custom image files."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data, self.hass)
            if len(self._errors) == 0:
                return await self.async_step_options_storage()
            return await self._show_options_3(user_input)
        return await self._show_options_3(user_input)

    async def _show_options_3(self, user_input: dict[str, Any] | None) -> Any:
        """Step 3 setup."""
        return self.async_show_form(
            step_id="options_3",
            data_schema=_get_schema_step_3(self._data, self._data),
            errors=self._errors,
        )

    async def async_step_options_storage(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Configure storage options."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data, self.hass)
            if len(self._errors) == 0:
                for key in list(self._data.keys()):
                    if key not in OPTIONS_KEYS:
                        self._data.pop(key, None)

                return self.async_create_entry(title="", data=self._data)

            return await self._show_options_storage(user_input)

        return await self._show_options_storage(user_input)

    async def _show_options_storage(self, user_input: dict[str, Any] | None) -> Any:
        """Step storage setup."""
        return self.async_show_form(
            step_id="options_storage",
            data_schema=_get_schema_step_storage(user_input, self._data),
            errors=self._errors,
        )
