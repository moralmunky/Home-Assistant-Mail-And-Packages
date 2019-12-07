"""Adds config flow for Mail and Packages."""
import logging
from collections import OrderedDict

import voluptuous as vol
import imaplib

from homeassistant import config_entries
from .const import (DOMAIN, DEFAULT_PORT, DEFAULT_PATH, DEFAULT_FOLDER)
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
        self._errors = {}

    async def async_step_user(self, user_input={}):
        """Handle a flow initialized by the user."""
        self._errors = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if self.hass.data.get(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            valid = await self._test_login(
                user_input[CONF_HOST], user_input[CONF_PORT],
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if valid:
                return self.async_create_entry(title=user_input[CONF_HOST],
                                               data=user_input)
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
        folder = DEFAULT_FOLDER
        image_path = DEFAULT_PATH

        if user_input is not None:
            if "host" in user_input:
                host = user_input["host"]
            if "port" in user_input:
                port = user_input["port"]
            if "username" in user_input:
                username = user_input["username"]
            if "password" in user_input:
                password = user_input["password"]
            if "folder" in user_input:
                folder = user_input["folder"]
            if "image_path" in user_input:
                image_path = user_input["image_path"]

        data_schema = OrderedDict()
        data_schema[vol.Required("host", default=host)] = str
        data_schema[vol.Required("port", default=port)] = vol.Coerce(int)
        data_schema[vol.Required("username", default=username)] = str
        data_schema[vol.Required("password", default=password)] = str
        data_schema[vol.Optional("folder", default=folder)] = str
        data_schema[vol.Optional("image_path", default=image_path)] = str
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema),
            errors=self._errors)

    # async def async_step_import(self, user_input):
    #     """Import a config entry.
    #     Special type of import, we're not actually going to store any data.
    #     Instead, we're going to rely on the values that are in config file.
    #     """
    #     if self._async_current_entries():
    #         return self.async_abort(reason="single_instance_allowed")

    #     return self.async_create_entry(title="configuration.yaml", data={})

    async def _test_login(self, host, port, user, pwd):
        """function used to login"""
        # Attempt to catch invalid mail server hosts
        try:
            account = imaplib.IMAP4_SSL(host, port)
        except imaplib.IMAP4.error as err:
            _LOGGER.info("Error connecting into IMAP Server: %s", str(err))
            return False
        # Validate we can login to mail server
        try:
            rv, data = account.login(user, pwd)
            return True
        except imaplib.IMAP4.error as err:
            _LOGGER.info("Error logging into IMAP Server: %s", str(err))
            return False
