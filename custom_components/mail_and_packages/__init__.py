"""Mail and Packages Integration."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    CONFIG_VER,
    COORDINATOR,
    DEFAULT_AMAZON_DAYS,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
)
from .helpers import process_emails

_LOGGER = logging.getLogger(__name__)


async def async_setup(
    hass: HomeAssistant, config_entry: ConfigEntry
):  # pylint: disable=unused-argument
    """Disallow configuration via YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report them here: %s",
        VERSION,
        ISSUE_URL,
    )
    hass.data.setdefault(DOMAIN, {})
    updated_config = config_entry.data.copy()

    # Sort the resources
    updated_config[CONF_RESOURCES] = sorted(updated_config[CONF_RESOURCES])

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_config)

    # Variables for data coordinator
    config = config_entry.data

    # Setup the data coordinator
    coordinator = MailDataUpdateCoordinator(hass, config)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    # Raise ConfEntryNotReady if coordinator didn't update
    if not coordinator.last_update_success:
        _LOGGER.error("Error updating sensor data: %s", coordinator.last_exception)
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Attempting to unload sensors from the %s integration", DOMAIN)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed sensors from the %s integration", DOMAIN)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER

    _LOGGER.debug("Migrating from version %s", version)
    updated_config = {**config_entry.data}

    # 1 -> 4: Migrate format
    if version == 1:
        if CONF_AMAZON_FWDS in updated_config.keys():
            if not isinstance(updated_config[CONF_AMAZON_FWDS], list):
                updated_config[CONF_AMAZON_FWDS] = [
                    x.strip() for x in updated_config[CONF_AMAZON_FWDS].split(",")
                ]
            else:
                updated_config[CONF_AMAZON_FWDS] = []
        else:
            _LOGGER.warning("Missing configuration data: %s", CONF_AMAZON_FWDS)

        # Force path change
        updated_config[CONF_PATH] = "custom_components/mail_and_packages/images/"

        # Always on image security
        if not config_entry.data[CONF_IMAGE_SECURITY]:
            updated_config[CONF_IMAGE_SECURITY] = True

        # Add default Amazon Days configuration
        updated_config[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS

    # 2 -> 4
    if version <= 2:
        # Force path change
        updated_config[CONF_PATH] = "custom_components/mail_and_packages/images/"

        # Always on image security
        if not config_entry.data[CONF_IMAGE_SECURITY]:
            updated_config[CONF_IMAGE_SECURITY] = True

        # Add default Amazon Days configuration
        updated_config[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS

    if version <= 3:
        # Add default Amazon Days configuration
        updated_config[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS

    if version <= 4:
        if CONF_AMAZON_FWDS in updated_config and updated_config[CONF_AMAZON_FWDS] == [
            '""'
        ]:
            updated_config[CONF_AMAZON_FWDS] = []

    if version <= 5:
        if CONF_VERIFY_SSL not in updated_config:
            updated_config[CONF_VERIFY_SSL] = True

    if version <= 6:
        if CONF_IMAP_SECURITY not in updated_config:
            updated_config[CONF_IMAP_SECURITY] = "SSL"

    if version <= 7:
        if CONF_AMAZON_DOMAIN not in updated_config:
            updated_config[CONF_AMAZON_DOMAIN] = "amazon.com"

    if CONF_PATH not in updated_config:
        updated_config[CONF_PATH] = "custom_components/mail_and_packages/images/"

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=new_version
        )

    _LOGGER.debug("Migration complete to version %s", new_version)

    return True


class MailDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching mail data."""

    def __init__(self, hass, config):
        """Initialize."""
        self.interval = timedelta(minutes=config.get(CONF_SCAN_INTERVAL))
        self.name = f"Mail and Packages ({config.get(CONF_HOST)})"
        self.timeout = config.get(CONF_IMAP_TIMEOUT)
        self.config = config
        self.hass = hass
        self._data = {}

        _LOGGER.debug("Data will be update every %s", self.interval)

        super().__init__(hass, _LOGGER, name=self.name, update_interval=self.interval)

    async def _async_update_data(self):
        """Fetch data."""
        async with asyncio.timeout(self.timeout):
            try:
                data = await self.hass.async_add_executor_job(
                    process_emails, self.hass, self.config
                )
            except Exception as error:
                _LOGGER.error("Problem updating sensors: %s", error)
                raise UpdateFailed(error) from error

            if data:
                self._data = data
            return self._data
