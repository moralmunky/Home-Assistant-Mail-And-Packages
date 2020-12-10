"""Mail and Packages Integration."""
import logging
from datetime import timedelta

import async_timeout
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const
from .helpers import process_emails, update_time

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
    hass.data.setdefault(const.DOMAIN, {})
    config_entry.options = config_entry.data

    config = config_entry.data

    async def async_update_data():
        """Fetch data """
        async with async_timeout.timeout(30):
            return await hass.async_add_executor_job(process_emails, hass, config)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Mail and Packages ({config.get(CONF_HOST)})",
        update_method=async_update_data,
        update_interval=timedelta(
            minutes=config_entry.options.get(const.CONF_SCAN_INTERVAL)
        ),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[const.DOMAIN][config_entry.entry_id] = {
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
            "Successfully removed sensor from the %s integration", const.DOMAIN
        )
    except ValueError:
        pass
    return True


async def update_listener(hass, config_entry):
    """Update listener."""
    config_entry.data = config_entry.options
    await hass.config_entries.async_forward_entry_unload(config_entry, const.PLATFORM)
    hass.async_add_job(
        hass.config_entries.async_forward_entry_setup(config_entry, const.PLATFORM)
    )
