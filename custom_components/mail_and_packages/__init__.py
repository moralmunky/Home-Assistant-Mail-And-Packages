"""Mail and Packages Integration."""
import logging
from datetime import timedelta

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_FWDS,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    COORDINATOR,
    DEFAULT_IMAP_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    PLATFORM,
    VERSION,
)
from .helpers import default_image_path, process_emails

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config_entry):
    """ Disallow configuration via YAML """

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report" " them here: %s",
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})
    updated_config = config_entry.data.copy()

    # Set amazon fwd blank if missing
    if CONF_AMAZON_FWDS not in updated_config.keys():
        updated_config[CONF_AMAZON_FWDS] = []

    # Set default timeout if missing
    if CONF_IMAP_TIMEOUT not in updated_config.keys():
        updated_config[CONF_IMAP_TIMEOUT] = DEFAULT_IMAP_TIMEOUT

    # Set external path off by default
    if CONF_ALLOW_EXTERNAL not in config_entry.data.keys():
        updated_config[CONF_ALLOW_EXTERNAL] = False

    updated_config[CONF_PATH] = default_image_path(hass, config_entry)

    # Set image security always on
    if CONF_IMAGE_SECURITY not in config_entry.data.keys():
        updated_config[CONF_IMAGE_SECURITY] = True

    # Sort the resources
    updated_config[CONF_RESOURCES] = sorted(updated_config[CONF_RESOURCES])

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_config)

    config_entry.add_update_listener(update_listener)

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
        update_interval=timedelta(minutes=config_entry.data.get(CONF_SCAN_INTERVAL)),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    try:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, PLATFORM)
        )
    except ValueError:
        pass

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    _LOGGER.debug("Attempting to unload sensors from the %s integration", DOMAIN)

    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, PLATFORM
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed sensors from the %s integration", DOMAIN)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""

    _LOGGER.debug("Attempting to reload sensors from the %s integration", DOMAIN)

    if config_entry.data == config_entry.options:
        _LOGGER.debug("No changes detected not reloading sensors.")
        return

    new_data = config_entry.options.copy()

    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=new_data,
    )

    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version

    # 1 -> 3: Migrate format
    if version == 1:
        _LOGGER.debug("Migrating from version %s", version)
        updated_config = config_entry.data.copy()

        if CONF_AMAZON_FWDS in updated_config.keys():
            if not isinstance(updated_config[CONF_AMAZON_FWDS], list):
                updated_config[CONF_AMAZON_FWDS] = [
                    x.strip() for x in updated_config[CONF_AMAZON_FWDS].split(",")
                ]
            else:
                updated_config[CONF_AMAZON_FWDS] = []
        else:
            _LOGGER.warn("Missing configuration data: %s", CONF_AMAZON_FWDS)

        # Force path change
        updated_config[CONF_PATH] = "images/mail_and_packages/"

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
        updated_config[CONF_PATH] = "images/mail_and_packages/"

        # Always on image security
        if not config_entry.data[CONF_IMAGE_SECURITY]:
            updated_config[CONF_IMAGE_SECURITY] = True

        if updated_config != config_entry.data:
            hass.config_entries.async_update_entry(config_entry, data=updated_config)

        config_entry.version = 3
        _LOGGER.debug("Migration to version %s complete", config_entry.version)

    return True
