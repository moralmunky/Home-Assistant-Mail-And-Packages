"""Adds config flow for Mail and Packages."""

import logging
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
    CONF_AMAZON_FWDS,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_MP4,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DEFAULT_ALLOW_EXTERNAL,
    DEFAULT_AMAZON_FWDS,
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


def _get_mailboxes(host: str, port: int, user: str, pwd: str) -> list:
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


def _get_schema_step_1(hass: Any, user_input: list, default_dict: list) -> Any:
    """Gets a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key):
        """Gets default value for key."""
        return user_input.get(key, default_dict.get(key))

    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=_get_default(CONF_HOST)): str,
            vol.Required(CONF_PORT, default=_get_default(CONF_PORT)): vol.Coerce(int),
            vol.Required(CONF_USERNAME, default=_get_default(CONF_USERNAME)): str,
            vol.Required(CONF_PASSWORD, default=_get_default(CONF_PASSWORD)): str,
        }
    )


def _get_schema_step_2(
    hass: Any, data: list, user_input: list, default_dict: list
) -> Any:
    """Gets a schema using the default_dict as a backup."""
    if user_input is None:
        user_input = {}

    def _get_default(key):
        """Gets default value for key."""
        return user_input.get(key, default_dict.get(key))

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
            vol.Optional(
                CONF_SCAN_INTERVAL, default=_get_default(CONF_SCAN_INTERVAL)
            ): vol.Coerce(int),
            vol.Optional(
                CONF_IMAP_TIMEOUT, default=_get_default(CONF_IMAP_TIMEOUT)
            ): vol.Coerce(int),
            vol.Optional(
                CONF_DURATION, default=_get_default(CONF_DURATION)
            ): vol.Coerce(int),
            vol.Optional(
                CONF_GENERATE_MP4, default=_get_default(CONF_GENERATE_MP4)
            ): bool,
            vol.Optional(
                CONF_ALLOW_EXTERNAL, default=_get_default(CONF_ALLOW_EXTERNAL)
            ): bool,
        }
    )


@config_entries.HANDLERS.register(DOMAIN)
class MailAndPackagesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Mail and Packages."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input={}):
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
            if valid:
                return await self.async_step_config_2()
            else:
                self._errors["base"] = "communication"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""

        # Defaults
        defaults = {
            CONF_PORT: DEFAULT_PORT,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=_get_schema_step_1(self.hass, user_input, defaults),
            errors=self._errors,
        )

    async def async_step_config_2(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            user_input[CONF_AMAZON_FWDS] = user_input[CONF_AMAZON_FWDS].split(",")
            self._data.update(user_input)
            if user_input[CONF_GENERATE_MP4]:
                valid = await _check_ffmpeg()
            else:
                valid = True

            if valid:
                return self.async_create_entry(
                    title=self._data[CONF_HOST], data=self._data
                )
            else:
                self._errors["base"] = "ffmpeg_not_found"

            return await self._show_config_2(user_input)

        return await self._show_config_2(user_input)

    async def _show_config_2(self, user_input):
        """ Step 2 setup """

        # Defaults
        defaults = {
            CONF_FOLDER: DEFAULT_FOLDER,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_PATH: self.hass.config.path() + DEFAULT_PATH,
            CONF_DURATION: DEFAULT_GIF_DURATION,
            CONF_IMAGE_SECURITY: DEFAULT_IMAGE_SECURITY,
            CONF_IMAP_TIMEOUT: DEFAULT_IMAP_TIMEOUT,
            CONF_AMAZON_FWDS: DEFAULT_AMAZON_FWDS,
            CONF_GENERATE_MP4: False,
            CONF_ALLOW_EXTERNAL: DEFAULT_ALLOW_EXTERNAL,
        }

        return self.async_show_form(
            step_id="config_2",
            data_schema=_get_schema_step_2(self.hass, self._data, user_input, defaults),
            errors=self._errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
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
            if valid:
                return await self.async_step_options_2()
            else:
                self._errors["base"] = "communication"

            return await self._show_options_form(user_input)

        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input):
        """Show the configuration form to edit location data."""

        return self.async_show_form(
            step_id="init",
            data_schema=_get_schema_step_1(self.hass, user_input, self._data),
            errors=self._errors,
        )

    async def async_step_options_2(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            user_input[CONF_AMAZON_FWDS] = user_input[CONF_AMAZON_FWDS].split(",")
            self._data.update(user_input)

            if user_input[CONF_GENERATE_MP4]:
                valid = await _check_ffmpeg()
            else:
                valid = True

            if valid:
                return self.async_create_entry(title="", data=self._data)
            else:
                self._errors["base"] = "ffmpeg_not_found"

            return await self._show_step_options_2(user_input)

        return await self._show_step_options_2(user_input)

    async def _show_step_options_2(self, user_input):
        """Step 2 of options."""

        return self.async_show_form(
            step_id="options_2",
            data_schema=_get_schema_step_2(
                self.hass, self._data, user_input, self._data
            ),
            errors=self._errors,
        )
