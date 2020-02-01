"""Mail and Packages Integration."""
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.config_entries import ConfigEntry

import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistantType, config: ConfigEntry):
    """ Disallow configuration via YAML """

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the saved entities."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    # hass.async_create_task(
    #     hass.config_entries.async_forward_entry_setup(entry, "camera")
    # )    

    return True


async def async_remove_entry(hass, config_entry):
    """Handle removal of an entry."""
    try:
        await hass.config_entries.async_forward_entry_unload(config_entry, DOMAIN)
        _LOGGER.info(
            "Successfully removed sensor from the mail_and_packages integration"
        )
    except ValueError:
        pass


async def update_listener(hass, entry):
    """Update listener."""
    entry.data = entry.options
    await hass.config_entries.async_forward_entry_unload(entry, DOMAIN)
    hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, DOMAIN))
