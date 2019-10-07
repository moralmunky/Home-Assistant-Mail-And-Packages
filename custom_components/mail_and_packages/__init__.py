"""Mail and Packages Integration."""
from .const import (DOMAIN, CONF_FOLDER, CONF_PATH)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_PORT
)


async def async_setup(hass, config):

    conf = config.get(DOMAIN)

    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}

    return True

async def async_setup_entry(hass, entry):

    host = entry.data[CONF_HOST]

    config = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_USERNAME: entry.data[CONF_USERNAME],
        CONF_PASSWORD: entry.data[CONF_PASSWORD],
        CONF_PORT: entry.data[CONF_PORT],
        CONF_FOLDER: entry.data[CONF_FOLDER],
        CONF_PATH: entry.data[CONF_PATH]
    }

    if config is None:
        return False
    return True
