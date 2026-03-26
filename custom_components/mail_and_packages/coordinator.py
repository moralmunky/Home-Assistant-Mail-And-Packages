"""Data coordinator for Mail and Packages."""

import asyncio
import datetime
import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import anyio
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import const
from .const import (
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    AUTH_TYPE_PASSWORD,
    CONF_ALLOW_EXTERNAL,
    CONF_AUTH_TYPE,
    CONF_FOLDER,
    CONF_IMAP_SECURITY,
    CONF_IMAP_TIMEOUT,
    DOMAIN,
)
from .helpers import copy_images
from .shippers import get_shipper_for_sensor
from .utils.image import default_image_path, hash_file
from .utils.imap import login, selectfolder

_LOGGER = logging.getLogger(__name__)


@dataclass
class MailAndPackagesData:
    """Data for Mail and Packages integration."""

    coordinator: "MailDataUpdateCoordinator"
    cameras: list


type MailAndPackagesConfigEntry = ConfigEntry[MailAndPackagesData]


class MailDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching mail data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        config_entry: MailAndPackagesConfigEntry = None,
    ):
        """Initialize."""
        self.interval = timedelta(minutes=config.get(CONF_SCAN_INTERVAL))
        self.name = f"Mail and Packages ({config.get(CONF_HOST)})"
        self.timeout = config.get(CONF_IMAP_TIMEOUT)
        self.config = config
        self.config_entry = config_entry
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
                config = dict(self.config)

                # Refresh OAuth2 token if using OAuth authentication
                auth_type = config.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
                if auth_type != AUTH_TYPE_PASSWORD and self.config_entry:
                    try:
                        self.hass.data.setdefault(DOMAIN, {})
                        self.hass.data[DOMAIN]["oauth_provider"] = auth_type

                        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
                            self.hass, self.config_entry
                        )
                        session = config_entry_oauth2_flow.OAuth2Session(
                            self.hass, self.config_entry, implementation
                        )
                        await session.async_ensure_token_valid()
                        config["oauth_token"] = session.token["access_token"]
                    except Exception as err:
                        _LOGGER.error("Error refreshing OAuth token: %s", err)
                        raise UpdateFailed(
                            f"OAuth token refresh failed: {err}"
                        ) from err

                data = await self.process_emails(self.hass, config)
            except UpdateFailed:
                raise
            except Exception as error:
                _LOGGER.error("Problem updating sensors: %s", error)
                raise UpdateFailed(error) from error

            if data:
                self._data = data
                await self._binary_sensor_update()
            return self._data

    async def process_emails(self, hass: HomeAssistant, config: dict) -> dict:
        """Process emails and update sensors."""
        # Basic data structure
        data = {
            "mail_updated": datetime.datetime.now(datetime.UTC).isoformat(),
            "amazon_delivered_by_others": 0,
        }

        # Initialize all potential sensors to 0
        for sensor in const.SENSOR_TYPES:
            data[sensor] = 0

        # Login to IMAP
        try:
            account = await login(
                hass,
                config.get(CONF_HOST),
                config.get(CONF_PORT),
                config.get(CONF_USERNAME),
                config.get(CONF_PASSWORD),
                config.get(CONF_IMAP_SECURITY),
                config.get(CONF_VERIFY_SSL),
                config.get("oauth_token"),
            )
        except Exception as err:
            _LOGGER.error("Error logging into IMAP: %s", err)
            raise UpdateFailed(f"Login failed: {err}") from err

        # Select folder
        if not await selectfolder(account, config.get(CONF_FOLDER)):
            _LOGGER.error("Error selecting folder: %s", config.get(CONF_FOLDER))
            await account.logout()
            raise UpdateFailed(f"Folder selection failed: {config.get(CONF_FOLDER)}")

        # Process sensors
        today = datetime.datetime.now().strftime("%d-%b-%Y")
        resources = config.get(CONF_RESOURCES, [])

        for sensor in resources:
            await self._process_sensor(account, today, sensor, data, hass, config)

        await account.logout()

        # Copy image file to www directory if enabled
        if config.get(CONF_ALLOW_EXTERNAL):
            try:
                await hass.async_add_executor_job(copy_images, hass, config)
            except (OSError, ValueError) as err:
                _LOGGER.error("Problem creating: %s", err)

        return data

    async def _process_sensor(
        self,
        account,
        today,
        sensor,
        data,
        hass,
        config,
    ):
        """Process a single sensor."""
        shipper = get_shipper_for_sensor(hass, config, sensor)
        if not shipper:
            return

        try:
            result = await shipper.process(account, today, sensor)
            if isinstance(result, dict):
                # Some shippers return direct sensor data, others return {ATTR_COUNT: x, ...}
                if sensor in result:
                    if isinstance(result[sensor], dict):
                        data.update(result[sensor])
                    else:
                        data[sensor] = result[sensor]
                elif const.ATTR_COUNT in result:
                    data[sensor] = result[const.ATTR_COUNT]
                    # Merge tracking and other attributes if present
                    for key, value in result.items():
                        if key == const.ATTR_COUNT:
                            continue
                        if key == const.ATTR_TRACKING:
                            tracking_key = (
                                f"{'_'.join(sensor.split('_')[:-1])}_tracking"
                            )
                            data[tracking_key] = value
                        else:
                            data[key] = value
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error processing sensor %s: %s", sensor, err)

    async def _binary_sensor_update(self):
        """Update binary sensor states."""
        # USPS uses different attributes (ATTR_IMAGE_NAME instead of ATTR_*_IMAGE)
        attributes = (ATTR_IMAGE_NAME, ATTR_IMAGE_PATH)
        if set(attributes).issubset(self._data.keys()):
            image = self._data[ATTR_IMAGE_NAME]
            path = default_image_path(self.hass, self.config)
            usps_image = f"{path}/{image}"
            usps_none = f"{Path(__file__).parent}/mail_none.gif"
            usps_check = await anyio.Path(usps_image).exists()
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

                image_check = await anyio.Path(delivery_image).exists()
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
