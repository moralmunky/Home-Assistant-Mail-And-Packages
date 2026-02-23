"""Mail and Packages Integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_RESOURCES, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_17TRACK_FORWARDED,
    ATTR_AMAZON_COOKIE_TRACKING,
    ATTR_COUNT,
    ATTR_LLM_ANALYZED,
    ATTR_TRACKING,
    ATTR_UNIVERSAL_TRACKING,
    CONF_17TRACK_ENABLED,
    CONF_17TRACK_ENTRY_ID,
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_COOKIES,
    CONF_AMAZON_COOKIES_ENABLED,
    CONF_AMAZON_COOKIE_DOMAIN,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_MP4,
    CONF_IMAGE_SECURITY,
    CONF_IMAP_TIMEOUT,
    CONF_LLM_API_KEY,
    CONF_LLM_ENABLED,
    CONF_LLM_ENDPOINT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_PATH,
    CONF_SCAN_ALL_EMAILS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_FORWARD_ENABLED,
    CONF_TRACKING_SERVICE,
    CONF_TRACKING_SERVICE_ENTRY_ID,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FOLDER,
    DEFAULT_GIF_DURATION,
    DEFAULT_IMAP_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    VERSION,
)
from .helpers import (
    IMAPAuthError,
    default_image_path,
    forward_to_tracking_service,
    llm_scan_emails,
    process_emails,
    scrape_amazon_tracking,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MailAndPackagesData:
    """Runtime data for the Mail and Packages integration."""

    coordinator: MailDataUpdateCoordinator
    cameras: list = field(default_factory=list)


async def async_setup(
    hass: HomeAssistant, config_entry: ConfigEntry
):  # pylint: disable=unused-argument
    """Disallow configuration via YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    _LOGGER.info(
        "Version %s is starting, if you have any issues please report" " them here: %s",
        VERSION,
        ISSUE_URL,
    )
    updated_config = config_entry.data.copy()

    # --- Backfill ALL expected config keys with safe defaults ---
    # This ensures old configs (from any version) get new fields without
    # losing existing values. Uses setdefault() so existing values are
    # NEVER overwritten.

    # Core settings
    updated_config.setdefault(CONF_FOLDER, DEFAULT_FOLDER)
    updated_config.setdefault(CONF_AMAZON_FWDS, [])
    updated_config.setdefault(CONF_IMAP_TIMEOUT, DEFAULT_IMAP_TIMEOUT)
    updated_config.setdefault(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    updated_config.setdefault(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)
    updated_config.setdefault(CONF_ALLOW_EXTERNAL, False)
    updated_config.setdefault(CONF_IMAGE_SECURITY, True)
    updated_config.setdefault(CONF_DURATION, DEFAULT_GIF_DURATION)
    updated_config.setdefault(CONF_GENERATE_MP4, False)
    updated_config.setdefault(CONF_CUSTOM_IMG, False)
    updated_config.setdefault(CONF_CUSTOM_IMG_FILE, DEFAULT_CUSTOM_IMG_FILE)

    # Image path is always computed
    updated_config[CONF_PATH] = default_image_path(hass, config_entry)

    # Advanced tracking defaults (all disabled by default, never overwrites)
    updated_config.setdefault(CONF_SCAN_ALL_EMAILS, False)
    # Backward compat: check legacy 17track keys first
    if CONF_TRACKING_FORWARD_ENABLED not in updated_config:
        updated_config[CONF_TRACKING_FORWARD_ENABLED] = updated_config.get(
            CONF_17TRACK_ENABLED, False
        )
    updated_config.setdefault(CONF_TRACKING_SERVICE, "seventeentrack")
    if CONF_TRACKING_SERVICE_ENTRY_ID not in updated_config:
        updated_config[CONF_TRACKING_SERVICE_ENTRY_ID] = updated_config.get(
            CONF_17TRACK_ENTRY_ID, ""
        )
    updated_config.setdefault(CONF_LLM_ENABLED, False)
    updated_config.setdefault(CONF_LLM_PROVIDER, "ollama")
    updated_config.setdefault(CONF_LLM_ENDPOINT, "http://localhost:11434")
    updated_config.setdefault(CONF_LLM_API_KEY, "")
    updated_config.setdefault(CONF_LLM_MODEL, "")
    updated_config.setdefault(CONF_AMAZON_COOKIES_ENABLED, False)
    updated_config.setdefault(CONF_AMAZON_COOKIES, "")
    updated_config.setdefault(CONF_AMAZON_COOKIE_DOMAIN, "amazon.com")

    # Sort the resources
    updated_config[CONF_RESOURCES] = sorted(updated_config[CONF_RESOURCES])

    # Make sure amazon forwarding emails are not a string
    if isinstance(updated_config[CONF_AMAZON_FWDS], str):
        tmp = updated_config[CONF_AMAZON_FWDS]
        tmp_list = []
        if "," in tmp:
            tmp_list = tmp.split(",")
        else:
            tmp_list.append(tmp)
        updated_config[CONF_AMAZON_FWDS] = tmp_list

    if updated_config != config_entry.data:
        hass.config_entries.async_update_entry(config_entry, data=updated_config)

    config_entry.async_on_unload(
        config_entry.add_update_listener(update_listener)
    )

    # Use a copy for options to avoid shared reference
    hass.config_entries.async_update_entry(
        config_entry, options=dict(config_entry.data)
    )
    config = config_entry.data

    # Variables for data coordinator
    host = config.get(CONF_HOST)
    the_timeout = config.get(CONF_IMAP_TIMEOUT)
    interval = config.get(CONF_SCAN_INTERVAL)

    # Setup the data coordinator
    coordinator = MailDataUpdateCoordinator(
        hass, host, the_timeout, interval, config, config_entry
    )

    # Fetch initial data so we have data when entities subscribe
    # Raises ConfigEntryNotReady automatically if first refresh fails
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = MailAndPackagesData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    _LOGGER.debug("Attempting to unload sensors from the %s integration", DOMAIN)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed sensors from the %s integration", DOMAIN)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""
    _LOGGER.debug("Attempting to reload sensors from the %s integration", DOMAIN)

    # Options flow stores new settings in options; sync them to data
    if dict(config_entry.data) == dict(config_entry.options):
        _LOGGER.debug("No changes detected not reloading sensors.")
        return

    new_data = dict(config_entry.options)

    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=new_data,
    )

    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry):
    """Migrate an old config entry.

    Uses config_entry.version (not a local variable) so cascading
    migrations execute in a single pass (e.g. 1 -> 4 -> 6).
    """
    _LOGGER.info(
        "Migrating config entry from version %s to %s",
        config_entry.version,
        6,
    )

    # 1 -> 4: Migrate format
    if config_entry.version == 1:
        _LOGGER.debug("Migrating from version 1")
        updated_config = config_entry.data.copy()

        if CONF_AMAZON_FWDS in updated_config.keys():
            if not isinstance(updated_config[CONF_AMAZON_FWDS], list):
                updated_config[CONF_AMAZON_FWDS] = [
                    x.strip() for x in updated_config[CONF_AMAZON_FWDS].split(",")
                ]
            else:
                updated_config[CONF_AMAZON_FWDS] = []
        else:
            _LOGGER.warning("Missing configuration data: %s", CONF_AMAZON_FWDS)
            updated_config[CONF_AMAZON_FWDS] = []

        # Force path change
        updated_config[CONF_PATH] = "images/mail_and_packages/"

        # Always on image security
        if not updated_config.get(CONF_IMAGE_SECURITY, False):
            updated_config[CONF_IMAGE_SECURITY] = True

        # Add default Amazon Days configuration
        updated_config.setdefault(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)

        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=4
        )
        _LOGGER.debug("Migration to version 4 complete")

    # 2 -> 4
    if config_entry.version == 2:
        _LOGGER.debug("Migrating from version 2")
        updated_config = config_entry.data.copy()

        # Force path change
        updated_config[CONF_PATH] = "images/mail_and_packages/"

        # Always on image security
        if not updated_config.get(CONF_IMAGE_SECURITY, False):
            updated_config[CONF_IMAGE_SECURITY] = True

        # Add default Amazon Days configuration
        updated_config.setdefault(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)

        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=4
        )
        _LOGGER.debug("Migration to version 4 complete")

    if config_entry.version == 3:
        _LOGGER.debug("Migrating from version 3")
        updated_config = config_entry.data.copy()

        # Add default Amazon Days configuration
        updated_config.setdefault(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)

        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=4
        )
        _LOGGER.debug("Migration to version 4 complete")

    if config_entry.version == 4:
        _LOGGER.debug("Migrating from version 4")
        updated_config = config_entry.data.copy()

        # Add advanced tracking defaults (all disabled by default)
        updated_config.setdefault(CONF_SCAN_ALL_EMAILS, False)
        updated_config.setdefault(CONF_TRACKING_FORWARD_ENABLED, False)
        updated_config.setdefault(CONF_TRACKING_SERVICE, "seventeentrack")
        updated_config.setdefault(CONF_TRACKING_SERVICE_ENTRY_ID, "")
        updated_config.setdefault(CONF_LLM_ENABLED, False)
        updated_config.setdefault(CONF_LLM_PROVIDER, "ollama")
        updated_config.setdefault(CONF_LLM_ENDPOINT, "http://localhost:11434")
        updated_config.setdefault(CONF_LLM_API_KEY, "")
        updated_config.setdefault(CONF_LLM_MODEL, "")
        updated_config.setdefault(CONF_AMAZON_COOKIES_ENABLED, False)
        updated_config.setdefault(CONF_AMAZON_COOKIES, "")
        updated_config.setdefault(CONF_AMAZON_COOKIE_DOMAIN, "amazon.com")

        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=6
        )
        _LOGGER.debug("Migration to version 6 complete")

    if config_entry.version == 5:
        _LOGGER.debug("Migrating from version 5")
        updated_config = config_entry.data.copy()

        # Migrate 17track-specific config to generic tracking service config
        old_enabled = updated_config.pop(CONF_17TRACK_ENABLED, False)
        old_entry_id = updated_config.pop(CONF_17TRACK_ENTRY_ID, "")
        updated_config.setdefault(CONF_TRACKING_FORWARD_ENABLED, old_enabled)
        updated_config.setdefault(CONF_TRACKING_SERVICE, "seventeentrack")
        updated_config.setdefault(CONF_TRACKING_SERVICE_ENTRY_ID, old_entry_id)

        hass.config_entries.async_update_entry(
            config_entry, data=updated_config, version=6
        )
        _LOGGER.debug("Migration to version 6 complete")

    _LOGGER.info("Migration complete, now at version %s", config_entry.version)
    return True


class MailDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching mail data."""

    def __init__(self, hass, host, the_timeout, interval, config, config_entry=None):
        """Initialize."""
        self.interval = timedelta(minutes=interval)
        self.name = f"Mail and Packages ({host})"
        self.timeout = the_timeout
        self.config = config
        self._tracking_forwarded: set = set()

        _LOGGER.debug("Data will be updated every %s", self.interval)

        # Pass config_entry to DataUpdateCoordinator (required in HA 2025.11+,
        # supported since HA 2024.4). Use try/except for backward compat.
        try:
            super().__init__(
                hass,
                _LOGGER,
                name=self.name,
                update_interval=self.interval,
                config_entry=config_entry,
            )
        except TypeError:
            super().__init__(
                hass,
                _LOGGER,
                name=self.name,
                update_interval=self.interval,
            )

    async def _async_update_data(self):
        """Fetch data."""
        import asyncio

        try:
            async with asyncio.timeout(self.timeout):
                try:
                    data = await self.hass.async_add_executor_job(
                        process_emails, self.hass, self.config
                    )
                except IMAPAuthError as error:
                    raise ConfigEntryAuthFailed(
                        f"IMAP authentication failed: {error}"
                    ) from error
                except Exception as error:
                    _LOGGER.error(
                        "Problem updating sensors: %s: %s",
                        type(error).__name__,
                        error,
                        exc_info=True,
                    )
                    raise UpdateFailed(error) from error
        except asyncio.TimeoutError as error:
            raise UpdateFailed(
                f"Timeout communicating with IMAP server after {self.timeout}s"
            ) from error

        # Run async advanced tracking features outside the main timeout
        # These are opt-in and may take additional time
        try:
            await self._process_advanced_tracking(data)
        except Exception as error:
            _LOGGER.warning("Error in advanced tracking: %s", error)

        return data

    async def _process_advanced_tracking(self, data: dict) -> None:
        """Handle async advanced tracking operations.

        Processes 17track forwarding, LLM analysis, and Amazon cookie
        scraping. All features are opt-in and disabled by default.
        """
        config = self.config

        # Tracking service forwarding (17track, AfterShip, AliExpress, etc.)
        forward_enabled = config.get(
            CONF_TRACKING_FORWARD_ENABLED,
            config.get(CONF_17TRACK_ENABLED, False),
        )
        if forward_enabled:
            service_key = data.get(
                "_tracking_service_key",
                config.get(CONF_TRACKING_SERVICE, "seventeentrack"),
            )
            entry_id = data.get(
                "_tracking_entry_id",
                config.get(CONF_TRACKING_SERVICE_ENTRY_ID, ""),
            )
            all_to_forward = data.get(ATTR_17TRACK_FORWARDED, [])
            carrier_map = data.get("_tracking_carrier_map", {})
            already_forwarded = data.get("_tracking_already_forwarded", set())

            if all_to_forward:
                newly_forwarded = await forward_to_tracking_service(
                    self.hass,
                    service_key,
                    entry_id,
                    all_to_forward,
                    carrier_map,
                    already_forwarded,
                )
                # Update the persistent forwarded set on coordinator
                self._tracking_forwarded.update(newly_forwarded)
                data["tracking_service_forwarded"] = len(newly_forwarded)

        # LLM email analysis (opt-in, privacy-sensitive)
        if config.get(CONF_LLM_ENABLED, False):
            llm_config = data.get("_llm_config", {})
            if llm_config:
                _LOGGER.info(
                    "LLM email analysis enabled (provider: %s). "
                    "Email content will be sent to: %s",
                    llm_config.get("provider"),
                    "local Ollama"
                    if llm_config.get("provider") == "ollama"
                    else llm_config.get("provider") + " cloud API",
                )
                from .helpers import login, selectfolder

                account = await self.hass.async_add_executor_job(
                    login,
                    config.get(CONF_HOST),
                    config.get(CONF_PORT),
                    config.get(CONF_USERNAME),
                    config.get(CONF_PASSWORD),
                )
                if account:
                    try:
                        folder = config.get(CONF_FOLDER, '"INBOX"')
                        if await self.hass.async_add_executor_job(
                            selectfolder, account, folder
                        ):
                            llm_result = await llm_scan_emails(
                                account,
                                llm_config.get("known_tracking", []),
                                llm_config["provider"],
                                llm_config["endpoint"],
                                llm_config["api_key"],
                                llm_config["model"],
                            )
                            data[ATTR_LLM_ANALYZED] = llm_result[ATTR_TRACKING]

                            # Merge LLM findings into universal tracking
                            existing = data.get(ATTR_UNIVERSAL_TRACKING, [])
                            for num in llm_result[ATTR_TRACKING]:
                                if num not in existing:
                                    existing.append(num)
                            data[ATTR_UNIVERSAL_TRACKING] = existing
                            data["email_tracking_numbers"] = len(existing)
                    finally:
                        await self.hass.async_add_executor_job(
                            account.logout
                        )

        # Amazon cookie scraping (opt-in)
        if config.get(CONF_AMAZON_COOKIES_ENABLED, False):
            cookie_config = data.get("_amazon_cookie_config", {})
            if cookie_config and cookie_config.get("cookies"):
                amazon_result = await scrape_amazon_tracking(
                    cookie_config["cookies"],
                    cookie_config["domain"],
                )
                data["amazon_cookie_packages"] = amazon_result[ATTR_COUNT]
                data[ATTR_AMAZON_COOKIE_TRACKING] = amazon_result[ATTR_TRACKING]

                # Also forward Amazon tracking to chosen service if enabled
                if forward_enabled:
                    service_key = config.get(
                        CONF_TRACKING_SERVICE, "seventeentrack"
                    )
                    entry_id = config.get(CONF_TRACKING_SERVICE_ENTRY_ID, "")
                    if amazon_result[ATTR_TRACKING]:
                        carrier_map = {
                            t["number"]: t.get("carrier", "Amazon")
                            for t in amazon_result.get("orders", [])
                        }
                        await forward_to_tracking_service(
                            self.hass,
                            service_key,
                            entry_id,
                            amazon_result[ATTR_TRACKING],
                            carrier_map,
                            self._tracking_forwarded,
                        )

        # Clean up internal config keys from data before it reaches sensors
        for key in list(data.keys()):
            if key.startswith("_"):
                del data[key]
