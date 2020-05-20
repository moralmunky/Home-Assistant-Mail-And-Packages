"""Adds config flow for Mail and Packages."""
import logging
from collections import OrderedDict

import voluptuous as vol
import imaplib
import os

from homeassistant.core import callback
from homeassistant import config_entries
from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_PATH,
    DEFAULT_FOLDER,
    DEFAULT_IMAGE_SECURITY,
    GIF_DURATION,
    DEFAULT_SCAN_INTERVAL,
    CONF_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_FOLDER,
    CONF_PATH,
    CONF_IMAGE_SECURITY,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_PORT
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class MailAndPackagesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Mail and Packages."""

    VERSION = 1
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
            valid = await self._test_login(
                user_input[CONF_HOST], user_input[CONF_PORT],
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if valid:
                return await self.async_step_config_2()
            else:
                self._errors["base"] = "communication"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):
        """Show the configuration form to edit location data."""

        # Defaults
        host = ""
        port = DEFAULT_PORT
        username = ""
        password = ""

        if user_input is not None:
            if "host" in user_input:
                host = user_input["host"]
            if "port" in user_input:
                port = user_input["port"]
            if "username" in user_input:
                username = user_input["username"]
            if "password" in user_input:
                password = user_input["password"]

        data_schema = OrderedDict()
        data_schema[vol.Required("host", default=host)] = str
        data_schema[vol.Required("port", default=port)] = vol.Coerce(int)
        data_schema[vol.Required("username", default=username)] = str
        data_schema[vol.Required("password", default=password)] = str
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema),
            errors=self._errors)

    async def async_step_config_2(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            valid = await self._validate_path(user_input["image_path"])

            if valid:
                if user_input["folder"] is not None:
                    if not user_input["image_path"].endswith("/"):
                        user_input["image_path"] += "/"
                        self._data.update(user_input)
                return self.async_create_entry(title=self._data[CONF_HOST],
                                               data=self._data)
            else:
                self._errors["base"] = "invalid_path"

            return await self._show_config_2(user_input)

        return await self._show_config_2(user_input)

    async def _show_config_2(self, user_input):
        """ Step 2 setup """

        # Defaults
        folder = DEFAULT_FOLDER
        image_path = DEFAULT_PATH
        gif_duration = GIF_DURATION
        image_security = DEFAULT_IMAGE_SECURITY
        scan_interval = DEFAULT_SCAN_INTERVAL

        account = imaplib.IMAP4_SSL(self._data["host"], self._data["port"])
        status, data = account.login(self._data["username"],
                                     self._data["password"])
        if status != "OK":
            _LOGGER.error("IMAP Login failed!")
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

        if user_input is not None:
            if "folder" in user_input:
                folder = user_input["folder"]
            if "image_path" in user_input:
                image_path = user_input["image_path"]
            if "gif_duration" in user_input:
                gif_duration = user_input["gif_duration"]
            if "image_security" in user_input:
                image_security = user_input["image_security"]
            if "scan_interval" in user_input:
                scan_interval = user_input["scan_interval"]

        data_schema = OrderedDict()
        data_schema[vol.Required("folder",
                                 default=folder)] = vol.In(mailboxes)
        data_schema[vol.Optional("image_security",
                                 default=image_security)] = bool
        data_schema[vol.Optional("gif_duration",
                                 default=gif_duration)] = vol.Coerce(int)
        data_schema[vol.Optional("scan_interval",
                                 default=scan_interval)] = vol.Coerce(int)
        data_schema[vol.Optional("image_path", default=image_path)] = str
        return self.async_show_form(
            step_id="config_2", data_schema=vol.Schema(data_schema),
            errors=self._errors)

    async def _test_login(self, host, port, user, pwd):
        """function used to login"""
        # Attempt to catch invalid mail server hosts
        try:
            account = imaplib.IMAP4_SSL(host, port)
        except imaplib.IMAP4.error as err:
            _LOGGER.error("Error connecting into IMAP Server: %s", str(err))
            return False
        # Validate we can login to mail server
        try:
            rv, data = account.login(user, pwd)
            return True
        except imaplib.IMAP4.error as err:
            _LOGGER.error("Error logging into IMAP Server: %s", str(err))
            return False

    async def _validate_path(self, path):
        """ make sure path is valid """
        if path in os.path.dirname(__file__):
            return False
        else:
            return True

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

            valid = await self._test_login(
                user_input[CONF_HOST], user_input[CONF_PORT],
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if valid:
                return await self.async_step_options_2()
            else:
                self._errors["base"] = "communication"

            return await self._show_options_form(user_input)

        return await self._show_options_form(user_input)

    async def _show_options_form(self, user_input):
        """Show the configuration form to edit location data."""

        # Defaults
        host = self.config.options.get(CONF_HOST)
        port = self.config.options.get(CONF_PORT)
        username = self.config.options.get(CONF_USERNAME)
        password = self.config.options.get(CONF_PASSWORD)

        if user_input is not None:
            if "host" in user_input:
                host = user_input["host"]
            if "port" in user_input:
                port = user_input["port"]
            if "username" in user_input:
                username = user_input["username"]
            if "password" in user_input:
                password = user_input["password"]

        data_schema = OrderedDict()
        data_schema[vol.Required("host", default=host)] = str
        data_schema[vol.Required("port", default=port)] = vol.Coerce(int)
        data_schema[vol.Required("username", default=username)] = str
        data_schema[vol.Required("password", default=password)] = str
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema),
            errors=self._errors)

    async def async_step_options_2(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            valid = await self._validate_path(user_input["image_path"])

            if valid:
                if user_input["folder"] is not None:
                    if not user_input["image_path"].endswith("/"):
                        user_input["image_path"] += "/"
                        self._data.update(user_input)

                return self.async_create_entry(title="", data=self._data)
            else:
                self._errors["base"] = "invalid_path"

            return await self._show_step_options_2(user_input)

        return await self._show_step_options_2(user_input)

    async def _show_step_options_2(self, user_input):
        """Step 2 of options."""

        # Defaults
        folder = self.config.options.get(CONF_FOLDER)
        image_path = self.config.options.get(CONF_PATH)
        gif_duration = self.config.options.get(CONF_DURATION)
        scan_interval = self.config.options.get(CONF_SCAN_INTERVAL)
        image_security = self.config.options.get(CONF_IMAGE_SECURITY)

        account = imaplib.IMAP4_SSL(self._data["host"], self._data["port"])
        status, data = account.login(self._data["username"],
                                     self._data["password"])
        if status != "OK":
            _LOGGER.error("IMAP Login failed!")
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

        if user_input is not None:
            if "folder" in user_input:
                folder = user_input["folder"]
            if "image_path" in user_input:
                image_path = user_input["image_path"]
            if "gif_duration" in user_input:
                gif_duration = user_input["gif_duration"]
            if "image_security" in user_input:
                image_security = user_input["image_security"]
            if "scan_interval" in user_input:
                scan_interval = user_input["scan_interval"]

        data_schema = OrderedDict()
        data_schema[vol.Required("folder",
                                 default=folder)] = vol.In(mailboxes)
        data_schema[vol.Optional("image_security",
                                 default=image_security)] = bool
        data_schema[vol.Optional("gif_duration",
                                 default=gif_duration)] = vol.Coerce(int)
        data_schema[vol.Optional("scan_interval",
                                 default=scan_interval)] = vol.Coerce(int)
        data_schema[vol.Optional("image_path", default=image_path)] = str
        return self.async_show_form(
            step_id="options_2", data_schema=vol.Schema(data_schema),
            errors=self._errors)

    async def _test_login(self, host, port, user, pwd):
        """function used to login"""
        # Attempt to catch invalid mail server hosts
        try:
            account = imaplib.IMAP4_SSL(host, port)
        except imaplib.IMAP4.error as err:
            _LOGGER.error("Error connecting into IMAP Server: %s", str(err))
            return False
        # Validate we can login to mail server
        try:
            rv, data = account.login(user, pwd)
            return True
        except imaplib.IMAP4.error as err:
            _LOGGER.error("Error logging into IMAP Server: %s", str(err))
            return False

    async def _validate_path(self, path):
        """ make sure path is valid """
        if os.path.dirname(__file__) in path:
            return False
        else:
            return True
