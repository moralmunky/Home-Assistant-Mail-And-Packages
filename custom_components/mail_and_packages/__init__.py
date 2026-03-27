"""Mail and Packages Integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

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
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
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
    "CONF_GENERIC_CUSTOM_IMG",
    "CONF_GENERIC_CUSTOM_IMG_FILE",
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
    "DEFAULT_UPS_CUSTOM_IMG_FILE",
    "DEFAULT_WALMART_CUSTOM_IMG_FILE",
    "DOMAIN",
    "ISSUE_URL",
    "PLATFORMS",
    "VERSION",
    "MailAndPackagesConfigEntry",
    "MailAndPackagesData",
    "MailDataUpdateCoordinator",
    "const",
    "default_image_path",
    "hash_file",
]

_LOGGER = logging.getLogger(__name__)


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
    hass.data.setdefault(DOMAIN, {})
    updated_config = config_entry.data.copy()

    # Sort the resources
    updated_config[CONF_RESOURCES] = sorted(updated_config[CONF_RESOURCES])

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_config)

    # Variables for data coordinator
    config = config_entry.data

    # Setup the data coordinator
    coordinator = MailDataUpdateCoordinator(hass, config, config_entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    # Raise ConfEntryNotReady if coordinator didn't update
    if not coordinator.last_update_success:
        _LOGGER.error("Error updating sensor data: %s", coordinator.last_exception)
        raise ConfigEntryNotReady

    config_entry.runtime_data = MailAndPackagesData(coordinator=coordinator, cameras=[])

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


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


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER

    _LOGGER.debug("Migrating from version %s", version)
    updated_config = {**config_entry.data}

    _migrate_legacy_versions(updated_config, version, config_entry)
    _apply_default_config(updated_config)

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry,
            data=updated_config,
            version=new_version,
        )

    _LOGGER.debug("Migration complete to version %s", new_version)

    return True


def _migrate_legacy_versions(updated_config, version, config_entry):
    """Handle migration of legacy versions."""
    _migrate_versions_1_to_3(updated_config, version, config_entry)
    _migrate_versions_4_to_16(updated_config, version)


def _migrate_versions_1_to_3(updated_config, version, config_entry):
    """Handle migration for versions 1 to 3."""
    if version == 1:
        if CONF_AMAZON_FWDS in updated_config:
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
        if not config_entry.data.get(CONF_IMAGE_SECURITY, False):
            updated_config[CONF_IMAGE_SECURITY] = True

        # Add default Amazon Days configuration
        updated_config[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS

    # 2 -> 4
    if version <= 2:
        # Force path change
        updated_config[CONF_PATH] = "custom_components/mail_and_packages/images/"

        # Always on image security
        if not config_entry.data.get(CONF_IMAGE_SECURITY, False):
            updated_config[CONF_IMAGE_SECURITY] = True

        # Add default Amazon Days configuration
        updated_config[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS

    if version <= 3:
        # Add default Amazon Days configuration
        updated_config[CONF_AMAZON_DAYS] = DEFAULT_AMAZON_DAYS


def _migrate_versions_4_to_16(updated_config, version):
    """Handle migration for versions 4 to 16."""
    _migrate_versions_4_to_7(updated_config, version)
    _migrate_versions_15_to_16(updated_config, version)


def _migrate_versions_4_to_7(updated_config, version):
    """Handle migration for versions 4 to 7."""
    if version <= 4:
        if CONF_AMAZON_FWDS in updated_config and updated_config[CONF_AMAZON_FWDS] == [
            '""',
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


def _migrate_versions_15_to_16(updated_config, version):
    """Handle migration for versions 15 to 16."""
    if version <= 15:
        if updated_config.get(CONF_IMAP_SECURITY) == "startTLS":
            updated_config[CONF_IMAP_SECURITY] = "SSL"
        if CONF_AUTH_TYPE not in updated_config:
            updated_config[CONF_AUTH_TYPE] = AUTH_TYPE_PASSWORD

    if version <= 16:
        if "auth" in updated_config:
            auth_data = updated_config.pop("auth")
            updated_config.update(auth_data)


def _apply_default_config(updated_config):
    """Ensure default configurations are present."""
    # Require configs on all migration paths
    if CONF_PATH not in updated_config:
        updated_config[CONF_PATH] = "custom_components/mail_and_packages/images/"

    if CONF_RESOURCES not in updated_config:
        updated_config[CONF_RESOURCES] = []

    # Add default for image storage config
    if CONF_STORAGE not in updated_config:
        updated_config[CONF_STORAGE] = "custom_components/mail_and_packages/images/"

    _apply_courier_image_defaults(updated_config)
    _apply_walmart_generic_fedex_defaults(updated_config)


def _apply_courier_image_defaults(updated_config):
    """Apply default Amazon and UPS custom image configurations."""
    if CONF_AMAZON_CUSTOM_IMG not in updated_config:
        updated_config[CONF_AMAZON_CUSTOM_IMG] = False
    if CONF_AMAZON_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_AMAZON_CUSTOM_IMG_FILE] = DEFAULT_AMAZON_CUSTOM_IMG_FILE
    if CONF_UPS_CUSTOM_IMG not in updated_config:
        updated_config[CONF_UPS_CUSTOM_IMG] = False
    if CONF_UPS_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_UPS_CUSTOM_IMG_FILE] = DEFAULT_UPS_CUSTOM_IMG_FILE


def _apply_walmart_generic_fedex_defaults(updated_config):
    """Apply default Walmart, Generic and FedEx custom image configurations."""
    if CONF_WALMART_CUSTOM_IMG not in updated_config:
        updated_config[CONF_WALMART_CUSTOM_IMG] = False
    if CONF_WALMART_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_WALMART_CUSTOM_IMG_FILE] = DEFAULT_WALMART_CUSTOM_IMG_FILE
    if CONF_GENERIC_CUSTOM_IMG not in updated_config:
        updated_config[CONF_GENERIC_CUSTOM_IMG] = False
    if CONF_GENERIC_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_GENERIC_CUSTOM_IMG_FILE] = DEFAULT_GENERIC_CUSTOM_IMG_FILE

    if CONF_FEDEX_CUSTOM_IMG not in updated_config:
        updated_config[CONF_FEDEX_CUSTOM_IMG] = False
    if CONF_FEDEX_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_FEDEX_CUSTOM_IMG_FILE] = DEFAULT_FEDEX_CUSTOM_IMG_FILE
