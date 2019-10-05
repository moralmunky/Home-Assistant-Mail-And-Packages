"""Mail and Packages Integration."""

import logging
import os
from datetime import timedelta, datetime, date

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT
)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
from .const import (
    DEFAULT_PORT,
    DEFAULT_FOLDER,
    DEFAULT_PATH,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    REQUIRED_FILES,
    STARTUP,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_FOLDER, default=DEFAULT_FOLDER): cv.string,
                vol.Optional(CONF_IMAGE_OUTPUT_PATH,
                             default=DEFAULT_PATH): cv.string,
            })
        )
    }
)


async def async_setup(hass, config):
    """Set up this integration using yaml."""
    if DOMAIN not in config:
        # Using config entries (UI COnfiguration)
        return True

    conf = config[DOMAIN]

    # startup message
    startup = STARTUP.format(name=DOMAIN, version=VERSION, issueurl=ISSUE_URL)
    _LOGGER.info(startup)

    # check all required files
    file_check = await check_files(hass)
    if not file_check:
        return False

    # Store config to be used during entry setup
    hass.data[DATA_CONF] = conf

    return True

async def async_setup_entry(hass, config_entry):
    """Set up this integration using UI."""
    conf = hass.data(DATA_CONF)

    # check all required files
    file_check = await check_files(hass)
    if not file_check:
        return False

    host = conf[CONF_HOST]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    port = conf[CONF_PORT]
    
    try:
        account = imaplib.IMAP4_SSL(host, port)
        rv, data = account.login(user, pwd)

    except Exception as exception:  # pylint: disable=broad-except
        _LOGGER.error(exception)
        raise ConfigEntryNotReady

    return True

async def check_files(hass):
    """Return bool that indicates if all files are present."""
    base = "{}/custom_components/{}/".format(hass.config.path(), DOMAIN)
    missing = []
    for file in REQUIRED_FILES:
        fullpath = "{}{}".format(base, file)
        if not os.path.exists(fullpath):
            missing.append(file)

    if missing:
        _LOGGER.critical("The following files are missing: %s", str(missing))
        returnvalue = False
    else:
        returnvalue = True

    return returnvalue


async def async_remove_entry(hass, config_entry):
    """Handle removal of an entry."""
    del hass.data[DOMAIN]

    _LOGGER.info("Successfully removed the Mail And Packages integration")

    return True