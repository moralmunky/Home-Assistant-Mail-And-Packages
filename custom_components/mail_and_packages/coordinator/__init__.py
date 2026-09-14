"""Data coordinator for Mail and Packages."""

import asyncio
import datetime
import logging
import sys
from datetime import timedelta
from time import monotonic

import anyio
from aioimaplib import IMAP4_SSL
from homeassistant.const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import (
    ConfigEntryAuthFailed,
    DataUpdateCoordinator,
    UpdateFailed,
)

from custom_components.mail_and_packages import const
from custom_components.mail_and_packages.const import (
    AUTH_TYPE_PASSWORD,
    CONF_ALLOW_EXTERNAL,
    CONF_AUTH_TYPE,
    CONF_CUSTOM_DAYS,
    CONF_IMAP_TIMEOUT,
    DEFAULT_CUSTOM_DAYS,
    DEFAULT_IMAP_TIMEOUT,
    MAX_TRACKING_AGE_DAYS,
)
from custom_components.mail_and_packages.helpers import copy_images
from custom_components.mail_and_packages.shippers import get_shipper_for_sensor
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.image import (
    default_image_path,
    hash_file,
)
from custom_components.mail_and_packages.utils.imap import (
    InvalidAuth,
    login,
    logout,
    selectfolder,
)

from .connection import get_imap_connection
from .helpers import (
    aggregate_package_counts,
    async_oauth_access_token,
    binary_sensor_update,
    check_camera_update,
    get_file_hash_if_changed,
    initialize_data,
    setup_image_config,
    sum_delivered_counts,
    sum_delivering_counts,
    sum_transit_counts,
    update_shippers,
)
from .models import MailAndPackagesConfigEntry, MailAndPackagesData
from .tracking import (
    MailDeliveredLatchState,
    apply_tracking_state,
    dedupe_marketplace_duplicates,
    latch_mail_delivered,
    remove_marketplace_package,
    update_tracking_for_prefix,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "InvalidAuth",
    "MailAndPackagesConfigEntry",
    "MailAndPackagesData",
    "MailDataUpdateCoordinator",
    "MailDeliveredLatchState",
    "aggregate_package_counts",
    "apply_tracking_state",
    "async_oauth_access_token",
    "binary_sensor_update",
    "check_camera_update",
    "const",
    "copy_images",
    "datetime",
    "dedupe_marketplace_duplicates",
    "default_image_path",
    "get_shipper_for_sensor",
    "hash_file",
    "initialize_data",
    "latch_mail_delivered",
    "login",
    "logout",
    "remove_marketplace_package",
    "selectfolder",
    "setup_image_config",
    "sum_delivered_counts",
    "sum_delivering_counts",
    "sum_transit_counts",
    "update_shippers",
    "update_tracking_for_prefix",
]


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
        self.timeout = config.get(CONF_IMAP_TIMEOUT, DEFAULT_IMAP_TIMEOUT)
        self.config = config
        self.config_entry = config_entry
        self.hass = hass
        self._data = {}
        self._file_mtime_cache = {}
        self._hash_cache = {}
        self._in_transit_tracking: dict[str, dict[str, str]] = {}
        self._mail_delivered_latch_state = MailDeliveredLatchState()
        self.email_cache = EmailCache(hass=hass)

        _LOGGER.debug("Data will be update every %s", self.interval)

        super().__init__(hass, _LOGGER, name=self.name, update_interval=self.interval)

    @property
    def _mail_delivered_latch_date(self) -> str | None:
        """Return latched date for backward compatibility."""
        return self._mail_delivered_latch_state.date

    @_mail_delivered_latch_date.setter
    def _mail_delivered_latch_date(self, value: str | None) -> None:
        """Set latched date for backward compatibility."""
        self._mail_delivered_latch_state = MailDeliveredLatchState(
            date=value, latched=self._mail_delivered_latch_state.latched
        )

    @property
    def _mail_delivered_latched(self) -> bool:
        """Return latched boolean for backward compatibility."""
        return self._mail_delivered_latch_state.latched

    @_mail_delivered_latched.setter
    def _mail_delivered_latched(self, value: bool) -> None:
        """Set latched boolean for backward compatibility."""
        self._mail_delivered_latch_state = MailDeliveredLatchState(
            date=self._mail_delivered_latch_state.date, latched=value
        )

    async def _get_file_hash_if_changed(self, file_path: str) -> str | None:
        """Only hash file if mtime changed."""
        return await get_file_hash_if_changed(
            self.hass,
            self._file_mtime_cache,
            self._hash_cache,
            file_path,
            hash_fn=getattr(sys.modules.get(__name__), "hash_file", hash_file),
        )

    async def async_get_file_hash_if_changed(self, file_path: str) -> str | None:
        """Public method to get file hash if changed."""
        return await self._get_file_hash_if_changed(file_path)

    async def _async_oauth_access_token(self, auth_type: str) -> str:
        """Return a valid OAuth2 access token, refreshing it when required."""
        return await async_oauth_access_token(
            self.hass, self.config_entry, auth_type, flow_mod=config_entry_oauth2_flow
        )

    async def _async_update_data(self):
        """Fetch data."""
        start = monotonic()
        try:
            async with asyncio.timeout(self.timeout):
                try:
                    config = dict(self.config)

                    # Refresh OAuth2 token if using OAuth authentication
                    auth_type = config.get(CONF_AUTH_TYPE, AUTH_TYPE_PASSWORD)
                    if auth_type != AUTH_TYPE_PASSWORD and self.config_entry:
                        oauth_token = await self._async_oauth_access_token(auth_type)
                        config["oauth_token"] = oauth_token
                        self.config["oauth_token"] = oauth_token

                    data = await self.process_emails(self.hass, config)
                except ConfigEntryAuthFailed:
                    raise
                except Exception as error:
                    _LOGGER.error("Problem updating sensors: %s", error)
                    if self._data:
                        return self._data
                    raise UpdateFailed(error) from error

                if data:
                    self._data = data
                    await self._binary_sensor_update(data)
                return self._data
        except TimeoutError:
            _LOGGER.error(
                "Mail and Packages scan exceeded its %.0fs time budget (elapsed %.1fs). "
                "This budget covers the ENTIRE scan (login plus every per-carrier IMAP "
                "search), not just connecting. Increase the scan time limit in the "
                "integration options, or reduce the mailbox size searched (use a "
                "dedicated folder), the days-back window, or the number of enabled "
                "carriers.",
                self.timeout,
                monotonic() - start,
            )
            if self._data:
                return self._data
            raise UpdateFailed("Scan timed out and no prior data available") from None

    async def process_emails(self, hass: HomeAssistant, config: dict) -> dict:
        """Process emails and update sensors."""
        # Initialize defaults and image paths
        data = self._initialize_data()
        config = await self._setup_image_config(hass, config)

        # Connect to IMAP
        account = await self._get_imap_connection(config)
        try:
            days = config.get(CONF_CUSTOM_DAYS, DEFAULT_CUSTOM_DAYS)
            cache = self.email_cache
            cache.set_account(account)
            await cache.async_load()
            await cache.async_purge_expired(custom_days=days)

            now = datetime.datetime.now()
            today = now.strftime("%d-%b-%Y")
            today_iso = now.date().isoformat()
            days = config.get(CONF_CUSTOM_DAYS, DEFAULT_CUSTOM_DAYS)
            since_date = (now - datetime.timedelta(days=days)).strftime("%d-%b-%Y")

            # Process logic
            shipper_data = await self._update_shippers(
                account, config, today, since_date, cache
            )
            tracking_details = shipper_data.pop("_tracking_details", {})
            data.update(shipper_data)
            self._dedupe_marketplace_duplicates(data, tracking_details)
            self._apply_tracking_state(data, tracking_details, today_iso)
            self._latch_mail_delivered(data, today_iso)

            # Aggregate global transit and delivered sensors
            self._aggregate_package_counts(data)
            await cache.async_save()
        finally:
            await logout(account)

        # Post-process external images
        if config.get(CONF_ALLOW_EXTERNAL):
            try:
                await hass.async_add_executor_job(copy_images, hass, config)
            except (OSError, ValueError) as err:
                _LOGGER.error("Problem creating: %s", err)

        return data

    def _initialize_data(self) -> dict:
        """Initialize core data structure with default values."""
        return initialize_data(self.config)

    async def _setup_image_config(self, hass: HomeAssistant, config: dict) -> dict:
        """Configure image paths and filenames for all shippers."""
        return await setup_image_config(hass, config)

    async def _get_imap_connection(self, config: dict) -> IMAP4_SSL:
        """Establish and return an authenticated IMAP connection."""
        return await get_imap_connection(
            self.hass,
            config,
            self.timeout,
            self.config_entry,
            login_fn=login,
            selectfolder_fn=selectfolder,
            logout_fn=logout,
        )

    async def _update_shippers(
        self,
        account: IMAP4_SSL,
        config: dict,
        today: str,
        since_date: str,
        cache: EmailCache,
    ) -> dict:
        """Group and process sensors by shipper."""
        return await update_shippers(
            self.hass,
            account,
            config,
            today,
            since_date,
            cache,
            shipper_fn=get_shipper_for_sensor,
        )

    @staticmethod
    def _dedupe_marketplace_duplicates(
        data: dict,
        tracking_details: dict[str, list],
    ) -> None:
        dedupe_marketplace_duplicates(data, tracking_details)

    @staticmethod
    def _remove_marketplace_package(
        data: dict,
        tracking_details: dict[str, list],
        prefix: str,
        marketplace_id: str,
        carrier_num: str,
    ) -> None:
        remove_marketplace_package(
            data, tracking_details, prefix, marketplace_id, carrier_num
        )

    def _apply_tracking_state(
        self,
        data: dict,
        tracking_details: dict[str, list[str]],
        today_iso: str,
    ) -> None:
        apply_tracking_state(
            self._in_transit_tracking,
            data,
            tracking_details,
            today_iso,
            MAX_TRACKING_AGE_DAYS,
        )

    def _latch_mail_delivered(self, data: dict, today_iso: str) -> None:
        self._mail_delivered_latch_state = latch_mail_delivered(
            self._mail_delivered_latch_state, data, today_iso
        )

    def _update_tracking_for_prefix(
        self,
        prefix: str,
        delivering: list[str],
        delivered: list[str],
        today_iso: str,
        ttl_days: int,
    ) -> None:
        update_tracking_for_prefix(
            self._in_transit_tracking,
            prefix,
            delivering,
            delivered,
            today_iso,
            ttl_days,
        )

    def _aggregate_package_counts(self, data: dict) -> None:
        aggregate_package_counts(data)

    async def async_check_camera_update(
        self, base_name: str, data: dict | None = None
    ) -> None:
        """Check image hash changes for a specific delivery camera."""
        await check_camera_update(
            self,
            base_name,
            data,
            def_img_path=default_image_path,
            anyio_mod=anyio,
        )

    async def _check_camera_update(
        self, base_name: str, data: dict | None = None
    ) -> None:
        """Backward-compatible alias for async_check_camera_update."""
        await self.async_check_camera_update(base_name, data)

    async def async_binary_sensor_update(self, data: dict | None = None) -> None:
        """Update binary sensor states."""
        await binary_sensor_update(
            self,
            data,
            def_img_path=default_image_path,
            anyio_mod=anyio,
        )

    async def _binary_sensor_update(self, data: dict | None = None) -> None:
        """Backward-compatible alias for async_binary_sensor_update."""
        await self.async_binary_sensor_update(data)
