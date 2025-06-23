"""DataUpdateCoordinator for Mail and Packages V2."""
import asyncio
import logging
from datetime import timedelta, datetime as dt # Added dt for mail_updated
from typing import Any, Dict, List, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_RESOURCES,
)

# V2 specific imports
from .const import (
    CONF_FOLDER,
    CONF_IMAP_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_AMAZON_DAYS, # Added
    CONF_AMAZON_FWDS, # Added
    DOMAIN,
    SENSOR_DATA, # Crucial for knowing what to search for each sensor type
    AMAZON_DOMAINS, # For specific Amazon searches
    AMAZON_SHIPMENT_TRACKING, # For specific Amazon searches
    AMAZON_EMAIL, # For Amazon delivered search
    AMAZON_DELIVERED_SUBJECT, # For Amazon delivered search
    AMAZON_PACKAGES, # Sensor key
    AMAZON_ORDER, # Attribute key
    # ... other constants needed ...
)
from .imap_client import (
    connect_to_server,
    select_mailbox_folder,
    search_emails,
    fetch_email_rfc822,
    logout_server,
    build_search_criteria,
)
from .email_parser import identify_and_parse_email
from .utils import get_formatted_date_for_imap, LOG_PREFIX # Utility for IMAP date format & logging
from .exceptions import UpdateFailed # Custom exception

_LOGGER = logging.getLogger(__name__)

class MailDataUpdateCoordinatorV2(DataUpdateCoordinator[Dict[str, Any]]):
    """Manages fetching and processing email data for Mail and Packages V2."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the data update coordinator."""
        self.config_entry = config_entry
        self.hass = hass

        # Extract and store configuration data
        cfg = config_entry.data
        self.server_details = {
            "host": cfg[CONF_HOST],
            "port": cfg[CONF_PORT],
            "username": cfg[CONF_USERNAME],
            "password": cfg[CONF_PASSWORD],
            "folder": cfg[CONF_FOLDER],
            "imap_timeout": cfg.get(CONF_IMAP_TIMEOUT, 30),
        }
        self.resources_to_monitor = cfg.get(CONF_RESOURCES, [])
        self.amazon_search_days = cfg.get(CONF_AMAZON_DAYS, 3)
        self.amazon_forwarding_emails = cfg.get(CONF_AMAZON_FWDS, [])

        update_interval_minutes = cfg.get(CONF_SCAN_INTERVAL, 5)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{LOG_PREFIX} ({self.server_details['host']})", # Using LOG_PREFIX from utils
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        _LOGGER.info(
            "%s Coordinator initialized. Update interval: %s min. IMAP Timeout: %s s. Resources: %s. Amazon Days: %s, Amazon Fwds: %s",
            self.name, update_interval_minutes, self.server_details["imap_timeout"],
            self.resources_to_monitor, self.amazon_search_days, self.amazon_forwarding_emails
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch and process email data using Home Assistant's executor for synchronous IMAP calls."""
        _LOGGER.debug("%s Starting email data update", self.name)

        processed_data: Dict[str, Any] = {resource: 0 for resource in self.resources_to_monitor}
        # Initialize specific known structured data
        if AMAZON_ORDER in self.resources_to_monitor or AMAZON_PACKAGES in self.resources_to_monitor :
             processed_data[AMAZON_ORDER] = [] # Stores list of Amazon order numbers
        # Add other specific initializations as parsers are developed (e.g., for tracking numbers)

        account = None
        try:
            account = await self.hass.async_add_executor_job(
                connect_to_server,
                self.server_details["host"], self.server_details["port"],
                self.server_details["username"], self.server_details["password"],
                self.server_details["imap_timeout"],
            )
            if not account:
                raise UpdateFailed(f"Failed to connect/login to IMAP: {self.server_details['host']}")

            if not await self.hass.async_add_executor_job(
                select_mailbox_folder, account, self.server_details["folder"]
            ):
                raise UpdateFailed(f"Failed to select folder: {self.server_details['folder']}")

            # --- Main Email Processing Logic ---
            # This is where the core logic from original helpers.py (process_emails, fetch) will be refactored.
            # The goal is to iterate through SENSOR_DATA, build search queries, fetch emails,
            # and pass them to the appropriate parser from email_parser.py.

            # Date for IMAP search (e.g., "SINCE 01-Jan-2023")
            # For Amazon, it will use `self.amazon_search_days`. Other providers might use a fixed 1-day window.
            search_date_general = get_formatted_date_for_imap(days_ago=1) # General daily digest type emails
            search_date_amazon = get_formatted_date_for_imap(days_ago=self.amazon_search_days)

            # Accumulators for Amazon data from multiple emails/domains
            all_amazon_orders_found = set(processed_data.get(AMAZON_ORDER, [])) # Use set for unique orders
            total_amazon_deliveries_today = 0

            # Iterate through monitored resources to fetch and parse relevant emails
            for sensor_key in self.resources_to_monitor:
                sensor_config = SENSOR_DATA.get(sensor_key)
                if not sensor_config and sensor_key not in [AMAZON_PACKAGES, AMAZON_ORDER, "mail_updated"]: # Skip pseudo-sensors
                    _LOGGER.warning("%s No SENSOR_DATA config found for resource: %s", self.name, sensor_key)
                    continue

                # --- AMAZON Specific Logic (Example of refactoring get_items) ---
                if sensor_key == AMAZON_PACKAGES: # This sensor drives fetching for AMAZON_ORDER too
                    _LOGGER.debug("%s Processing resource: %s", self.name, sensor_key)

                    # Construct list of sender addresses for Amazon
                    amazon_sender_addresses = []
                    for domain in AMAZON_DOMAINS:
                        for prefix in AMAZON_SHIPMENT_TRACKING: # shipment-tracking@, conferma-spedizione@
                            amazon_sender_addresses.append(f"{prefix}@{domain}")
                    if self.amazon_forwarding_emails:
                         amazon_sender_addresses.extend([fwd for fwd in self.amazon_forwarding_emails if fwd and "@" in fwd])

                    if not amazon_sender_addresses:
                        _LOGGER.warning("%s No Amazon sender addresses to search (check domains/fwds).", self.name)
                        continue

                    use_literal, criteria_str = build_search_criteria(
                        addresses=amazon_sender_addresses, date_since=search_date_amazon
                    )

                    email_uids = await self.hass.async_add_executor_job(
                        search_emails, account, (use_literal, criteria_str)
                    )

                    if email_uids:
                        _LOGGER.info("%s Found %d potential Amazon emails (Shipped/Order updates).", self.name, len(email_uids))
                        for uid in email_uids:
                            email_bytes = await self.hass.async_add_executor_job(fetch_email_rfc822, account, uid)
                            if email_bytes:
                                parsed = identify_and_parse_email(email_bytes) # Parser identifies it's Amazon
                                if parsed and parsed.get("provider") == "amazon":
                                    total_amazon_deliveries_today += parsed.get("deliveries_today", 0)
                                    for order in parsed.get("orders", []):
                                        all_amazon_orders_found.add(order)
                                    # TODO: Accumulate tracking numbers if parser provides them

                    processed_data[AMAZON_PACKAGES] = total_amazon_deliveries_today
                    processed_data[AMAZON_ORDER] = sorted(list(all_amazon_orders_found))
                    continue # Move to next resource after handling Amazon packages

                # --- Other Generic Sensor Processing (using SENSOR_DATA) ---
                # This part needs to be built out, similar to original get_count
                if sensor_config: # For non-Amazon sensors defined in SENSOR_DATA
                    _LOGGER.debug("%s Processing resource: %s using SENSOR_DATA", self.name, sensor_key)
                    email_addrs = sensor_config.get("email", [])
                    subjects_to_search = sensor_config.get("subject", [None]) # Search with no subject if None

                    # Most non-Amazon are daily, so use general search date
                    # This needs refinement based on per-sensor day lookback if necessary
                    current_search_date = search_date_general

                    count_for_sensor = 0
                    all_tracking_numbers_for_sensor = set()

                    for subject_keyword in subjects_to_search:
                        use_literal, criteria_str = build_search_criteria(
                            addresses=email_addrs, date_since=current_search_date, subject=subject_keyword
                        )
                        email_uids = await self.hass.async_add_executor_job(
                            search_emails, account, (use_literal, criteria_str),
                            subject_literal_value=subject_keyword if use_literal else None
                        )
                        if email_uids:
                            _LOGGER.info("%s Found %d emails for %s (subject: %s)", self.name, len(email_uids), sensor_key, subject_keyword)
                            for uid in email_uids:
                                email_bytes = await self.hass.async_add_executor_job(fetch_email_rfc822, account, uid)
                                if email_bytes:
                                    parsed = identify_and_parse_email(email_bytes)
                                    if parsed: # If parser returns data
                                        # Logic to increment count_for_sensor based on parsed data
                                        # This is simplified. Original get_count had more complex logic.
                                        # For now, assume 1 email = 1 item for the sensor if relevant.
                                        # This needs to align with what each parser returns.
                                        # Example: if parser returns a specific status for this sensor_key
                                        if parsed.get("status") in ["delivering", "delivered"] or parsed.get("provider") == sensor_key.split("_")[0]:
                                            count_for_sensor += 1

                                        for tn in parsed.get("tracking_numbers", []):
                                            all_tracking_numbers_for_sensor.add(tn)

                    processed_data[sensor_key] = count_for_sensor
                    # Store tracking numbers if the sensor type implies it (e.g., "ups_delivering")
                    if "delivering" in sensor_key or "packages" in sensor_key:
                         tracking_key = sensor_key.replace("_delivering", "_tracking").replace("_packages", "_tracking")
                         processed_data[tracking_key] = sorted(list(all_tracking_numbers_for_sensor))


            processed_data["mail_updated"] = dt.now(tz=self.hass.config.time_zone) # Use HA's timezone aware now

        except UpdateFailed as e:
            _LOGGER.error("%s Update failed: %s", self.name, e)
            raise # Re-raise UpdateFailed to be handled by Home Assistant
        except IMAP_EXCEPTIONS as e: # Catch specific IMAP errors from client
            _LOGGER.error("%s IMAP library error during update: %s", self.name, e, exc_info=True)
            raise UpdateFailed(f"IMAP library error: {e}") from e
        except Exception as e:
            _LOGGER.error("%s Unexpected error during coordinator update: %s", self.name, e, exc_info=True)
            raise UpdateFailed(f"Unexpected error: {e}") from e
        finally:
            if account:
                await self.hass.async_add_executor_job(logout_server, account)

        _LOGGER.debug("%s Email data update complete. Processed data snapshot: %s", self.name, {k: v for k, v in processed_data.items() if k not in ["amazon_order"] or not v}) # Avoid logging huge lists
        return processed_data

# This coordinator is still a work in progress.
# The main loop for processing `self.resources_to_monitor` needs to be
# fully fleshed out to replicate the logic from the original `helpers.py::fetch()`
# and `helpers.py::process_emails()`, deciding which emails to search for
# based on `SENSOR_DATA`, calling the correct parsers, and aggregating counts.
# The example for `amazon_packages` is a start.
# Error handling for individual email processing steps (fetch, parse) should be added.
# Added CONF_AMAZON_DAYS and CONF_AMAZON_FWDS to init.
# Used utils.LOG_PREFIX.
# Using hass.async_add_executor_job for all imaplib calls.
# Added basic structure for iterating other SENSOR_DATA entries.
# Refined Amazon specific logic slightly.
# Ensured `mail_updated` uses HA's timezone.
# Added more specific IMAP exception catching.
# Simplified logging of processed_data to avoid overly large log entries.
# Initialized `amazon_order` if relevant.
# The aggregation logic for `count_for_sensor` in the generic loop is very basic and needs alignment with parser outputs.
# Added handling for `subject_literal_value` in `search_emails` call.
