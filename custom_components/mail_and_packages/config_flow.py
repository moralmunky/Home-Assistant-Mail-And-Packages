"""Adds config flow for Mail and Packages."""

from collections import OrderedDict
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant import config_entries
from .const import (
    CONF_AMAZON_FWDS,
    CONF_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_FOLDER,
    CONF_PATH,
    CONF_IMAGE_SECURITY,
    CONF_GENERATE_MP4,
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_PATH,
    DEFAULT_FOLDER,
    DEFAULT_IMAGE_SECURITY,
    DEFAULT_GIF_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_FFMPEG,
    SENSOR_TYPES,
    SENSOR_NAME,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_PORT,
    CONF_RESOURCES,
)
import imaplib
import logging
import os
from shutil import which
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

ATTR_HOST = "host"
ATTR_PORT = "port"
ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"
ATTR_FOLDER = "folder"
ATTR_IMAGE_PATH = "image_path"
ATTR_SCAN_INTERVAL = "scan_interval"
ATTR_GIF_DURATION = "gif_duration"
ATTR_IMAGE_SECURITY = "image_security"
ATTR_GENERATE_MP4 = "generate_mp4"
ATTR_AMAZON_FWDS = "amazon_fwds"


def get_resources():
    """Resource selection schema."""

    known_available_resources = {
        sensor_id: sensor[SENSOR_NAME] for sensor_id, sensor in SENSOR_TYPES.items()
    }

    return known_available_resources


async def _validate_path(path):
    """ make sure path is valid """
    if path in os.path.dirname(__file__):
        return False
    else:
        return True


async def _check_ffmpeg():
    """ check if ffmpeg is installed """
    if which("ffmpeg") is not None:
        return True
    else:
        return False


async def _test_login(host, port, user, pwd):
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
        host = ""
        port = DEFAULT_PORT
        username = ""
        password = ""

        if user_input is not None:
            if ATTR_HOST in user_input:
                host = user_input[ATTR_HOST]
            if ATTR_PORT in user_input:
                port = user_input[ATTR_PORT]
            if ATTR_USERNAME in user_input:
                username = user_input[ATTR_USERNAME]
            if ATTR_PASSWORD in user_input:
                password = user_input[ATTR_PASSWORD]

        data_schema = OrderedDict()
        data_schema[vol.Required(ATTR_HOST, default=host)] = str
        data_schema[vol.Required(ATTR_PORT, default=port)] = vol.Coerce(int)
        data_schema[vol.Required(ATTR_USERNAME, default=username)] = str
        data_schema[vol.Required(ATTR_PASSWORD, default=password)] = str
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=self._errors
        )

    async def async_step_config_2(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            valid = await _validate_path(user_input[ATTR_IMAGE_PATH])
            if valid:
                if user_input[ATTR_GENERATE_MP4]:
                    valid = await _check_ffmpeg()
                else:
                    valid = True

                if valid:
                    if user_input[ATTR_FOLDER] is not None:
                        if not user_input[ATTR_IMAGE_PATH].endswith("/"):
                            user_input[ATTR_IMAGE_PATH] += "/"
                            self._data.update(user_input)
                    return self.async_create_entry(
                        title=self._data[CONF_HOST], data=self._data
                    )
                else:
                    self._errors["base"] = "ffmpeg_not_found"
            else:
                self._errors["base"] = "invalid_path"

            return await self._show_config_2(user_input)

        return await self._show_config_2(user_input)

    async def _show_config_2(self, user_input):
        """ Step 2 setup """

        # Defaults
        folder = DEFAULT_FOLDER
        scan_interval = DEFAULT_SCAN_INTERVAL
        image_path = self.hass.config.path() + DEFAULT_PATH
        gif_duration = DEFAULT_GIF_DURATION
        image_security = DEFAULT_IMAGE_SECURITY
        generate_mp4 = DEFAULT_FFMPEG
        known_available_resources = get_resources()
        amazon_fwds = ""

        account = imaplib.IMAP4_SSL(self._data[ATTR_HOST], self._data[ATTR_PORT])
        status, data = account.login(
            self._data[ATTR_USERNAME], self._data[ATTR_PASSWORD]
        )
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
            if ATTR_FOLDER in user_input:
                folder = user_input[ATTR_FOLDER]
            if ATTR_SCAN_INTERVAL in user_input:
                scan_interval = user_input[ATTR_SCAN_INTERVAL]
            if ATTR_IMAGE_PATH in user_input:
                image_path = user_input[ATTR_IMAGE_PATH]
            if ATTR_GIF_DURATION in user_input:
                gif_duration = user_input[ATTR_GIF_DURATION]
            if ATTR_IMAGE_SECURITY in user_input:
                image_security = user_input[ATTR_IMAGE_SECURITY]
            if ATTR_GENERATE_MP4 in user_input:
                generate_mp4 = user_input[ATTR_GENERATE_MP4]
            if ATTR_AMAZON_FWDS in user_input:
                amazon_fwds = user_input[ATTR_AMAZON_FWDS]

        data_schema = OrderedDict()
        data_schema[vol.Required(ATTR_FOLDER, default=folder)] = vol.In(mailboxes)
        data_schema[vol.Required(CONF_RESOURCES, default=[])] = cv.multi_select(
            known_available_resources
        )
        data_schema[vol.Optional(ATTR_AMAZON_FWDS, default=amazon_fwds)] = str
        data_schema[
            vol.Optional(ATTR_SCAN_INTERVAL, default=scan_interval)
        ] = vol.Coerce(int)
        data_schema[vol.Optional(ATTR_IMAGE_PATH, default=image_path)] = str
        data_schema[vol.Optional(ATTR_GIF_DURATION, default=gif_duration)] = vol.Coerce(
            int
        )
        data_schema[vol.Optional(ATTR_IMAGE_SECURITY, default=image_security)] = bool
        data_schema[vol.Optional(ATTR_GENERATE_MP4, default=generate_mp4)] = bool
        return self.async_show_form(
            step_id="config_2", data_schema=vol.Schema(data_schema), errors=self._errors
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

        # Defaults
        host = self.config.options.get(CONF_HOST)
        port = self.config.options.get(CONF_PORT)
        username = self.config.options.get(CONF_USERNAME)
        password = self.config.options.get(CONF_PASSWORD)

        if user_input is not None:
            if ATTR_HOST in user_input:
                host = user_input[ATTR_HOST]
            if ATTR_PORT in user_input:
                port = user_input[ATTR_PORT]
            if ATTR_USERNAME in user_input:
                username = user_input[ATTR_USERNAME]
            if ATTR_PASSWORD in user_input:
                password = user_input[ATTR_PASSWORD]

        data_schema = OrderedDict()
        data_schema[vol.Required(ATTR_HOST, default=host)] = str
        data_schema[vol.Required(ATTR_PORT, default=port)] = vol.Coerce(int)
        data_schema[vol.Required(ATTR_USERNAME, default=username)] = str
        data_schema[vol.Required(ATTR_PASSWORD, default=password)] = str
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(data_schema), errors=self._errors
        )

    async def async_step_options_2(self, user_input=None):
        self._errors = {}
        if user_input is not None:
            self._data.update(user_input)
            valid = await _validate_path(user_input[ATTR_IMAGE_PATH])

            if valid:
                if user_input[ATTR_GENERATE_MP4]:
                    valid = await _check_ffmpeg()
                else:
                    valid = True

                if valid:
                    if user_input[ATTR_FOLDER] is not None:
                        if not user_input[ATTR_IMAGE_PATH].endswith("/"):
                            user_input[ATTR_IMAGE_PATH] += "/"
                            self._data.update(user_input)

                    return self.async_create_entry(title="", data=self._data)
                else:
                    self._errors["base"] = "ffmpeg_not_found"
            else:
                self._errors["base"] = "invalid_path"

            return await self._show_step_options_2(user_input)

        return await self._show_step_options_2(user_input)

    async def _show_step_options_2(self, user_input):
        """Step 2 of options."""

        # Defaults
        folder = self.config.options.get(CONF_FOLDER)
        scan_interval = self.config.options.get(CONF_SCAN_INTERVAL)
        image_path = self.config.options.get(CONF_PATH)
        gif_duration = self.config.options.get(CONF_DURATION)
        image_security = self.config.options.get(CONF_IMAGE_SECURITY)
        generate_mp4 = self.config.options.get(CONF_GENERATE_MP4)
        resources = self.config.options.get(CONF_RESOURCES)
        known_available_resources = get_resources()
        amazon_fwds = self.config.options.get(CONF_AMAZON_FWDS) or ""

        account = imaplib.IMAP4_SSL(self._data[ATTR_HOST], self._data[ATTR_PORT])
        status, data = account.login(
            self._data[ATTR_USERNAME], self._data[ATTR_PASSWORD]
        )
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
            if ATTR_FOLDER in user_input:
                folder = user_input[ATTR_FOLDER]
            if ATTR_SCAN_INTERVAL in user_input:
                scan_interval = user_input[ATTR_SCAN_INTERVAL]
            if ATTR_IMAGE_PATH in user_input:
                image_path = user_input[ATTR_IMAGE_PATH]
            if ATTR_GIF_DURATION in user_input:
                gif_duration = user_input[ATTR_GIF_DURATION]
            if ATTR_IMAGE_SECURITY in user_input:
                image_security = user_input[ATTR_IMAGE_SECURITY]
            if ATTR_GENERATE_MP4 in user_input:
                generate_mp4 = user_input[ATTR_GENERATE_MP4]
            if ATTR_AMAZON_FWDS in user_input:
                amazon_fwds = user_input[ATTR_AMAZON_FWDS]

        data_schema = OrderedDict()
        data_schema[vol.Required(ATTR_FOLDER, default=folder)] = vol.In(mailboxes)
        data_schema[vol.Required(CONF_RESOURCES, default=resources)] = cv.multi_select(
            known_available_resources
        )
        data_schema[vol.Optional(ATTR_AMAZON_FWDS, default=amazon_fwds)] = str
        data_schema[
            vol.Optional(ATTR_SCAN_INTERVAL, default=scan_interval)
        ] = vol.Coerce(int)
        data_schema[vol.Optional(ATTR_IMAGE_PATH, default=image_path)] = str
        data_schema[vol.Optional(ATTR_GIF_DURATION, default=gif_duration)] = vol.Coerce(
            int
        )
        data_schema[vol.Optional(ATTR_IMAGE_SECURITY, default=image_security)] = bool
        data_schema[vol.Optional(ATTR_GENERATE_MP4, default=generate_mp4)] = bool
        return self.async_show_form(
            step_id="options_2",
            data_schema=vol.Schema(data_schema),
            errors=self._errors,
        )
