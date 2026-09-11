"""Config entry migration logic for Mail and Packages."""

import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import (
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
    CONF_PATH,
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
)
from .coordinator import MailAndPackagesConfigEntry

_LOGGER = logging.getLogger(__name__)

OAUTH_TOKEN_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "expires_at",
    "expires_in",
    "auth_implementation",
}


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: MailAndPackagesConfigEntry
) -> bool:
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER

    _LOGGER.debug("Migrating from version %s", version)
    updated_config = {**config_entry.data}
    updated_options = {**config_entry.options}

    _migrate_legacy_versions(updated_config, version, config_entry)
    _apply_default_config(updated_config)

    # Ensure non-IMAP options are removed from data and moved to options
    imap_keys = {
        CONF_HOST,
        CONF_PORT,
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_IMAP_SECURITY,
        CONF_VERIFY_SSL,
        CONF_AUTH_TYPE,
        *OAUTH_TOKEN_KEYS,
    }
    for key in list(updated_config.keys()):
        if key not in imap_keys:
            val = updated_config.pop(key)
            if key not in updated_options:
                updated_options[key] = val

    if updated_config != config_entry.data or updated_options != config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            data=updated_config,
            options=updated_options,
            version=new_version,
        )

    _LOGGER.debug("Migration complete to version %s", new_version)

    return True


def _migrate_legacy_versions(updated_config, version, config_entry):
    """Handle migration of legacy versions."""
    _migrate_versions_1_to_3(updated_config, version, config_entry)
    _migrate_versions_4_to_16(updated_config, version)
    _migrate_version_17(updated_config, version)
    _migrate_version_18(updated_config, version)


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


def _migrate_version_17(updated_config, version):
    """Handle migration for version 17."""
    if version <= 17:
        fwds = updated_config.get(CONF_FORWARDED_EMAILS)
        if isinstance(fwds, str):
            if fwds and fwds != "(none)":
                updated_config[CONF_FORWARDED_EMAILS] = [
                    e.strip() for e in fwds.split(",") if e.strip()
                ]
            else:
                updated_config.pop(CONF_FORWARDED_EMAILS, None)


def _migrate_version_18(updated_config, version):
    """Handle migration for version 18."""
    if version <= 18:
        if CONF_FOLDER in updated_config:
            folder = updated_config[CONF_FOLDER]
            if isinstance(folder, str):
                updated_config[CONF_FOLDER] = folder.strip('"')
            elif isinstance(folder, (list, tuple, set)):
                updated_config[CONF_FOLDER] = [
                    f.strip('"') for f in folder if isinstance(f, str)
                ]


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
    if CONF_HOME_DEPOT_CUSTOM_IMG not in updated_config:
        updated_config[CONF_HOME_DEPOT_CUSTOM_IMG] = False
    if CONF_HOME_DEPOT_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_HOME_DEPOT_CUSTOM_IMG_FILE] = (
            DEFAULT_HOME_DEPOT_CUSTOM_IMG_FILE
        )
