"""Mail and Packages Integration."""
from . import const
from .helpers import process_emails, update_time
import async_timeout
from datetime import timedelta
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config_entry):
    """ Disallow configuration via YAML """

    return True


async def async_setup_entry(hass, config_entry):
    """Load the saved entities."""
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report" " them here: %s",
        const.VERSION,
        const.ISSUE_URL,
    )
    config_entry.options = config_entry.data

    config = config_entry.data

    data = EmailData(hass, config)

    async def async_update_data():
        """Fetch data from NUT."""
        async with async_timeout.timeout(10):
            await hass.async_add_executor_job(data.update)
            if not data:
                raise UpdateFailed("Error fetching emails")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Mail and Packages Updater",
        update_method=async_update_data,
        update_interval=timedelta(
            minutes=config_entry.options.get(const.CONF_SCAN_INTERVAL)
        ),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if const.DOMAIN_DATA not in hass.data:
        hass.data[const.DOMAIN_DATA] = {}

    hass.data[const.DOMAIN_DATA][config_entry.entry_id] = {
        const.DATA: data,
        const.COORDINATOR: coordinator,
    }

    config_entry.add_update_listener(update_listener)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, const.PLATFORM)
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Handle removal of an entry."""
    try:
        await hass.config_entries.async_forward_entry_unload(
            config_entry, const.PLATFORM
        )
        _LOGGER.info(
            "Successfully removed sensor from the " + const.DOMAIN + " integration"
        )
    except ValueError:
        pass
    return True


async def update_listener(hass, config_entry):
    """Update listener."""
    config_entry.data = config_entry.options
    await hass.config_entries.async_reload(config_entry.entry_id)


class EmailData:
    """The class for handling the data retrieval."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self._hass = hass
        self._config = config
        self._host = config.get(CONF_HOST)
        self._scan_interval = config.get(const.CONF_SCAN_INTERVAL)
        self._data = None

        _LOGGER.debug("Config scan interval: %s", self._scan_interval)

    def update(self):
        """Get the latest data"""
        if self._host is not None:
            """Login to email server and select the folder"""
            self._data = process_emails(self._hass, self._config)
        else:
            _LOGGER.error("Host was left blank not attempting connection")

        _LOGGER.debug("Updated scan time: %s", update_time())
