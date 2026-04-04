"""Data coordinator for Mail and Packages."""

import asyncio
import datetime
import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import anyio
from aioimaplib import IMAP4_SSL
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
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import const
from .const import (
    ATTR_IMAGE_PATH,
    ATTR_USPS_IMAGE,
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
from .utils.cache import EmailCache
from .utils.image import default_image_path, hash_file, image_file_name
from .utils.imap import InvalidAuth, login, selectfolder

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
                            self.hass,
                            self.config_entry,
                        )
                        session = config_entry_oauth2_flow.OAuth2Session(
                            self.hass,
                            self.config_entry,
                            implementation,
                        )
                        await session.async_ensure_token_valid()
                        config["oauth_token"] = session.token["access_token"]
                    except Exception as err:
                        _LOGGER.error("Error refreshing OAuth token: %s", err)
                        raise UpdateFailed(
                            f"OAuth token refresh failed: {err}",
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
        # Initialize defaults and image paths
        data = self._initialize_data()
        config = await self._setup_image_config(hass, config)

        # Connect to IMAP
        account = await self._get_imap_connection(config)
        try:
            cache = EmailCache(account)
            today = datetime.datetime.now().strftime("%d-%b-%Y")

            # Process logic
            shipper_data = await self._update_shippers(account, config, today, cache)
            data.update(shipper_data)

            # Aggregate global transit and delivered sensors
            self._aggregate_package_counts(data)
        finally:
            await account.logout()

        # Post-process external images
        if config.get(CONF_ALLOW_EXTERNAL):
            try:
                await hass.async_add_executor_job(copy_images, hass, config)
            except (OSError, ValueError) as err:
                _LOGGER.error("Problem creating: %s", err)

        return data

    def _initialize_data(self) -> dict:
        """Initialize core data structure with default values."""
        data = {
            "mail_updated": datetime.datetime.now(datetime.UTC).isoformat(),
            "amazon_delivered_by_others": 0,
        }
        resources = self.config.get(CONF_RESOURCES, [])
        for sensor in resources:
            if sensor not in data:
                data[sensor] = 0
        return data

    async def _setup_image_config(self, hass: HomeAssistant, config: dict) -> dict:
        """Configure image paths and filenames for all shippers."""
        image_path = default_image_path(hass, config)
        config["image_path"] = image_path

        shipper_images = {
            "amazon_image": (True, False, False, False),
            "ups_image": (False, True, False, False),
            "walmart_image": (False, False, True, False),
            "fedex_image": (False, False, False, True),
            "usps_image": (False, False, False, False),
        }

        for key, params in shipper_images.items():
            config[key] = await hass.async_add_executor_job(
                image_file_name, hass, config, *params
            )
        return config

    async def _get_imap_connection(self, config: dict) -> IMAP4_SSL:
        """Establish and return an authenticated IMAP connection."""
        try:
            account = await login(
                self.hass,
                config.get(CONF_HOST),
                config.get(CONF_PORT),
                config.get(CONF_USERNAME),
                config.get(CONF_PASSWORD),
                config.get(CONF_IMAP_SECURITY),
                config.get(CONF_VERIFY_SSL),
                config.get("oauth_token"),
            )
        except InvalidAuth as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            _LOGGER.error("Error logging into IMAP: %s", err)
            raise UpdateFailed(f"Login failed: {err}") from err

        if not await selectfolder(account, config.get(CONF_FOLDER)):
            _LOGGER.error("Error selecting folder: %s", config.get(CONF_FOLDER))
            await account.logout()
            raise UpdateFailed(f"Folder selection failed: {config.get(CONF_FOLDER)}")

        return account

    async def _update_shippers(
        self, account: IMAP4_SSL, config: dict, today: str, cache: EmailCache
    ) -> dict:
        """Group and process sensors by shipper."""
        data = {}
        resources = config.get(CONF_RESOURCES, [])
        sensors_by_shipper = {}

        for sensor in resources:
            shipper = get_shipper_for_sensor(self.hass, config, sensor)
            if shipper:
                sensors_by_shipper.setdefault(shipper.name, []).append(
                    (shipper, sensor)
                )

        for shipper_name, shipper_group in sensors_by_shipper.items():
            shipper_instance = shipper_group[0][0]
            sensors = [s[1] for s in shipper_group]

            try:
                results = await shipper_instance.process_batch(
                    account, today, sensors, cache
                )
                if isinstance(results, dict):
                    data.update(results)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Error processing shipper %s: %s", shipper_name, err)

        return data

    def _aggregate_package_counts(self, data: dict) -> None:
        """Aggregate global transit and delivered counts from all shippers."""
        # Only update if sensors were requested in initialize_data
        if "zpackages_transit" in data:
            data["zpackages_transit"] = self._sum_transit_counts(data)
        if "zpackages_delivered" in data:
            data["zpackages_delivered"] = self._sum_delivered_counts(data)

    def _sum_delivered_counts(self, data: dict) -> int:
        """Sum delivered packages from all shippers."""
        delivered = 0
        exclude_keys = ("zpackages_delivered", "amazon_delivered_by_others")

        for key, value in data.items():
            if (
                isinstance(value, int)
                and value > 0
                and key.endswith("_delivered")
                and key not in exclude_keys
            ):
                delivered += value
        return delivered

    def _sum_transit_counts(self, data: dict) -> int:
        """Sum transit and exception packages from all shippers."""
        transit = 0
        shippers_counted = set()

        # Amazon is special as it uses amazon_packages for total arriving
        if data.get("amazon_packages", 0) > 0:
            transit += data["amazon_packages"]
            shippers_counted.add("amazon")

        for key, value in data.items():
            if not isinstance(value, int) or value <= 0:
                continue

            # Add exceptions for all shippers
            if key.endswith("_exception") and key != "zpackages_exception":
                transit += value
                continue

            # Match shipper prefix
            shipper = next((s for s in const.SHIPPERS if key.startswith(s)), None)
            if not shipper or shipper in shippers_counted:
                continue

            # Priority: _delivering (preferred generic state) or _packages
            if key.endswith(("_delivering", "_packages")):
                transit += value
                shippers_counted.add(shipper)

        return transit

    async def _binary_sensor_update(self):
        """Update binary sensor states."""
        # USPS uses ATTR_USPS_IMAGE instead of the old ATTR_IMAGE_NAME
        _LOGGER.debug("Data: %s", self._data)
        attributes = (ATTR_USPS_IMAGE, ATTR_IMAGE_PATH)
        if set(attributes).issubset(self._data.keys()):
            image = self._data[ATTR_USPS_IMAGE]
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
                const,
                f"CONF_{base_name.upper()}_CUSTOM_IMG",
                None,
            )
            custom_img_file_key = getattr(
                const,
                f"CONF_{base_name.upper()}_CUSTOM_IMG_FILE",
                None,
            )
            update_key = f"{base_name}_update"

            attributes = (image_attr, ATTR_IMAGE_PATH)
            _LOGGER.debug("%s attributes check: %s", base_name.title(), attributes)
            if set(attributes).issubset(self._data.keys()):
                image = self._data[image_attr]
                _LOGGER.debug(
                    "%s image from coordinator data: %s",
                    base_name.title(),
                    image,
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
                    "Full %s image path: %s",
                    base_name.title(),
                    delivery_image,
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
