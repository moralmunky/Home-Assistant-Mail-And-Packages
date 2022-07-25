"""Adds config flow for Mail and Packages."""

import logging
from os import path
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
from homeassistant.core import callback

from .const import (
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_MP4,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DEFAULT_ALLOW_EXTERNAL,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_AMAZON_FWDS,
    DEFAULT_CUSTOM_IMG,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FOLDER,
    DEFAULT_GIF_DURATION,
    DEFAULT_IMAGE_SECURITY,
    DEFAULT_IMAP_TIMEOUT,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
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

    # No forwards
    elif forwards in ["", "(none)", ""]:
        amazon_forwards_list = []

    # If only one address append it to the list
    elif forwards:
        amazon_forwards_list.append(forwards)

    if len(errors) == 0:
        errors.append("ok")

    return errors, amazon_forwards_list


async def _validate_user_input(user_input: dict) -> tuple:
    """Valididate user input from config flow.

    Returns tuple with error messages and modified user_input
    """
    errors = {}

    # Validate amazon forwarding email addresses
    if isinstance(user_input[CONF_AMAZON_FWDS], str):
        status, amazon_list = await _check_amazon_forwards(user_input[CONF_AMAZON_FWDS])
        if status[0] == "ok":
            user_input[CONF_AMAZON_FWDS] = amazon_list
        else:
            user_input[CONF_AMAZON_FWDS] = amazon_list
            errors[CONF_AMAZON_FWDS] = status[0]

    # Check for ffmpeg if option enabled
    if user_input[CONF_GENERATE_MP4]:
        valid = await _check_ffmpeg()
    else:
        valid = True

    if not valid:
        errors[CONF_GENERATE_MP4] = "ffmpeg_not_found"

    # validate custom file exists
    if user_input[CONF_CUSTOM_IMG] and CONF_CUSTOM_IMG_FILE in user_input:
        valid = path.isfile(user_input[CONF_CUSTOM_IMG_FILE])
    else:
        valid = True

    if not valid:
        errors[CONF_CUSTOM_IMG_FILE] = "file_not_found"

    # validate scan interval
    if user_input[CONF_SCAN_INTERVAL] < 5:
        errors[CONF_SCAN_INTERVAL] = "scan_too_low"

    # validate imap timeout
    if user_input[CONF_IMAP_TIMEOUT] < 10:
        errors[CONF_IMAP_TIMEOUT] = "timeout_too_low"

    return errors, user_input


def _get_mailboxes(host: str, port: int, user: str, pwd: str) -> list:
    """Get list of mailbox folders from mail server."""
    account = login(host, port, user, pwd)

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

    return mailboxes


def _get_schema_step_1(user_input: list, default_dict: list) -> Any:
    """Get a schema using the default_dict as a backup."""
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


def _get_schema_step_2(data: list, user_input: list, default_dict: list) -> Any:
    """Get a schema using the default_dict as a backup."""
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
            vol.Optional(CONF_AMAZON_FWDS, default=_get_default(CONF_AMAZON_FWDS)): str,
            vol.Optional(CONF_AMAZON_DAYS, default=_get_default(CONF_AMAZON_DAYS)): int,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=_get_default(CONF_SCAN_INTERVAL)
            ): vol.All(vol.Coerce(int)),
            vol.Optional(
                CONF_IMAP_TIMEOUT, default=_get_default(CONF_IMAP_TIMEOUT)
            ): vol.All(vol.Coerce(int)),
            vol.Optional(
                CONF_DURATION, default=_get_default(CONF_DURATION)
            ): vol.Coerce(int),
            vol.Optional(
                CONF_GENERATE_MP4, default=_get_default(CONF_GENERATE_MP4)
            ): bool,
            vol.Optional(
                CONF_ALLOW_EXTERNAL, default=_get_default(CONF_ALLOW_EXTERNAL)
            ): bool,
            vol.Optional(CONF_CUSTOM_IMG, default=_get_default(CONF_CUSTOM_IMG)): bool,
        }
    )


def _get_schema_step_3(user_input: list, default_dict: list) -> Any:
    """Get a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key: str, fallback_default: Any = None) -> None:
        """Get default value for key."""
        return user_input.get(key, default_dict.get(key, fallback_default))

    return vol.Schema(
        {
            vol.Optional(
                CONF_CUSTOM_IMG_FILE,
                default=_get_default(CONF_CUSTOM_IMG_FILE, DEFAULT_CUSTOM_IMG_FILE),
            ): str,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class MailAndPackagesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Mail and Packages."""

    VERSION = 4
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            self._data.update(user_input)
            valid = await _test_login(
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

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit configuration data."""
        # Defaults
        defaults = {
            CONF_PORT: DEFAULT_PORT,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema_step_1(user_input, defaults),
            errors=self._errors,
        )

    async def async_step_config_2(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            if len(self._errors) == 0:
                if self._data[CONF_CUSTOM_IMG]:
                    return await self.async_step_config_3()
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )
            return await self._show_config_2(user_input)

        return await self._show_config_2(user_input)

    async def _show_config_2(self, user_input):
        """Step 2 setup."""
        # Defaults
        defaults = {
            CONF_FOLDER: DEFAULT_FOLDER,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_PATH: self.hass.config.path() + DEFAULT_PATH,
            CONF_DURATION: DEFAULT_GIF_DURATION,
            CONF_IMAGE_SECURITY: DEFAULT_IMAGE_SECURITY,
            CONF_IMAP_TIMEOUT: DEFAULT_IMAP_TIMEOUT,
            CONF_AMAZON_FWDS: DEFAULT_AMAZON_FWDS,
            CONF_AMAZON_DAYS: DEFAULT_AMAZON_DAYS,
            CONF_GENERATE_MP4: False,
            CONF_ALLOW_EXTERNAL: DEFAULT_ALLOW_EXTERNAL,
            CONF_CUSTOM_IMG: DEFAULT_CUSTOM_IMG,
        }

        return self.async_show_form(
            step_id="config_2",
            data_schema=_get_schema_step_2(self._data, user_input, defaults),
            errors=self._errors,
        )

    async def async_step_config_3(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )
            return await self._show_config_3(user_input)

        return await self._show_config_3(user_input)

    async def _show_config_3(self, user_input):
        """Step 3 setup."""
        # Defaults
        defaults = {
            CONF_CUSTOM_IMG_FILE: DEFAULT_CUSTOM_IMG_FILE,
        }

        return self.async_show_form(
            step_id="config_3",
            data_schema=_get_schema_step_3(user_input, defaults),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Redirect to options flow."""
        return MailAndPackagesOptionsFlow(config_entry)


class MailAndPackagesOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Mail and Packages."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config = config_entry
        self._data = dict(config_entry.options)
        self._errors = {}

    async def async_step_init(self, user_input=None):
        """Manage Mail and Packages options."""
        if user_input is not None:
            self._data.update(user_input)

            valid = await _test_login(
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

    async def _show_options_form(self, user_input):
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="init",
            data_schema=_get_schema_step_1(user_input, self._data),
            errors=self._errors,
        )

    async def async_step_options_2(self, user_input=None):
        """Configure form step 2."""
        self._errors = {}
        if user_input is not None:
            self._errors, user_input = await _validate_user_input(user_input)
            self._data.update(user_input)
            if len(self._errors) == 0:
                if self._data[CONF_CUSTOM_IMG]:
                    return await self.async_step_options_3()
                return self.async_create_entry(title="", data=self._data)
            return await self._show_step_options_2(user_input)
        return await self._show_step_options_2(user_input)

    async def _show_step_options_2(self, user_input):
        """Step 2 of options."""
        # Defaults
        defaults = {
            CONF_FOLDER: self._data.get(CONF_FOLDER),
            CONF_SCAN_INTERVAL: self._data.get(CONF_SCAN_INTERVAL),
            CONF_PATH: self._data.get(CONF_PATH),
            CONF_DURATION: self._data.get(CONF_DURATION),
            CONF_IMAGE_SECURITY: self._data.get(CONF_IMAGE_SECURITY),
            CONF_IMAP_TIMEOUT: self._data.get(CONF_IMAP_TIMEOUT)
            or DEFAULT_IMAP_TIMEOUT,
            CONF_AMAZON_FWDS: self._data.get(CONF_AMAZON_FWDS) or DEFAULT_AMAZON_FWDS,
            CONF_AMAZON_DAYS: self._data.get(CONF_AMAZON_DAYS) or DEFAULT_AMAZON_DAYS,
            CONF_GENERATE_MP4: self._data.get(CONF_GENERATE_MP4),
            CONF_ALLOW_EXTERNAL: self._data.get(CONF_ALLOW_EXTERNAL),
            CONF_RESOURCES: self._data.get(CONF_RESOURCES),
            CONF_CUSTOM_IMG: self._data.get(CONF_CUSTOM_IMG) or DEFAULT_CUSTOM_IMG,
        }

        return self.async_show_form(
            step_id="options_2",
            data_schema=_get_schema_step_2(self._data, user_input, defaults),
            errors=self._errors,
        )

    async def async_step_options_3(self, user_input=None):
        """Configure form step 3."""
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            self._errors, user_input = await _validate_user_input(self._data)
            if len(self._errors) == 0:
                return self.async_create_entry(title="", data=self._data)
            return await self._show_step_options_3(user_input)

        return await self._show_step_options_3(user_input)

    async def _show_step_options_3(self, user_input):
        """Step 3 setup."""
        # Defaults
        defaults = {
            CONF_CUSTOM_IMG_FILE: self._data.get(CONF_CUSTOM_IMG_FILE)
            or DEFAULT_CUSTOM_IMG_FILE,
        }

        return self.async_show_form(
            step_id="options_3",
            data_schema=_get_schema_step_3(user_input, defaults),
            errors=self._errors,
        )
