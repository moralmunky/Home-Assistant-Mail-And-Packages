"""Mail and Packages Integration."""

import asyncio
import logging
import shutil
from pathlib import Path

import anyio
from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
    ConfigEntryState,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_RESOURCES,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later

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
    SENSOR_TYPES,
    SIGNAL_MAILBOX_UPDATED,
    SUMMARY_PLATFORMS,
    VERSION,
)
from .coordinator import (
    MailAndPackagesConfigEntry,
    MailAndPackagesData,
    MailDataUpdateCoordinator,
)
from .migrate import async_migrate_entry
from .summary import (
    SummaryData,
    is_summary_entry,
    mailbox_entries,
    summary_entry,
    summary_keys,
)
from .utils.image import default_image_path, hash_file
from .views import MailAndPackagesImageView

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
    if is_summary_entry(config_entry):
        return await _async_setup_summary(hass, config_entry)

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

    # Ensure storage directory exists
    storage_path_str = default_image_path(hass, config_entry)
    storage_dir = Path(hass.config.path(storage_path_str))
    await hass.async_add_executor_job(
        lambda: storage_dir.mkdir(parents=True, exist_ok=True)
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

    # Register HTTP view for serving images if not already registered
    if not hass.data.setdefault(DOMAIN, {}).get("view_registered") and getattr(
        hass, "http", None
    ):
        hass.http.register_view(MailAndPackagesImageView(hass))
        hass.data[DOMAIN]["view_registered"] = True

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    # Let the combined summary recalculate whenever this mailbox refreshes.
    @callback
    def _notify_summary() -> None:
        async_dispatcher_send(hass, SIGNAL_MAILBOX_UPDATED)

    config_entry.async_on_unload(coordinator.async_add_listener(_notify_summary))
    _async_mailboxes_changed(hass)

    return True


async def _async_setup_summary(
    hass: HomeAssistant, config_entry: MailAndPackagesConfigEntry
) -> bool:
    """Set up the combined "All mailboxes" summary entry."""
    config_entry.runtime_data = SummaryData(keys=summary_keys(hass, SENSOR_TYPES))
    await hass.config_entries.async_forward_entry_setups(
        config_entry, SUMMARY_PLATFORMS
    )
    return True


@callback
def _async_mailboxes_changed(hass: HomeAssistant) -> None:
    """Offer or refresh the summary after mailboxes are added or removed."""
    summary = summary_entry(hass)
    if summary is None:
        if len(mailbox_entries(hass)) >= 2:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data={},
                )
            )
        return

    if summary.state is not ConfigEntryState.LOADED:
        return
    if summary.runtime_data.keys != summary_keys(hass, SENSOR_TYPES):
        # A mailbox tracks sensors the summary does not have yet (or no longer).
        hass.config_entries.async_schedule_reload(summary.entry_id)
    else:
        async_dispatcher_send(hass, SIGNAL_MAILBOX_UPDATED)


async def update_listener(
    hass: HomeAssistant, config_entry: MailAndPackagesConfigEntry
) -> None:
    """Update listener."""
    if is_summary_entry(config_entry):
        return
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
    if is_summary_entry(config_entry):
        return True
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

    summary = is_summary_entry(config_entry)
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in (SUMMARY_PLATFORMS if summary else PLATFORMS)
            ],
        ),
    )

    if unload_ok:
        _LOGGER.debug("Successfully removed sensors from the %s integration", DOMAIN)
        if not summary:
            # Recalculate once this entry is no longer loaded.
            async_call_later(
                hass, 1, callback(lambda _now: _async_mailboxes_changed(hass))
            )

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant,
    config_entry: MailAndPackagesConfigEntry,
) -> None:
    """Handle removal of an entry and clean up its storage directory."""
    if is_summary_entry(config_entry):
        return

    storage_path_str = default_image_path(hass, config_entry)
    storage_dir = Path(hass.config.path(storage_path_str))
    if await anyio.Path(storage_dir).exists():
        _LOGGER.debug(
            "Removing image directory for entry %s: %s",
            config_entry.entry_id,
            storage_dir,
        )
        await hass.async_add_executor_job(
            lambda: shutil.rmtree(storage_dir, ignore_errors=True)
        )
