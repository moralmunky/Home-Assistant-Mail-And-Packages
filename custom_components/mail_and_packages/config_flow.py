"""Adds config flow for Mail and Packages."""
from __future__ import annotations

import logging
from os import path
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries

try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import callback

from .const import (
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_COOKIES,
    CONF_AMAZON_COOKIES_ENABLED,
    CONF_AMAZON_COOKIE_DOMAIN,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_MP4,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_LLM_API_KEY,
    CONF_LLM_ENABLED,
    CONF_LLM_ENDPOINT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_PATH,
    CONF_SCAN_ALL_EMAILS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_FORWARD_ENABLED,
    CONF_TRACKING_SERVICE,
    CONF_TRACKING_SERVICE_ENTRY_ID,
    DEFAULT_ALLOW_EXTERNAL,
    DEFAULT_AMAZON_COOKIES,
    DEFAULT_AMAZON_COOKIES_ENABLED,
    DEFAULT_AMAZON_COOKIE_DOMAIN,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_AMAZON_FWDS,
    DEFAULT_CUSTOM_IMG,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FOLDER,
    DEFAULT_GIF_DURATION,
    DEFAULT_IMAGE_SECURITY,
    DEFAULT_IMAP_TIMEOUT,
    DEFAULT_LLM_API_KEY,
    DEFAULT_LLM_ENABLED,
    DEFAULT_LLM_ENDPOINT,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_ALL_EMAILS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACKING_FORWARD_ENABLED,
    DEFAULT_TRACKING_SERVICE,
    DEFAULT_TRACKING_SERVICE_ENTRY_ID,
    DOMAIN,
    LLM_PROVIDERS,
    TRACKING_SERVICE_OPTIONS,
)
from .helpers import _check_ffmpeg, _test_login, get_resources, login

_LOGGER = logging.getLogger(__name__)


async def _check_amazon_forwards(forwards: str) -> tuple:
    """Validate and format amazon forward emails for user input.

    Returns tuple: dict of errors, list of email addresses
    """
    amazon_forwards_list = []
    errors = []

    # Check for amazon domains
    if "@amazon" in forwards:
        errors.append("amazon_domain")

    # Check for commas
    if "," in forwards:
        amazon_forwards_list = forwards.split(",")

    # If only one address append it to the list
    elif forwards:
        amazon_forwards_list.append(forwards)

    if len(errors) == 0:
        errors.append("ok")

    return errors, amazon_forwards_list


async def _validate_user_input(user_input: dict) -> tuple:
    """Validate user input from config flow.

    Returns tuple with error messages and modified user_input.
    Only validates fields present in user_input.

    For non-critical failures (ffmpeg, custom image), the validation
    auto-disables the broken feature and returns the error so the user
    sees what happened. The form re-shows with the feature already
    turned off, so they can just submit again to proceed.
    """
    errors = {}

    # Validate amazon forwarding email addresses
    if CONF_AMAZON_FWDS in user_input and isinstance(
        user_input[CONF_AMAZON_FWDS], str
    ):
        status, amazon_list = await _check_amazon_forwards(
            user_input[CONF_AMAZON_FWDS]
        )
        if status[0] == "ok":
            user_input[CONF_AMAZON_FWDS] = amazon_list
        else:
            user_input[CONF_AMAZON_FWDS] = amazon_list
            errors[CONF_AMAZON_FWDS] = status[0]

    # Check for ffmpeg if option enabled
    if CONF_GENERATE_MP4 in user_input and user_input[CONF_GENERATE_MP4]:
        valid = _check_ffmpeg()
        if not valid:
            # Auto-disable MP4 so user can just submit again to proceed
            user_input[CONF_GENERATE_MP4] = False
            errors[CONF_GENERATE_MP4] = "ffmpeg_not_found"
            _LOGGER.warning(
                "ffmpeg not found - MP4 generation has been disabled. "
                "Install ffmpeg and re-enable in options if needed."
            )

    # Validate custom file exists
    if (
        CONF_CUSTOM_IMG in user_input
        and user_input.get(CONF_CUSTOM_IMG)
        and CONF_CUSTOM_IMG_FILE in user_input
    ):
        valid = path.isfile(user_input[CONF_CUSTOM_IMG_FILE])
        if not valid:
            errors[CONF_CUSTOM_IMG_FILE] = "file_not_found"

    # Validate scan interval (blocking - too-low values cause server issues)
    if CONF_SCAN_INTERVAL in user_input and user_input[CONF_SCAN_INTERVAL] < 5:
        errors[CONF_SCAN_INTERVAL] = "scan_too_low"

    # Validate imap timeout (blocking - too-low values cause timeouts)
    if CONF_IMAP_TIMEOUT in user_input and user_input[CONF_IMAP_TIMEOUT] < 10:
        errors[CONF_IMAP_TIMEOUT] = "timeout_too_low"

    return errors, user_input


def _get_mailboxes(host: str, port: int, user: str, pwd: str) -> list:
    """Get list of mailbox folders from mail server."""
    account = login(host, port, user, pwd)

    if not account:
        _LOGGER.error("Login failed, cannot list mailboxes ... using default")
        return [DEFAULT_FOLDER]

    try:
        status, folderlist = account.list()
        mailboxes = []
        if status != "OK":
            _LOGGER.error("Error listing mailboxes ... using default")
            mailboxes.append(DEFAULT_FOLDER)
        else:
            try:
                for i in folderlist:
                    mailboxes.append(i.decode().split(' "/" ')[1])
            except IndexError:
                _LOGGER.error("Error creating folder array trying period")
                try:
                    for i in folderlist:
                        mailboxes.append(i.decode().split(' "." ')[1])
                except IndexError:
                    _LOGGER.error("Error creating folder array, using INBOX")
                    mailboxes.append(DEFAULT_FOLDER)
    finally:
        try:
            account.logout()
        except Exception:
            pass

    return mailboxes


# --- Schema builders ---


def _get_schema_step_1(user_input: list, default_dict: list) -> Any:
    """Schema for IMAP connection credentials (step 1)."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=_get_default(CONF_HOST)): str,
            vol.Required(CONF_PORT, default=_get_default(CONF_PORT)): vol.Coerce(int),
            vol.Required(CONF_USERNAME, default=_get_default(CONF_USERNAME)): str,
            vol.Required(CONF_PASSWORD, default=_get_default(CONF_PASSWORD)): str,
        }
    )


def _get_schema_sensors(data: list, user_input: list, default_dict: list) -> Any:
    """Schema for mailbox and sensor selection (step 2)."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Required(CONF_FOLDER, default=_get_default(CONF_FOLDER)): vol.In(
                _get_mailboxes(
                    data[CONF_HOST],
                    data[CONF_PORT],
                    data[CONF_USERNAME],
                    data[CONF_PASSWORD],
                )
            ),
            vol.Required(
                CONF_RESOURCES, default=_get_default(CONF_RESOURCES)
            ): cv.multi_select(get_resources()),
        }
    )


def _get_schema_scanning(user_input: list, default_dict: list) -> Any:
    """Schema for scanning and Amazon settings (step 3)."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=_get_default(CONF_SCAN_INTERVAL)
            ): vol.All(vol.Coerce(int)),
            vol.Optional(
                CONF_IMAP_TIMEOUT, default=_get_default(CONF_IMAP_TIMEOUT)
            ): vol.All(vol.Coerce(int)),
            vol.Optional(
                CONF_AMAZON_FWDS, default=_get_default(CONF_AMAZON_FWDS, "")
            ): str,
            vol.Optional(
                CONF_AMAZON_DAYS, default=_get_default(CONF_AMAZON_DAYS)
            ): int,
        }
    )


def _get_schema_images(user_input: list, default_dict: list) -> Any:
    """Schema for image and output settings (step 4)."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_DURATION, default=_get_default(CONF_DURATION)
            ): vol.Coerce(int),
            vol.Optional(
                CONF_GENERATE_MP4, default=_get_default(CONF_GENERATE_MP4)
            ): bool,
            vol.Optional(
                CONF_ALLOW_EXTERNAL, default=_get_default(CONF_ALLOW_EXTERNAL)
            ): bool,
            vol.Optional(
                CONF_CUSTOM_IMG, default=_get_default(CONF_CUSTOM_IMG)
            ): bool,
        }
    )


def _get_schema_features(user_input: list, default_dict: list) -> Any:
    """Schema for advanced feature toggles (step 5)."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_ALL_EMAILS,
                default=_get_default(
                    CONF_SCAN_ALL_EMAILS, DEFAULT_SCAN_ALL_EMAILS
                ),
            ): bool,
            vol.Optional(
                CONF_TRACKING_FORWARD_ENABLED,
                default=_get_default(
                    CONF_TRACKING_FORWARD_ENABLED,
                    DEFAULT_TRACKING_FORWARD_ENABLED,
                ),
            ): bool,
            vol.Optional(
                CONF_LLM_ENABLED,
                default=_get_default(CONF_LLM_ENABLED, DEFAULT_LLM_ENABLED),
            ): bool,
            vol.Optional(
                CONF_AMAZON_COOKIES_ENABLED,
                default=_get_default(
                    CONF_AMAZON_COOKIES_ENABLED, DEFAULT_AMAZON_COOKIES_ENABLED
                ),
            ): bool,
        }
    )


def _has_advanced_tracking(data: dict) -> bool:
    """Check if any advanced tracking feature is enabled."""
    return (
        data.get(CONF_TRACKING_FORWARD_ENABLED, False)
        or data.get(CONF_LLM_ENABLED, False)
        or data.get(CONF_AMAZON_COOKIES_ENABLED, False)
    )


def _get_schema_advanced_tracking(
    user_input: list, default_dict: list, data: dict
) -> Any:
    """Build schema for advanced tracking configuration step."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    schema = {}

    # Tracking service forwarding configuration
    if data.get(CONF_TRACKING_FORWARD_ENABLED, False):
        schema[
            vol.Required(
                CONF_TRACKING_SERVICE,
                default=_get_default(
                    CONF_TRACKING_SERVICE, DEFAULT_TRACKING_SERVICE
                ),
            )
        ] = vol.In(TRACKING_SERVICE_OPTIONS)
        schema[
            vol.Optional(
                CONF_TRACKING_SERVICE_ENTRY_ID,
                default=_get_default(
                    CONF_TRACKING_SERVICE_ENTRY_ID,
                    DEFAULT_TRACKING_SERVICE_ENTRY_ID,
                ),
            )
        ] = str

    # LLM configuration (with privacy implications)
    if data.get(CONF_LLM_ENABLED, False):
        schema[
            vol.Required(
                CONF_LLM_PROVIDER,
                default=_get_default(
                    CONF_LLM_PROVIDER, DEFAULT_LLM_PROVIDER
                ),
            )
        ] = vol.In(LLM_PROVIDERS)
        schema[
            vol.Optional(
                CONF_LLM_ENDPOINT,
                default=_get_default(
                    CONF_LLM_ENDPOINT, DEFAULT_LLM_ENDPOINT
                ),
            )
        ] = str
        schema[
            vol.Optional(
                CONF_LLM_API_KEY,
                default=_get_default(CONF_LLM_API_KEY, DEFAULT_LLM_API_KEY),
            )
        ] = str
        schema[
            vol.Optional(
                CONF_LLM_MODEL,
                default=_get_default(CONF_LLM_MODEL, DEFAULT_LLM_MODEL),
            )
        ] = str

    # Amazon cookie configuration
    if data.get(CONF_AMAZON_COOKIES_ENABLED, False):
        schema[
            vol.Required(
                CONF_AMAZON_COOKIE_DOMAIN,
                default=_get_default(
                    CONF_AMAZON_COOKIE_DOMAIN, DEFAULT_AMAZON_COOKIE_DOMAIN
                ),
            )
        ] = str
        schema[
            vol.Required(
                CONF_AMAZON_COOKIES,
                default=_get_default(
                    CONF_AMAZON_COOKIES, DEFAULT_AMAZON_COOKIES
                ),
            )
        ] = str

    return vol.Schema(schema)


def _get_schema_custom_img(user_input: list, default_dict: list) -> Any:
    """Schema for custom image file path."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_CUSTOM_IMG_FILE,
                default=_get_default(
                    CONF_CUSTOM_IMG_FILE, DEFAULT_CUSTOM_IMG_FILE
                ),
            ): str,
        }
    )


# Keep old name for backward compatibility
_get_schema_step_3 = _get_schema_custom_img


# --- Config Flow ---


class MailAndPackagesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Mail and Packages."""

    VERSION = 6

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    # Step 1: IMAP Connection

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            valid = await _test_login(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not valid:
                self._errors["base"] = "communication"
            else:
                return await self.async_step_config_2()

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input) -> ConfigFlowResult:
        """Show the configuration form to edit configuration data."""
        defaults = {
            CONF_PORT: DEFAULT_PORT,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema_step_1(user_input, defaults),
            errors=self._errors,
        )

    # Reauth

    async def async_step_reauth(
        self, entry_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow triggered by auth failure."""
        self._data = dict(entry_data) if entry_data else {}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Handle reauth credentials input."""
        self._errors = {}

        if user_input is not None:
            self._data[CONF_HOST] = user_input[CONF_HOST]
            self._data[CONF_PORT] = user_input[CONF_PORT]
            self._data[CONF_USERNAME] = user_input[CONF_USERNAME]
            self._data[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            valid = await _test_login(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if valid:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=self._data,
                )
            else:
                self._errors["base"] = "communication"

        defaults = {
            CONF_HOST: self._data.get(CONF_HOST, ""),
            CONF_PORT: self._data.get(CONF_PORT, DEFAULT_PORT),
            CONF_USERNAME: self._data.get(CONF_USERNAME, ""),
            CONF_PASSWORD: self._data.get(CONF_PASSWORD, ""),
        }

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_get_schema_step_1(None, defaults),
            errors=self._errors,
        )

    # Step 2: Mailbox & Sensor Selection

    async def async_step_config_2(self, user_input=None) -> ConfigFlowResult:
        """Configure mailbox folder and sensors."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_config_3()

        return await self._show_config_2(user_input)

    async def _show_config_2(self, user_input) -> ConfigFlowResult:
        """Show mailbox & sensors form."""
        defaults = {
            CONF_FOLDER: DEFAULT_FOLDER,
        }

        return self.async_show_form(
            step_id="config_2",
            data_schema=_get_schema_sensors(
                self._data, user_input, defaults
            ),
            errors=self._errors,
        )

    # Step 3: Scanning & Amazon Settings

    async def async_step_config_3(self, user_input=None) -> ConfigFlowResult:
        """Configure scanning interval and Amazon settings."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            if len(self._errors) == 0:
                return await self.async_step_config_4()
            return await self._show_config_3(user_input)

        return await self._show_config_3(user_input)

    async def _show_config_3(self, user_input) -> ConfigFlowResult:
        """Show scanning & Amazon settings form."""
        defaults = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_IMAP_TIMEOUT: DEFAULT_IMAP_TIMEOUT,
            CONF_AMAZON_FWDS: DEFAULT_AMAZON_FWDS,
            CONF_AMAZON_DAYS: DEFAULT_AMAZON_DAYS,
        }

        return self.async_show_form(
            step_id="config_3",
            data_schema=_get_schema_scanning(user_input, defaults),
            errors=self._errors,
        )

    # Step 4: Image & Output Settings

    async def async_step_config_4(self, user_input=None) -> ConfigFlowResult:
        """Configure image and output settings."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            if len(self._errors) == 0:
                return await self.async_step_config_5()
            return await self._show_config_4(user_input)

        return await self._show_config_4(user_input)

    async def _show_config_4(self, user_input) -> ConfigFlowResult:
        """Show image settings form."""
        defaults = {
            CONF_DURATION: DEFAULT_GIF_DURATION,
            CONF_GENERATE_MP4: False,
            CONF_ALLOW_EXTERNAL: DEFAULT_ALLOW_EXTERNAL,
            CONF_CUSTOM_IMG: DEFAULT_CUSTOM_IMG,
        }

        return self.async_show_form(
            step_id="config_4",
            data_schema=_get_schema_images(user_input, defaults),
            errors=self._errors,
        )

    # Step 5: Advanced Feature Toggles

    async def async_step_config_5(self, user_input=None) -> ConfigFlowResult:
        """Configure advanced feature toggles."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            if _has_advanced_tracking(self._data):
                return await self.async_step_config_advanced()
            if self._data.get(CONF_CUSTOM_IMG, False):
                return await self.async_step_config_6()
            return self.async_create_entry(
                title=self._data[CONF_HOST], data=self._data
            )

        return await self._show_config_5(user_input)

    async def _show_config_5(self, user_input) -> ConfigFlowResult:
        """Show advanced feature toggles form."""
        defaults = {}

        return self.async_show_form(
            step_id="config_5",
            data_schema=_get_schema_features(user_input, defaults),
            errors=self._errors,
        )

    # Conditional: Advanced Tracking Configuration

    async def async_step_config_advanced(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Configure advanced tracking features."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            if self._data.get(CONF_CUSTOM_IMG, False):
                return await self.async_step_config_6()
            return self.async_create_entry(
                title=self._data[CONF_HOST], data=self._data
            )

        return await self._show_config_advanced(user_input)

    async def _show_config_advanced(self, user_input) -> ConfigFlowResult:
        """Show advanced tracking configuration form."""
        defaults = {
            CONF_TRACKING_SERVICE: DEFAULT_TRACKING_SERVICE,
            CONF_TRACKING_SERVICE_ENTRY_ID: DEFAULT_TRACKING_SERVICE_ENTRY_ID,
            CONF_LLM_PROVIDER: DEFAULT_LLM_PROVIDER,
            CONF_LLM_ENDPOINT: DEFAULT_LLM_ENDPOINT,
            CONF_LLM_API_KEY: DEFAULT_LLM_API_KEY,
            CONF_LLM_MODEL: DEFAULT_LLM_MODEL,
            CONF_AMAZON_COOKIES: DEFAULT_AMAZON_COOKIES,
            CONF_AMAZON_COOKIE_DOMAIN: DEFAULT_AMAZON_COOKIE_DOMAIN,
        }

        return self.async_show_form(
            step_id="config_advanced",
            data_schema=_get_schema_advanced_tracking(
                user_input, defaults, self._data
            ),
            errors=self._errors,
        )

    # Conditional: Custom Image Path

    async def async_step_config_6(self, user_input=None) -> ConfigFlowResult:
        """Configure custom image file path."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )
            # If custom image file not found, disable custom_img and
            # create entry anyway so user isn't stuck (no back button)
            if CONF_CUSTOM_IMG_FILE in self._errors:
                _LOGGER.warning(
                    "Custom image file '%s' not found. "
                    "Disabling custom image and continuing setup. "
                    "You can set a valid path later in options.",
                    self._data.get(CONF_CUSTOM_IMG_FILE, ""),
                )
                self._data[CONF_CUSTOM_IMG] = False
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )
            return await self._show_config_6(user_input)

        return await self._show_config_6(user_input)

    async def _show_config_6(self, user_input) -> ConfigFlowResult:
        """Show custom image path form."""
        defaults = {
            CONF_CUSTOM_IMG_FILE: DEFAULT_CUSTOM_IMG_FILE,
        }

        return self.async_show_form(
            step_id="config_6",
            data_schema=_get_schema_custom_img(user_input, defaults),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Redirect to options flow."""
        return MailAndPackagesOptionsFlow()


# --- Options Flow ---


class MailAndPackagesOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Mail and Packages."""

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    def _ensure_complete_data(self) -> None:
        """Ensure _data has all expected keys with safe defaults.

        This prevents KeyError or missing form defaults when
        reconfiguring an integration that was set up with an older
        version or is missing fields. Uses internal representations
        (e.g. list for AMAZON_FWDS, not the form display string).
        """
        defaults = {
            CONF_FOLDER: DEFAULT_FOLDER,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_IMAP_TIMEOUT: DEFAULT_IMAP_TIMEOUT,
            CONF_AMAZON_FWDS: [],  # Internal representation is list
            CONF_AMAZON_DAYS: DEFAULT_AMAZON_DAYS,
            CONF_DURATION: DEFAULT_GIF_DURATION,
            CONF_GENERATE_MP4: False,
            CONF_ALLOW_EXTERNAL: DEFAULT_ALLOW_EXTERNAL,
            CONF_CUSTOM_IMG: DEFAULT_CUSTOM_IMG,
            CONF_CUSTOM_IMG_FILE: DEFAULT_CUSTOM_IMG_FILE,
            CONF_SCAN_ALL_EMAILS: DEFAULT_SCAN_ALL_EMAILS,
            CONF_TRACKING_FORWARD_ENABLED: DEFAULT_TRACKING_FORWARD_ENABLED,
            CONF_TRACKING_SERVICE: DEFAULT_TRACKING_SERVICE,
            CONF_TRACKING_SERVICE_ENTRY_ID: DEFAULT_TRACKING_SERVICE_ENTRY_ID,
            CONF_LLM_ENABLED: DEFAULT_LLM_ENABLED,
            CONF_LLM_PROVIDER: DEFAULT_LLM_PROVIDER,
            CONF_LLM_ENDPOINT: DEFAULT_LLM_ENDPOINT,
            CONF_LLM_API_KEY: DEFAULT_LLM_API_KEY,
            CONF_LLM_MODEL: DEFAULT_LLM_MODEL,
            CONF_AMAZON_COOKIES_ENABLED: DEFAULT_AMAZON_COOKIES_ENABLED,
            CONF_AMAZON_COOKIES: DEFAULT_AMAZON_COOKIES,
            CONF_AMAZON_COOKIE_DOMAIN: DEFAULT_AMAZON_COOKIE_DOMAIN,
        }
        for key, default_val in defaults.items():
            self._data.setdefault(key, default_val)

    # Step 1: IMAP Connection

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage Mail and Packages options."""
        if not self._data:
            self._data = dict(self.config_entry.options)
            self._ensure_complete_data()
        if user_input is not None:
            self._data.update(user_input)

            valid = await _test_login(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not valid:
                self._errors["base"] = "communication"
            else:
                return await self.async_step_options_2()

            return await self._show_options_form(user_input)

        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input) -> ConfigFlowResult:
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="init",
            data_schema=_get_schema_step_1(user_input, self._data),
            errors=self._errors,
        )

    # Step 2: Mailbox & Sensor Selection

    async def async_step_options_2(self, user_input=None) -> ConfigFlowResult:
        """Configure mailbox folder and sensors."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_options_3()
        return await self._show_step_options_2(user_input)

    async def _show_step_options_2(self, user_input) -> ConfigFlowResult:
        """Show mailbox & sensors form."""
        defaults = {
            CONF_FOLDER: self._data.get(CONF_FOLDER),
            CONF_RESOURCES: self._data.get(CONF_RESOURCES),
        }

        return self.async_show_form(
            step_id="options_2",
            data_schema=_get_schema_sensors(
                self._data, user_input, defaults
            ),
            errors=self._errors,
        )

    # Step 3: Scanning & Amazon Settings

    async def async_step_options_3(self, user_input=None) -> ConfigFlowResult:
        """Configure scanning interval and Amazon settings."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            if len(self._errors) == 0:
                return await self.async_step_options_4()
            return await self._show_step_options_3(user_input)
        return await self._show_step_options_3(user_input)

    async def _show_step_options_3(self, user_input) -> ConfigFlowResult:
        """Show scanning & Amazon settings form."""
        # Convert list back to comma-separated string for form display
        fwds = self._data.get(CONF_AMAZON_FWDS, [])
        if isinstance(fwds, list):
            fwds = ", ".join(fwds) if fwds else ""
        defaults = {
            CONF_SCAN_INTERVAL: self._data.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
            CONF_IMAP_TIMEOUT: self._data.get(
                CONF_IMAP_TIMEOUT, DEFAULT_IMAP_TIMEOUT
            ),
            CONF_AMAZON_FWDS: fwds,
            CONF_AMAZON_DAYS: self._data.get(
                CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS
            ),
        }

        return self.async_show_form(
            step_id="options_3",
            data_schema=_get_schema_scanning(user_input, defaults),
            errors=self._errors,
        )

    # Step 4: Image & Output Settings

    async def async_step_options_4(self, user_input=None) -> ConfigFlowResult:
        """Configure image and output settings."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            if len(self._errors) == 0:
                return await self.async_step_options_5()
            return await self._show_step_options_4(user_input)
        return await self._show_step_options_4(user_input)

    async def _show_step_options_4(self, user_input) -> ConfigFlowResult:
        """Show image settings form."""
        defaults = {
            CONF_DURATION: self._data.get(CONF_DURATION, DEFAULT_GIF_DURATION),
            CONF_GENERATE_MP4: self._data.get(CONF_GENERATE_MP4, False),
            CONF_ALLOW_EXTERNAL: self._data.get(
                CONF_ALLOW_EXTERNAL, DEFAULT_ALLOW_EXTERNAL
            ),
            CONF_CUSTOM_IMG: self._data.get(CONF_CUSTOM_IMG, DEFAULT_CUSTOM_IMG),
        }

        return self.async_show_form(
            step_id="options_4",
            data_schema=_get_schema_images(user_input, defaults),
            errors=self._errors,
        )

    # Step 5: Advanced Feature Toggles

    async def async_step_options_5(self, user_input=None) -> ConfigFlowResult:
        """Configure advanced feature toggles."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            if _has_advanced_tracking(self._data):
                return await self.async_step_options_advanced()
            if self._data.get(CONF_CUSTOM_IMG, False):
                return await self.async_step_options_6()
            return self.async_create_entry(title="", data=self._data)
        return await self._show_step_options_5(user_input)

    async def _show_step_options_5(self, user_input) -> ConfigFlowResult:
        """Show advanced feature toggles form."""
        defaults = {
            CONF_SCAN_ALL_EMAILS: self._data.get(
                CONF_SCAN_ALL_EMAILS, DEFAULT_SCAN_ALL_EMAILS
            ),
            CONF_TRACKING_FORWARD_ENABLED: self._data.get(
                CONF_TRACKING_FORWARD_ENABLED, DEFAULT_TRACKING_FORWARD_ENABLED
            ),
            CONF_LLM_ENABLED: self._data.get(
                CONF_LLM_ENABLED, DEFAULT_LLM_ENABLED
            ),
            CONF_AMAZON_COOKIES_ENABLED: self._data.get(
                CONF_AMAZON_COOKIES_ENABLED, DEFAULT_AMAZON_COOKIES_ENABLED
            ),
        }

        return self.async_show_form(
            step_id="options_5",
            data_schema=_get_schema_features(user_input, defaults),
            errors=self._errors,
        )

    # Conditional: Advanced Tracking Configuration

    async def async_step_options_advanced(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Configure advanced tracking features in options flow."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            if self._data.get(CONF_CUSTOM_IMG, False):
                return await self.async_step_options_6()
            return self.async_create_entry(title="", data=self._data)

        return await self._show_step_options_advanced(user_input)

    async def _show_step_options_advanced(
        self, user_input
    ) -> ConfigFlowResult:
        """Show advanced tracking options form."""
        defaults = {
            CONF_TRACKING_SERVICE: self._data.get(
                CONF_TRACKING_SERVICE, DEFAULT_TRACKING_SERVICE
            ),
            CONF_TRACKING_SERVICE_ENTRY_ID: self._data.get(
                CONF_TRACKING_SERVICE_ENTRY_ID, DEFAULT_TRACKING_SERVICE_ENTRY_ID
            ),
            CONF_LLM_PROVIDER: self._data.get(
                CONF_LLM_PROVIDER, DEFAULT_LLM_PROVIDER
            ),
            CONF_LLM_ENDPOINT: self._data.get(
                CONF_LLM_ENDPOINT, DEFAULT_LLM_ENDPOINT
            ),
            CONF_LLM_API_KEY: self._data.get(
                CONF_LLM_API_KEY, DEFAULT_LLM_API_KEY
            ),
            CONF_LLM_MODEL: self._data.get(
                CONF_LLM_MODEL, DEFAULT_LLM_MODEL
            ),
            CONF_AMAZON_COOKIES: self._data.get(
                CONF_AMAZON_COOKIES, DEFAULT_AMAZON_COOKIES
            ),
            CONF_AMAZON_COOKIE_DOMAIN: self._data.get(
                CONF_AMAZON_COOKIE_DOMAIN, DEFAULT_AMAZON_COOKIE_DOMAIN
            ),
        }

        return self.async_show_form(
            step_id="options_advanced",
            data_schema=_get_schema_advanced_tracking(
                user_input, defaults, self._data
            ),
            errors=self._errors,
        )

    # Conditional: Custom Image Path

    async def async_step_options_6(self, user_input=None) -> ConfigFlowResult:
        """Configure custom image file path."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return self.async_create_entry(title="", data=self._data)
            # If custom image file not found, disable custom_img and
            # save anyway so user isn't stuck (no back button)
            if CONF_CUSTOM_IMG_FILE in self._errors:
                _LOGGER.warning(
                    "Custom image file '%s' not found. "
                    "Disabling custom image. You can set a valid "
                    "path later in options.",
                    self._data.get(CONF_CUSTOM_IMG_FILE, ""),
                )
                self._data[CONF_CUSTOM_IMG] = False
                return self.async_create_entry(title="", data=self._data)
            return await self._show_step_options_6(user_input)

        return await self._show_step_options_6(user_input)

    async def _show_step_options_6(self, user_input) -> ConfigFlowResult:
        """Show custom image path form."""
        defaults = {
            CONF_CUSTOM_IMG_FILE: self._data.get(
                CONF_CUSTOM_IMG_FILE, DEFAULT_CUSTOM_IMG_FILE
            ),
        }

        return self.async_show_form(
            step_id="options_6",
            data_schema=_get_schema_custom_img(user_input, defaults),
            errors=self._errors,
        )
