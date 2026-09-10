"""Mail and Packages Integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_RESOURCES,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    device_registry as dr,
)

from . import const
from .const import (
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    AUTH_TYPE_PASSWORD,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_AUTH_TYPE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FOLDER,
    CONF_FORWARDED_EMAILS,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_HOME_DEPOT_CUSTOM_IMG,
    CONF_HOME_DEPOT_CUSTOM_IMG_FILE,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_VERIFY_SSL,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    CONFIG_VER,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
    DEFAULT_GENERIC_CUSTOM_IMG_FILE,
    DEFAULT_HOME_DEPOT_CUSTOM_IMG_FILE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
)
from .coordinator import (
    MailAndPackagesConfigEntry,
    MailAndPackagesData,
    MailDataUpdateCoordinator,
)
from .migrate import async_migrate_entry
from .utils.image import default_image_path, hash_file

__all__ = [
    "ATTR_IMAGE_NAME",
    "ATTR_IMAGE_PATH",
    "AUTH_TYPE_PASSWORD",
    "CONFIG_VER",
    "CONF_AMAZON_CUSTOM_IMG",
    "CONF_AMAZON_CUSTOM_IMG_FILE",
    "CONF_AMAZON_DAYS",
    "CONF_AMAZON_DOMAIN",
    "CONF_AMAZON_FWDS",
    "CONF_AUTH_TYPE",
    "CONF_FEDEX_CUSTOM_IMG",
    "CONF_FEDEX_CUSTOM_IMG_FILE",
    "CONF_FOLDER",
    "CONF_FORWARDED_EMAILS",
    "CONF_GENERIC_CUSTOM_IMG",
    "CONF_GENERIC_CUSTOM_IMG_FILE",
    "CONF_HOME_DEPOT_CUSTOM_IMG",
    "CONF_HOME_DEPOT_CUSTOM_IMG_FILE",
    "CONF_IMAGE_SECURITY",
    "CONF_IMAP_SECURITY",
    "CONF_IMAP_TIMEOUT",
    "CONF_PATH",
    "CONF_SCAN_INTERVAL",
    "CONF_STORAGE",
    "CONF_UPS_CUSTOM_IMG",
    "CONF_UPS_CUSTOM_IMG_FILE",
    "CONF_VERIFY_SSL",
    "CONF_WALMART_CUSTOM_IMG",
    "CONF_WALMART_CUSTOM_IMG_FILE",
    "DEFAULT_AMAZON_CUSTOM_IMG_FILE",
    "DEFAULT_AMAZON_DAYS",
    "DEFAULT_FEDEX_CUSTOM_IMG_FILE",
    "DEFAULT_GENERIC_CUSTOM_IMG_FILE",
    "DEFAULT_HOME_DEPOT_CUSTOM_IMG_FILE",
    "DEFAULT_UPS_CUSTOM_IMG_FILE",
    "DEFAULT_WALMART_CUSTOM_IMG_FILE",
    "DOMAIN",
    "ISSUE_URL",
    "PLATFORMS",
    "VERSION",
    "MailAndPackagesConfigEntry",
    "MailAndPackagesData",
    "MailDataUpdateCoordinator",
    "async_migrate_entry",
    "const",
    "default_image_path",
    "hash_file",
]

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

OAUTH_TOKEN_KEYS = {
    CONF_TOKEN,
    CONF_ACCESS_TOKEN,
    "refresh_token",
    "expires_at",
    "expires_in",
    "auth_implementation",
}


async def async_setup(hass: HomeAssistant, config_entry: MailAndPackagesConfigEntry):  # pylint: disable=unused-argument
    """Disallow configuration via YAML."""
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MailAndPackagesConfigEntry,
) -> bool:
    """Load the saved entities."""
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report them here: %s",
        VERSION,
        ISSUE_URL,
    )
    # Merge data and options
    config = {**config_entry.data, **config_entry.options}

    # Sort the resources
    if CONF_RESOURCES in config:
        sorted_resources = sorted(config[CONF_RESOURCES])
        if sorted_resources != config[CONF_RESOURCES]:
            config[CONF_RESOURCES] = sorted_resources
            if CONF_RESOURCES in config_entry.options:
                hass.config_entries.async_update_entry(
                    config_entry,
                    options={**config_entry.options, CONF_RESOURCES: sorted_resources},
                )
            else:
                hass.config_entries.async_update_entry(
                    config_entry,
                    data={**config_entry.data, CONF_RESOURCES: sorted_resources},
                )

    # Setup the data coordinator
    coordinator = MailDataUpdateCoordinator(hass, config, config_entry)

    last_data = {
        k: v for k, v in config_entry.data.items() if k not in OAUTH_TOKEN_KEYS
    }
    config_entry.runtime_data = MailAndPackagesData(
        coordinator=coordinator,
        cameras=[],
        last_options=dict(config_entry.options),
        last_data=last_data,
    )

    # Fetch initial data in the background so setup doesn't block
    hass.async_create_task(coordinator.async_refresh())

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    return True


async def update_listener(
    hass: HomeAssistant, config_entry: MailAndPackagesConfigEntry
) -> None:
    """Update listener."""
    if config_entry.runtime_data:
        current_non_oauth_data = {
            k: v for k, v in config_entry.data.items() if k not in OAUTH_TOKEN_KEYS
        }
        if (
            config_entry.options == config_entry.runtime_data.last_options
            and current_non_oauth_data == config_entry.runtime_data.last_data
        ):
            _LOGGER.debug("Config entry update was token-only refresh; skipping reload")
            return

    _LOGGER.debug("Attempting to reload sensors from the %s integration", DOMAIN)
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(  # pylint: disable-next=unused-argument
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove config entry from a device if its no longer present."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and config_entry.runtime_data.get_device(identifier[1])
    )


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: MailAndPackagesConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Attempting to unload sensors from the %s integration", DOMAIN)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ],
        ),
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed sensors from the %s integration", DOMAIN)

    return unload_ok
