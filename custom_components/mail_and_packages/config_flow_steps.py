"""Step handlers mixin for Mail and Packages config flow."""

from __future__ import annotations

import sys
from typing import Any

from homeassistant.const import CONF_HOST, CONF_RESOURCES

from .config_flow_schemas import (
    _get_schema_step_2,
    _get_schema_step_3,
    _get_schema_step_amazon,
    _get_schema_step_forwarded_emails,
    _get_schema_step_storage,
)
from .config_flow_validation import _validate_user_input as default_validate_user_input
from .const import (
    CONF_ALLOW_EXTERNAL,
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
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
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_POST_DE_CUSTOM_IMG,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    CONF_SCAN_INTERVAL,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_USPS_PLACEHOLDER,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
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
    DEFAULT_GENERIC_CUSTOM_IMG,
    DEFAULT_GENERIC_CUSTOM_IMG_FILE,
    DEFAULT_GIF_DURATION,
    DEFAULT_IMAGE_SECURITY,
    DEFAULT_IMAP_TIMEOUT,
    DEFAULT_PATH,
    DEFAULT_POST_DE_CUSTOM_IMG,
    DEFAULT_POST_DE_CUSTOM_IMG_FILE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STORAGE,
    DEFAULT_UPS_CUSTOM_IMG,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_USPS_PLACEHOLDER,
    DEFAULT_WALMART_CUSTOM_IMG,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
)

AMAZON_SENSORS = [
    "amazon_packages",
    "amazon_delivering",
    "amazon_delivered",
    "amazon_exception",
]


def _get_target(symbol_name: str, fallback_callable: Any) -> Any:
    """Dynamically get symbol from config_flow module if imported/patched there."""
    cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
    if cf and hasattr(cf, symbol_name):
        return getattr(cf, symbol_name)
    return fallback_callable


def _get_target_val_fn() -> Any:
    """Dynamically get _validate_user_input from config_flow to honor any patches."""
    return _get_target("_validate_user_input", default_validate_user_input)


class ConfigFlowStepsMixin:
    """Mixin for multi-step setup flow forms in MailAndPackagesFlowHandler."""

    hass: Any
    _data: dict[str, Any]
    _errors: dict[str, Any]
    async_show_form: Any
    async_create_entry: Any

    async def async_step_config_2(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            val_fn = _get_target_val_fn()
            self._errors, user_input = await val_fn(user_input, self.hass)
            self._data.update(user_input)
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
                    or self._data.get(CONF_POST_DE_CUSTOM_IMG)
                )
                if has_custom_image:
                    return await self.async_step_config_3()

                return self.async_create_entry(
                    title=f"Mail and Packages ({self._data[CONF_HOST]})",
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
            CONF_PATH: self.hass.config.path(DEFAULT_PATH),
            CONF_DURATION: DEFAULT_GIF_DURATION,
            CONF_IMAGE_SECURITY: DEFAULT_IMAGE_SECURITY,
            CONF_IMAP_TIMEOUT: DEFAULT_IMAP_TIMEOUT,
            CONF_GENERATE_GRID: False,
            CONF_GENERATE_MP4: False,
            CONF_USPS_PLACEHOLDER: DEFAULT_USPS_PLACEHOLDER,
            CONF_ALLOW_EXTERNAL: DEFAULT_ALLOW_EXTERNAL,
            CONF_CUSTOM_IMG: DEFAULT_CUSTOM_IMG,
            CONF_AMAZON_CUSTOM_IMG: DEFAULT_AMAZON_CUSTOM_IMG,
            CONF_UPS_CUSTOM_IMG: DEFAULT_UPS_CUSTOM_IMG,
            CONF_WALMART_CUSTOM_IMG: DEFAULT_WALMART_CUSTOM_IMG,
            CONF_FEDEX_CUSTOM_IMG: DEFAULT_FEDEX_CUSTOM_IMG,
            CONF_GENERIC_CUSTOM_IMG: DEFAULT_GENERIC_CUSTOM_IMG,
            CONF_POST_DE_CUSTOM_IMG: DEFAULT_POST_DE_CUSTOM_IMG,
            CONF_ALLOW_FORWARDED_EMAILS: DEFAULT_ALLOW_FORWARDED_EMAILS,
        }

        # Resolve _get_schema_step_2 dynamically if patched
        cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
        schema_fn = getattr(cf, "_get_schema_step_2", _get_schema_step_2)

        return self.async_show_form(
            step_id="config_2",
            data_schema=await schema_fn(
                self._data,
                user_input,
                defaults,
                self.hass,
                getattr(self, "_entry", None),
            ),
            errors=self._errors,
        )

    async def async_step_config_3(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            val_fn = _get_target_val_fn()
            self._errors, user_input = await val_fn(self._data, self.hass)
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
            CONF_POST_DE_CUSTOM_IMG_FILE: DEFAULT_POST_DE_CUSTOM_IMG_FILE,
        }

        cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
        schema_fn = getattr(cf, "_get_schema_step_3", _get_schema_step_3)

        return self.async_show_form(
            step_id="config_3",
            data_schema=schema_fn(self._data, defaults),
            errors=self._errors,
        )

    async def async_step_config_amazon(self, user_input=None):
        """Configure form step amazon."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            val_fn = _get_target_val_fn()
            self._errors, user_input = await val_fn(self._data, self.hass)
            if len(self._errors) == 0:
                if (
                    self._data.get(CONF_CUSTOM_IMG)
                    or self._data.get(CONF_AMAZON_CUSTOM_IMG)
                    or self._data.get(CONF_UPS_CUSTOM_IMG)
                    or self._data.get(CONF_WALMART_CUSTOM_IMG)
                    or self._data.get(CONF_GENERIC_CUSTOM_IMG)
                    or self._data.get(CONF_POST_DE_CUSTOM_IMG)
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

        cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
        schema_fn = getattr(cf, "_get_schema_step_amazon", _get_schema_step_amazon)

        return self.async_show_form(
            step_id="config_amazon",
            data_schema=schema_fn(
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
            val_fn = _get_target_val_fn()
            self._errors, user_input = await val_fn(self._data, self.hass)
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

        cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
        schema_fn = getattr(
            cf,
            "_get_schema_step_forwarded_emails",
            _get_schema_step_forwarded_emails,
        )

        return self.async_show_form(
            step_id="config_forwarded_emails",
            data_schema=schema_fn(user_input, defaults),
            errors=self._errors,
        )

    async def async_step_config_storage(self, user_input=None):
        """Configure form step storage."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            val_fn = _get_target_val_fn()
            self._errors, user_input = await val_fn(self._data, self.hass)
            if len(self._errors) == 0:
                return self.async_create_entry(
                    title=f"Mail and Packages ({self._data[CONF_HOST]})",
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

        cf = sys.modules.get("custom_components.mail_and_packages.config_flow")
        schema_fn = getattr(cf, "_get_schema_step_storage", _get_schema_step_storage)

        return self.async_show_form(
            step_id="config_storage",
            data_schema=schema_fn(user_input, defaults),
            errors=self._errors,
        )
