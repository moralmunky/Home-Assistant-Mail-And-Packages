"""Generic Shipper class."""

from __future__ import annotations

import email
import logging
from email.header import decode_header
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_EMAIL,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.shippers.base import Shipper
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.email import find_text, find_text_matches
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_fetch_headers,
    email_search,
)
from custom_components.mail_and_packages.utils.shipper import (
    generic_delivery_image_extraction,
    get_tracking,
)

from .batch import GenericBatchMixin
from .helpers import (
    SearchContext,
    _find_carrier_number,
)
from .helpers import (
    _check_amazon_mentions as helper_check_amazon_mentions,
)
from .helpers import (
    _collect_carrier_tracking as helper_collect_carrier_tracking,
)
from .helpers import (
    _copy_generic_placeholder as helper_copy_generic_placeholder,
)
from .helpers import (
    _decode_subject as helper_decode_subject,
)
from .helpers import (
    _extract_images_for_shipper as helper_extract_images_for_shipper,
)
from .helpers import (
    _extract_subject_from_headers as helper_extract_subject_from_headers,
)
from .helpers import (
    _filter_unique_ids as helper_filter_unique_ids,
)
from .helpers import (
    _process_emails_by_type as helper_process_emails_by_type,
)
from .helpers import (
    _process_tracking_numbers as helper_process_tracking_numbers,
)
from .helpers import (
    _setup_image_extraction as helper_setup_image_extraction,
)
from .helpers import (
    _verify_matched_subjects as helper_verify_matched_subjects,
)
from .search import GenericSearchMixin

_LOGGER = logging.getLogger(__name__)

# Re-exports for test compatibility and patch targets
__all__ = [
    "GenericBatchMixin",
    "GenericSearchMixin",
    "GenericShipper",
    "Path",
    "SearchContext",
    "_find_carrier_number",
    "anyio",
    "copyfile",
    "decode_header",
    "email",
    "email_fetch",
    "email_fetch_headers",
    "email_search",
    "find_text",
    "find_text_matches",
    "generic_delivery_image_extraction",
    "get_tracking",
]


class GenericShipper(GenericBatchMixin, GenericSearchMixin, Shipper):
    """Generic Shipper class for UPS, FedEx, Walmart, etc."""

    @property
    def name(self) -> str:
        """Return the internal name of the shipper."""
        return "generic"

    @classmethod
    def handles_sensor(cls, sensor_type: str) -> bool:
        """Return True if this shipper handles the given sensor type."""
        return sensor_type in SENSOR_DATA

    async def process(
        self,
        account: IMAP4_SSL,
        date: str,
        sensor_type: str,
        cache: EmailCache | None = None,
        since_date: str | None = None,
    ) -> dict[str, Any]:
        """Process emails for this shipper on the given date.

        since_date: if provided, used instead of date for _delivering and
        _exception sensors so that emails from previous days are included.
        """
        _LOGGER.debug("Processing generic sensor: %s", sensor_type)

        if sensor_type not in SENSOR_DATA:
            _LOGGER.error("Sensor %s not found in SENSOR_DATA", sensor_type)
            return {ATTR_COUNT: 0}

        config = SENSOR_DATA[sensor_type]
        email_addresses = config.get(ATTR_EMAIL, [])
        subjects = config.get(ATTR_SUBJECT, [])

        if sensor_type.endswith("_packages") and not email_addresses and not subjects:
            _LOGGER.debug(
                "Skipping email search for %s: no email addresses configured",
                sensor_type,
            )
            return {ATTR_COUNT: 0, ATTR_TRACKING: []}

        forwarding_header, email_addresses = self._resolve_forwarding(email_addresses)
        is_delivered = sensor_type.endswith("_delivered")
        search_date = self._determine_search_date(sensor_type, date, since_date)
        result: dict[str, Any] = {ATTR_COUNT: 0, ATTR_TRACKING: []}

        if not email_addresses:
            _LOGGER.debug(
                "Skipping email search for %s: no email addresses configured",
                sensor_type,
            )
            return result

        image_path = self.config.get("image_path")
        shipper_cfg = await self._setup_image_extraction(sensor_type, image_path)
        search_ctx = SearchContext(
            sensor_type=sensor_type,
            config=config,
            shipper_cfg=shipper_cfg,
            result=result,
            cache=cache,
            forwarding_header=forwarding_header,
        )

        count, found_data, image_found = await self._search_for_emails(
            account,
            email_addresses,
            search_date,
            subjects,
            search_ctx,
        )

        result[ATTR_TRACKING] = await self._process_tracking_numbers(
            sensor_type,
            found_data,
            account,
            cache,
        )
        if result[ATTR_TRACKING]:
            count = len(result[ATTR_TRACKING])

        result.update(
            await self._collect_carrier_tracking(
                sensor_type, found_data, account, cache
            )
        )

        if is_delivered:
            result["pre_filtered_tracking"] = result.get(ATTR_TRACKING, [])
            if since_date and search_date != date:
                count = await self._process_delivered_today(
                    account, email_addresses, date, subjects, search_ctx, result
                )

        result[ATTR_COUNT] = count
        await self._finalize_shipper_image(shipper_cfg, image_path, image_found, result)
        return result

    async def _copy_generic_placeholder(self, shipper_cfg: dict[str, Any]) -> None:
        """Copy the generic placeholder for the shipper."""
        await helper_copy_generic_placeholder(self.hass, shipper_cfg)

    async def _setup_image_extraction(
        self,
        sensor_type: str,
        image_path: str,
    ) -> dict | None:
        """Set up image extraction configuration."""
        return await helper_setup_image_extraction(
            self.hass, self.config, sensor_type, image_path
        )

    def _decode_subject(self, header_part: bytes | bytearray) -> str | None:
        """Decode MIME encoded subject from email header part."""
        return helper_decode_subject(header_part)

    def _extract_subject_from_headers(
        self,
        header_data: list[Any],
        sensor_type: str,
        eid: bytes,
        expected_subjects_lower: list[str],
    ) -> bool:
        """Check if any header part matches the expected subjects."""
        return helper_extract_subject_from_headers(
            header_data, sensor_type, eid, expected_subjects_lower
        )

    async def _verify_matched_subjects(
        self,
        account: IMAP4_SSL,
        email_ids: list[bytes],
        sensor_type: str,
        expected_subjects: list[str],
        cache: EmailCache | None = None,
    ) -> list[bytes]:
        """Verify the subject of each matched email locally and log for debugging."""
        return await helper_verify_matched_subjects(
            account, email_ids, sensor_type, expected_subjects, self.name, cache
        )

    def _filter_unique_ids(
        self, email_ids: list[bytes], unique_email_ids: set
    ) -> list[bytes]:
        """Filter out already processed email IDs."""
        return helper_filter_unique_ids(email_ids, unique_email_ids)

    async def _process_tracking_numbers(
        self,
        sensor_type: str,
        found_data: list,
        account: IMAP4_SSL,
        cache: EmailCache | None = None,
    ) -> list:
        """Process tracking numbers for the sensor."""
        return await helper_process_tracking_numbers(
            sensor_type, found_data, account, cache
        )

    async def _collect_carrier_tracking(
        self,
        sensor_type: str,
        found_data: list,
        account: IMAP4_SSL,
        cache: EmailCache | None = None,
    ) -> dict[str, dict]:
        """Map marketplace tracking id -> embedded carrier tracking number."""
        return await helper_collect_carrier_tracking(
            sensor_type, found_data, account, cache
        )

    async def _process_emails_by_type(
        self,
        account: IMAP4_SSL,
        config: dict,
        ids: list,
        current_count: int,
        cache: EmailCache | None = None,
    ) -> tuple[int, list]:
        """Process emails based on body search or just count."""
        return await helper_process_emails_by_type(
            account, config, ids, current_count, cache
        )

    async def _extract_images_for_shipper(
        self,
        account: IMAP4_SSL,
        ids: list,
        s_config: dict,
        cache: EmailCache | None = None,
    ) -> bool:
        """Extract delivery images from emails."""
        return await helper_extract_images_for_shipper(
            self.hass, account, ids, s_config, self.name, cache
        )

    async def _check_amazon_mentions(
        self,
        account: IMAP4_SSL,
        ids: list,
        result: dict,
        cache: EmailCache | None = None,
    ) -> None:
        """Check for Amazon mentions in emails."""
        await helper_check_amazon_mentions(account, ids, result, cache)
