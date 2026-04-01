"""Generic Shipper class."""

from __future__ import annotations

import email
import logging
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
    AMAZON_DELIVERED,
    ATTR_BODY,
    ATTR_BODY_COUNT,
    ATTR_COUNT,
    ATTR_EMAIL,
    ATTR_PATTERN,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    CAMERA_DATA,
    CAMERA_EXTRACTION_CONFIG,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.utils.amazon import get_decoded_subject
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.email import find_text
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_fetch_headers,
    email_search,
)
from custom_components.mail_and_packages.utils.shipper import (
    generic_delivery_image_extraction,
    get_tracking,
)

from .base import Shipper

_LOGGER = logging.getLogger(__name__)


class GenericShipper(Shipper):
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
    ) -> dict[str, Any]:
        """Process emails for this shipper on the given date."""
        _LOGGER.debug("Processing generic sensor: %s", sensor_type)

        if sensor_type not in SENSOR_DATA:
            _LOGGER.error("Sensor %s not found in SENSOR_DATA", sensor_type)
            return {ATTR_COUNT: 0}

        config = SENSOR_DATA[sensor_type]
        email_addresses = config.get(ATTR_EMAIL, [])
        subjects = config.get(ATTR_SUBJECT, [])

        # Add forwarded emails if configured
        forwarded_emails = self.config.get("forwarded_emails", [])
        if forwarded_emails:
            email_addresses = forwarded_emails + email_addresses

        result = {ATTR_COUNT: 0, ATTR_TRACKING: []}

        image_path = self.config.get("image_path")
        # Setup image extraction
        shipper_cfg = await self._setup_image_extraction(sensor_type, image_path)
        image_found = False

        count, found_data, image_found = await self._search_for_emails(
            account,
            email_addresses,
            date,
            subjects,
            config,
            shipper_cfg,
            sensor_type,
            result,
            cache,
        )

        # Process tracking numbers
        result[ATTR_TRACKING] = await self._process_tracking_numbers(
            sensor_type,
            found_data,
            account,
            cache,
        )
        if result[ATTR_TRACKING]:
            count = len(result[ATTR_TRACKING])

        result[ATTR_COUNT] = count
        if shipper_cfg:
            image_attr = f"{shipper_cfg['name']}_image"
            result[image_attr] = shipper_cfg["image_name"]
            result["image_path"] = image_path

            if count > 0 and not image_found:
                await self._copy_generic_placeholder(shipper_cfg)

        return result

    async def process_batch(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
    ) -> dict[str, Any]:
        """Process multiple generic sensors in batch."""
        res = {}
        for sensor in sensors:
            sensor_res = await self.process(account, date, sensor, cache)
            res.update(sensor_res)
            # Replicate coordinator dictionary logic
            if sensor not in sensor_res:
                if ATTR_COUNT in sensor_res:
                    res[sensor] = sensor_res[ATTR_COUNT]
        return res

    async def _copy_generic_placeholder(self, shipper_cfg: dict[str, Any]) -> None:
        """Copy the generic placeholder for the shipper."""
        shipper_name = shipper_cfg["name"]
        # Try to find courier-specific placeholder
        placeholder = Path(__file__).parent.parent / f"no_deliveries_{shipper_name}.jpg"
        if not await anyio.Path(placeholder).exists():
            placeholder = Path(__file__).parent.parent / "mail_none.gif"

        target = (
            Path(shipper_cfg["image_path"]) / shipper_name / shipper_cfg["image_name"]
        )
        _LOGGER.debug(
            "No %s images found in emails, using placeholder: %s",
            shipper_name,
            placeholder.name,
        )
        try:
            await self.hass.async_add_executor_job(
                copyfile, str(placeholder), str(target)
            )
        except OSError as err:
            _LOGGER.error("Error attempting to copy placeholder: %s", err)

    async def _search_for_emails(
        self,
        account: IMAP4_SSL,
        email_addresses: list[str],
        date: str,
        subjects: list[str],
        config: dict[str, Any],
        shipper_cfg: dict[str, Any] | None,
        sensor_type: str,
        result: dict[str, Any],
        cache: EmailCache | None = None,
    ) -> tuple[int, list[bytes], bool]:
        """Search for and process emails."""
        count = 0
        unique_email_ids = set()
        found_data = []
        image_found = False

        if len(subjects) > 2:
            matched_ids_str = await self._broad_search_then_filter(
                account, email_addresses, date, subjects, cache
            )
            if matched_ids_str:
                raw_ids = [eid.encode() for eid in matched_ids_str]
                filtered_new_ids = self._filter_unique_ids(raw_ids, unique_email_ids)

                if filtered_new_ids:
                    count, img_found = await self._process_matched_emails(
                        account,
                        config,
                        filtered_new_ids,
                        count,
                        cache,
                        shipper_cfg,
                        sensor_type,
                        result,
                        found_data,
                    )
                    if img_found:
                        image_found = True

        else:
            for subject in subjects:
                (server_response, sdata) = await email_search(
                    account,
                    email_addresses,
                    date,
                    subject,
                )
                if server_response == "OK" and sdata[0]:
                    raw_ids = sdata[0].split()
                    filtered_new_ids = self._filter_unique_ids(
                        raw_ids, unique_email_ids
                    )

                    if not filtered_new_ids:
                        continue

                    count, img_found = await self._process_matched_emails(
                        account,
                        config,
                        filtered_new_ids,
                        count,
                        cache,
                        shipper_cfg,
                        sensor_type,
                        result,
                        found_data,
                    )
                    if img_found:
                        image_found = True

        return count, found_data, image_found

    def _filter_unique_ids(
        self, email_ids: list[bytes], unique_email_ids: set
    ) -> list[bytes]:
        """Filter out already processed email IDs."""
        new_ids = []
        for eid in email_ids:
            eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
            if eid_str not in unique_email_ids:
                unique_email_ids.add(eid_str)
                new_ids.append(eid)
        return new_ids

    async def _process_matched_emails(
        self,
        account: IMAP4_SSL,
        config: dict[str, Any],
        new_ids: list[bytes],
        current_count: int,
        cache: EmailCache | None,
        shipper_cfg: dict[str, Any] | None,
        sensor_type: str,
        result: dict[str, Any],
        found_data: list[bytes],
    ) -> tuple[int, bool]:
        """Process a batch of matched unique emails."""
        image_found = False
        count = await self._process_emails_by_type(
            account, config, new_ids, current_count, cache
        )
        found_data.append(b" ".join(new_ids))

        if shipper_cfg:
            if await self._extract_images_for_shipper(
                account, new_ids, shipper_cfg, cache
            ):
                image_found = True

        if sensor_type.endswith("_delivered") and sensor_type != AMAZON_DELIVERED:
            await self._check_amazon_mentions(account, new_ids, result, cache)

        return count, image_found

    async def _broad_search_then_filter(
        self,
        account: IMAP4_SSL,
        email_addresses: list[str],
        date: str,
        subjects: list[str],
        cache: EmailCache | None,
    ) -> list[str]:
        """Perform a single IMAP SEARCH by FROM+SINCE and filter subjects client-side."""
        (server_response, sdata) = await email_search(
            account, email_addresses, date, ""
        )
        if server_response != "OK" or not sdata[0]:
            return []

        email_ids = sdata[0].split()
        matched_ids = []

        for eid in email_ids:
            if cache:
                header_data = (await cache.fetch(eid, "(HEADER)"))[1]
            else:
                header_data = (await email_fetch_headers(account, eid))[1]

            for response_part in header_data:
                if isinstance(response_part, (bytes, bytearray)):
                    msg = email.message_from_bytes(response_part)

                    subject = get_decoded_subject(msg)
                    if not subject:
                        continue

                    if any(s.lower() in subject.lower() for s in subjects):
                        matched_ids.append(
                            eid.decode() if isinstance(eid, bytes) else str(eid)
                        )

        return matched_ids

    async def _process_tracking_numbers(
        self,
        sensor_type: str,
        found_data: list,
        account: IMAP4_SSL,
        cache: EmailCache | None = None,
    ) -> list:
        """Process tracking numbers for the sensor."""
        tracking_key = f"{'_'.join(sensor_type.split('_')[:-1])}_tracking"
        if (
            tracking_key not in SENSOR_DATA
            or ATTR_PATTERN not in SENSOR_DATA[tracking_key]
        ):
            return []

        pattern = SENSOR_DATA[tracking_key][ATTR_PATTERN][0]
        tracking_nums = []
        for sdata in found_data:
            tracking_nums.extend(
                await get_tracking(sdata.decode(), account, pattern, cache)
            )

        return list(dict.fromkeys(tracking_nums))

    async def _setup_image_extraction(
        self,
        sensor_type: str,
        image_path: str,
    ) -> dict | None:
        """Set up image extraction configuration."""
        if not sensor_type.endswith("_delivered"):
            return None

        shipper_name = sensor_type.replace("_delivered", "")
        camera_key = f"{shipper_name}_camera"
        if camera_key not in CAMERA_DATA or camera_key in (
            "usps_camera",
            "generic_camera",
        ):
            return None

        extraction_config = CAMERA_EXTRACTION_CONFIG.get(shipper_name, {})
        absolute_image_path = image_path.rstrip("/") + "/"

        def _create_dir():
            path = Path(absolute_image_path) / shipper_name
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)

        await self.hass.async_add_executor_job(_create_dir)

        return {
            "name": shipper_name,
            "image_path": absolute_image_path,
            "image_name": self.config.get(f"{shipper_name}_image")
            or f"{shipper_name}_delivery.jpg",
            "image_type": extraction_config.get("image_type", "jpeg"),
            "cid_name": extraction_config.get("cid_name"),
            "pattern": extraction_config.get("attachment_filename_pattern"),
        }

    async def _process_emails_by_type(
        self,
        account: IMAP4_SSL,
        config: dict,
        ids: list,
        current_count: int,
        cache: EmailCache | None = None,
    ) -> int:
        """Process emails based on body search or just count."""
        if ATTR_BODY in config:
            body_count = config.get(ATTR_BODY_COUNT, False)
            mock_data = (b" ".join(ids),)
            return current_count + await find_text(
                mock_data,
                account,
                config[ATTR_BODY],
                body_count,
                cache,
            )
        return current_count + len(ids)

    async def _extract_images_for_shipper(
        self,
        account: IMAP4_SSL,
        ids: list,
        s_config: dict,
        cache: EmailCache | None = None,
    ) -> bool:
        """Extract delivery images from emails."""
        image_found = False
        for eid in ids:
            if cache:
                msg_parts = (await cache.fetch(eid, "(RFC822)"))[1]
            else:
                msg_parts = (await email_fetch(account, eid, "(RFC822)"))[1]
            for response_part in msg_parts:
                if isinstance(response_part, (bytes, bytearray)):
                    if generic_delivery_image_extraction(
                        response_part,
                        s_config["image_path"],
                        s_config["image_name"],
                        s_config["name"],
                        s_config["image_type"],
                        s_config["cid_name"],
                        s_config["pattern"],
                    ):
                        _LOGGER.debug("Extracted image for %s", s_config["name"])
                        image_found = True
        return image_found

    async def _check_amazon_mentions(
        self,
        account: IMAP4_SSL,
        ids: list,
        result: dict,
        cache: EmailCache | None = None,
    ):
        """Check for Amazon mentions in emails."""
        mock_data = (b" ".join(ids),)
        amazon_mentions = await find_text(
            mock_data,
            account,
            AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
            False,
            cache,
        )
        if amazon_mentions > 0:
            result["amazon_delivered_by_others"] = (
                result.get("amazon_delivered_by_others", 0) + amazon_mentions
            )
