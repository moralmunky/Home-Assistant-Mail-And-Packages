"""Mail and Packages Integration V2."""
import asyncio
import logging
from datetime import timedelta

from async_timeout import timeout # This might be part of HA's core libraries or might need to be imported differently
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES, CONF_PASSWORD, CONF_USERNAME, CONF_PORT # Added for coordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# V2 specific imports (will be created)
from .const import (
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_FWDS,
    CONF_IMAP_TIMEOUT,
    CONF_PATH, # This is image path, may need renaming for clarity if utils handles paths generally
    CONF_SCAN_INTERVAL,
    CONF_FOLDER, # Added for coordinator
    COORDINATOR,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_IMAP_TIMEOUT,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
    DEFAULT_AMAZON_FWDS,
    DEFAULT_ALLOW_EXTERNAL, # Added for completeness
    DEFAULT_PATH as DEFAULT_IMAGE_PATH_CONST, # Renamed to avoid conflict
)

from .coordinator import MailDataUpdateCoordinatorV2
from .utils import generate_image_path # Renamed from default_image_path_v2 for clarity
from .exceptions import UpdateFailed

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Mail and Packages V2 from a config entry."""
    _LOGGER.info(
        "Version %s (%s) is starting. Report issues at: %s",
        VERSION,
        DOMAIN,
        ISSUE_URL,
    )

    hass.data.setdefault(DOMAIN, {})

    # --- Configuration Handling & Migration ---
    # For V2, we assume the config_entry.data is the primary source.
    # Options flow will handle changes post-setup.
    # If migrating from an older version of *this* (v2) component's config schema,
    # it would be handled by async_migrate_entry before this setup.

    current_data = config_entry.data.copy()
    updated_data = current_data.copy() # Start with current data

    # Ensure essential defaults for any missing keys
    if CONF_AMAZON_FWDS not in updated_data:
        updated_data[CONF_AMAZON_FWDS] = DEFAULT_AMAZON_FWDS
    elif isinstance(updated_data[CONF_AMAZON_FWDS], str): # Ensure it's a list
        tmp_fwds = updated_data[CONF_AMAZON_FWDS]
        if not tmp_fwds or tmp_fwds == '""':
            updated_data[CONF_AMAZON_FWDS] = []
        else:
            updated_data[CONF_AMAZON_FWDS] = [x.strip() for x in tmp_fwds.split(",") if x.strip()]

    if CONF_IMAP_TIMEOUT not in updated_data:
        updated_data[CONF_IMAP_TIMEOUT] = DEFAULT_IMAP_TIMEOUT

    if CONF_AMAZON_DAYS not in updated_data:
        updated_data[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS

    if CONF_ALLOW_EXTERNAL not in updated_data:
        updated_data[CONF_ALLOW_EXTERNAL] = DEFAULT_ALLOW_EXTERNAL

    if CONF_PATH not in updated_data: # Image specific path
        updated_data[CONF_PATH] = generate_image_path(hass, DEFAULT_IMAGE_PATH_CONST)
    else: # Ensure existing path is made absolute if it's relative
        updated_data[CONF_PATH] = generate_image_path(hass, updated_data[CONF_PATH])


    if CONF_RESOURCES in updated_data:
        updated_data[CONF_RESOURCES] = sorted(updated_data[CONF_RESOURCES])
    else:
        updated_data[CONF_RESOURCES] = [] # Default to empty list if not present

    # If data was updated with defaults, store it back
    if updated_data != current_data:
        hass.config_entries.async_update_entry(config_entry, data=updated_data)

    # --- Coordinator Setup ---
    coordinator = MailDataUpdateCoordinatorV2(hass, config_entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        # Error already logged by coordinator
        raise ConfigEntryNotReady(f"Initial data fetch failed for {config_entry.title}")

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    # --- Platform Setup ---
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # --- Listener for config entry updates (options flow) ---
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading %s config entry: %s", DOMAIN, config_entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        _LOGGER.debug("%s config entry unloaded successfully: %s", DOMAIN, config_entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.debug("Reloading %s config entry: %s", DOMAIN, config_entry.entry_id)
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating %s config entry from version %s", DOMAIN, config_entry.version)

    if config_entry.version == 1:
        # Example migration: If we introduced a new required key in version 2 of the config schema
        # new_data = {**config_entry.data}
        # if "new_required_key" not in new_data:
        #     new_data["new_required_key"] = "default_value"
        # config_entry.version = 2
        # hass.config_entries.async_update_entry(config_entry, data=new_data)
        # _LOGGER.info("Migrated %s config entry to version 2", DOMAIN)
        pass # No migrations defined yet for v2 schema, assuming current schema is version 1

    _LOGGER.debug("Migration to version %s successful for %s", config_entry.version, DOMAIN)
    return True

# Placeholder for exceptions.py - will be created in a later step
# """Custom exceptions for Mail and Packages V2."""
# from homeassistant.exceptions import HomeAssistantError
#
# class UpdateFailed(HomeAssistantError):
#     """Error to indicate an update failed."""
#
# class ImapConnectError(HomeAssistantError):
#     """Error to indicate an IMAP connection failed."""
#
# class ImapLoginError(HomeAssistantError):
#     """Error to indicate an IMAP login failed."""
#
# class EmailParsingError(HomeAssistantError):
#     """Error to indicate email parsing failed."""

# Placeholder for utils.py - will be created in a later step
# """Utility functions for Mail and Packages V2."""
# import os
# from homeassistant.core import HomeAssistant
# from homeassistant.config_entries import ConfigEntry
#
# def generate_image_path(hass: HomeAssistant, configured_path: str) -> str:
#     """Generate the absolute path for images, ensuring it's within www if intended for UI."""
#     # This function will need more robust logic to handle paths correctly,
#     # especially if they are intended to be served by HA's webserver (then must be under www).
#     # For now, a simplified version.
#     if not os.path.isabs(configured_path):
#         # If it's a relative path, assume it's relative to HA config dir
#         # This might need to change based on where images are stored for v2
#         return hass.config.path(configured_path)
#     return configured_path

# Placeholder for coordinator.py - will be created in a later step
# """DataUpdateCoordinator for Mail and Packages V2."""
# # ... imports ...
# class MailDataUpdateCoordinatorV2(DataUpdateCoordinator):
#     def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
#         self.config_entry = config_entry
#         # ... other initializations ...
#         super().__init__(...)
#     async def _async_update_data(self):
#         # ... logic to call imap_client, email_parser, etc. ...
#         return {}
