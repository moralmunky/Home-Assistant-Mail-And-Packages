"""Mail and Packages Integration."""

import asyncio
import logging
import os
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const
from .const import (
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
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
    COORDINATOR,
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
from .helpers import default_image_path, hash_file, process_emails

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config_entry: ConfigEntry):  # pylint: disable=unused-argument
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


async def async_remove_config_entry_device(  # pylint: disable-next=unused-argument
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove config entry from a device if its no longer present."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and config_entry.runtime_data.get_device(identifier[1])
    )


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


async def async_migrate_entry(hass, config_entry):  # noqa: C901
    """Migrate an old config entry."""
    version = config_entry.version
    new_version = CONFIG_VER

    _LOGGER.debug("Migrating from version %s", version)
    updated_config = {**config_entry.data}

    # 1 -> 4: Migrate format
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

    # Require configs on all migration paths

    if CONF_PATH not in updated_config:
        updated_config[CONF_PATH] = "custom_components/mail_and_packages/images/"

    if CONF_RESOURCES not in updated_config:
        updated_config[CONF_RESOURCES] = []

    # Add default for image storage config
    if CONF_STORAGE not in updated_config:
        updated_config[CONF_STORAGE] = "custom_components/mail_and_packages/images/"

    # Add default custom image configurations
    if CONF_AMAZON_CUSTOM_IMG not in updated_config:
        updated_config[CONF_AMAZON_CUSTOM_IMG] = False
    if CONF_AMAZON_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_AMAZON_CUSTOM_IMG_FILE] = DEFAULT_AMAZON_CUSTOM_IMG_FILE
    if CONF_UPS_CUSTOM_IMG not in updated_config:
        updated_config[CONF_UPS_CUSTOM_IMG] = False
    if CONF_UPS_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_UPS_CUSTOM_IMG_FILE] = DEFAULT_UPS_CUSTOM_IMG_FILE

    # Add default Walmart and Generic custom image configurations
    if CONF_WALMART_CUSTOM_IMG not in updated_config:
        updated_config[CONF_WALMART_CUSTOM_IMG] = False
    if CONF_WALMART_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_WALMART_CUSTOM_IMG_FILE] = DEFAULT_WALMART_CUSTOM_IMG_FILE
    if CONF_GENERIC_CUSTOM_IMG not in updated_config:
        updated_config[CONF_GENERIC_CUSTOM_IMG] = False
    if CONF_GENERIC_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_GENERIC_CUSTOM_IMG_FILE] = DEFAULT_GENERIC_CUSTOM_IMG_FILE

    # Add default FedEx
    if CONF_FEDEX_CUSTOM_IMG not in updated_config:
        updated_config[CONF_FEDEX_CUSTOM_IMG] = False
    if CONF_FEDEX_CUSTOM_IMG_FILE not in updated_config:
        updated_config[CONF_FEDEX_CUSTOM_IMG_FILE] = DEFAULT_FEDEX_CUSTOM_IMG_FILE

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
        self._file_mtime_cache = {}
        self._hash_cache = {}

        _LOGGER.debug("Data will be update every %s", self.interval)

        super().__init__(hass, _LOGGER, name=self.name, update_interval=self.interval)

    async def _get_file_hash_if_changed(self, file_path):
        """Only hash file if mtime changed."""
        try:
            mtime = await self.hass.async_add_executor_job(os.path.getmtime, file_path)
            if (
                file_path in self._file_mtime_cache
                and self._file_mtime_cache[file_path] == mtime
            ):
                return self._hash_cache.get(file_path)

            # File changed, re-hash
            file_hash = await self.hass.async_add_executor_job(hash_file, file_path)
            self._file_mtime_cache[file_path] = mtime
            self._hash_cache[file_path] = file_hash
        except OSError:
            return None
        else:
            return file_hash

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
                await self._binary_sensor_update()
            return self._data

    async def _binary_sensor_update(self):
        """Update binary sensor states."""
        # USPS uses different attributes (ATTR_IMAGE_NAME instead of ATTR_*_IMAGE)
        attributes = (ATTR_IMAGE_NAME, ATTR_IMAGE_PATH)
        if set(attributes).issubset(self._data.keys()):
            image = self._data[ATTR_IMAGE_NAME]
            path = default_image_path(self.hass, self.config)
            usps_image = f"{path}/{image}"
            usps_none = f"{Path(__file__).parent}/mail_none.gif"
            usps_check = Path(usps_image).exists()
            _LOGGER.debug("USPS Check: %s", usps_check)
            if usps_check:
                # Optimized: Use _get_file_hash_if_changed
                image_hash = await self._get_file_hash_if_changed(usps_image)
                none_hash = await self._get_file_hash_if_changed(usps_none)

                _LOGGER.debug("USPS Image hash: %s", image_hash)
                _LOGGER.debug("USPS None hash: %s", none_hash)

                if image_hash != none_hash:
                    self._data["usps_update"] = True
                else:
                    self._data["usps_update"] = False

        # Handle generic delivery cameras (Amazon, UPS, Walmart, FedEx, Generic) with unified logic
        # Derive camera list dynamically from CAMERA_DATA, excluding usps_camera and generic_camera
        delivery_cameras = [
            camera_type.replace("_camera", "")
            for camera_type in const.CAMERA_DATA
            if camera_type not in ("usps_camera", "generic_camera")
        ]

        for base_name in delivery_cameras:
            # Derive attribute and config keys dynamically
            image_attr_name = f"ATTR_{base_name.upper()}_IMAGE"
            image_attr = getattr(const, image_attr_name, None)
            if not image_attr:
                continue

            custom_img_key = getattr(
                const, f"CONF_{base_name.upper()}_CUSTOM_IMG", None
            )
            custom_img_file_key = getattr(
                const, f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE", None
            )
            update_key = f"{base_name}_update"

            attributes = (image_attr, ATTR_IMAGE_PATH)
            _LOGGER.debug("%s attributes check: %s", base_name.title(), attributes)
            if set(attributes).issubset(self._data.keys()):
                image = self._data[image_attr]
                _LOGGER.debug(
                    "%s image from coordinator data: %s", base_name.title(), image
                )
                # Normalize path to avoid double slashes
                image_path = (
                    default_image_path(self.hass, self.config).rstrip("/") + "/"
                )
                path = f"{image_path}{base_name}/"
                # Use absolute path for file existence check
                delivery_image_relative = f"{path}{image}"
                delivery_image = f"{self.hass.config.path()}/{delivery_image_relative}"
                _LOGGER.debug(
                    "Full %s image path: %s", base_name.title(), delivery_image
                )

                if custom_img_key and self.config.get(custom_img_key):
                    none_image = self.config.get(custom_img_file_key)
                else:
                    none_image = (
                        f"{Path(__file__).parent}/no_deliveries_{base_name}.jpg"
                    )

                image_check = Path(delivery_image).exists()
                _LOGGER.debug("%s Check: %s", base_name.title(), image_check)
                if image_check:
                    # Optimized: Use _get_file_hash_if_changed
                    image_hash = await self._get_file_hash_if_changed(delivery_image)
                    none_hash = await self._get_file_hash_if_changed(none_image)

                    _LOGGER.debug("%s Image hash: %s", base_name.title(), image_hash)
                    _LOGGER.debug("%s None hash: %s", base_name.title(), none_hash)

                    if image_hash != none_hash:
                        self._data[update_key] = True
                    else:
                        self._data[update_key] = False
