"""Mail and Packages Integration."""
import logging
from datetime import timedelta

import async_timeout
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_IMAGE_SECURITY,
    CONF_IMAP_TIMEOUT,
    COORDINATOR,
    CONF_AMAZON_FWDS,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    ISSUE_URL,
    PLATFORM,
    VERSION,
)
from .helpers import process_emails

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config_entry):
    """ Disallow configuration via YAML """

    return True


async def async_setup_entry(hass, config_entry):
    """Load the saved entities."""
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report" " them here: %s",
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})
    updated_config = config_entry.data.copy()

    # Set default image path
    if CONF_PATH not in config_entry.data.keys():
        updated_config[CONF_PATH] = "www/mail_and_packages/"
    # Set image security always on
    if CONF_IMAGE_SECURITY not in config_entry.data.keys():
        updated_config[CONF_IMAGE_SECURITY] = True

    # Force path update
    if config_entry.data[CONF_PATH] != "www/mail_and_packages/":
        updated_config = config_entry.data.copy()
        updated_config[CONF_PATH] = "www/mail_and_packages/"

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_config)

    config_entry.options = config_entry.data

    config = config_entry.data

    async def async_update_data():
        """Fetch data """
        async with async_timeout.timeout(config.get(CONF_IMAP_TIMEOUT)):
            return await hass.async_add_executor_job(process_emails, hass, config)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Mail and Packages ({config.get(CONF_HOST)})",
        update_method=async_update_data,
        update_interval=timedelta(minutes=config_entry.options.get(CONF_SCAN_INTERVAL)),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    config_entry.add_update_listener(update_listener)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, PLATFORM)
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Handle removal of an entry."""
    try:
        await hass.config_entries.async_forward_entry_unload(config_entry, PLATFORM)
        _LOGGER.info("Successfully removed sensor from the %s integration", DOMAIN)
    except ValueError:
        pass
    return True


async def update_listener(hass, config_entry):
    """Update listener."""
    config_entry.data = config_entry.options
    await hass.config_entries.async_forward_entry_unload(config_entry, PLATFORM)
    hass.async_add_job(
        hass.config_entries.async_forward_entry_setup(config_entry, PLATFORM)
    )


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version

    # 1 -> 3: Migrate format
    if version == 1:
        _LOGGER.debug("Migrating from version %s", version)
        updated_config = config_entry.data.copy()

        if CONF_AMAZON_FWDS in updated_config.keys():
            if not isinstance(updated_config[CONF_AMAZON_FWDS], list):
                updated_config[CONF_AMAZON_FWDS] = updated_config[
                    CONF_AMAZON_FWDS
                ].split(",")
        else:
            _LOGGER.warn("Missing configuration data: %s", CONF_AMAZON_FWDS)

        # Force path change
        updated_config[CONF_PATH] = "www/mail_and_packages/"

        # Always on image security
        if not config_entry.data[CONF_IMAGE_SECURITY]:
            updated_config[CONF_IMAGE_SECURITY] = True

        if updated_config != config_entry.data:
            hass.config_entries.async_update_entry(config_entry, data=updated_config)

        config_entry.version = 3
        _LOGGER.debug("Migration to version %s complete", config_entry.version)

    if version == 2:
        _LOGGER.debug("Migrating from version %s", version)
        updated_config = config_entry.data.copy()

        # Force path change
        updated_config[CONF_PATH] = "www/mail_and_packages/"

        # Always on image security
        if not config_entry.data[CONF_IMAGE_SECURITY]:
            updated_config[CONF_IMAGE_SECURITY] = True

        if updated_config != config_entry.data:
            hass.config_entries.async_update_entry(config_entry, data=updated_config)

        config_entry.version = 3
        _LOGGER.debug("Migration to version %s complete", config_entry.version)

    return True
