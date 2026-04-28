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
    CONF_FORWARDING_HEADER,
    SENSOR_DATA,
)
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

        # _packages sensors with no email/subject are computed in process_batch
        # as delivering + delivered; skip IMAP search here.
        if sensor_type.endswith("_packages") and not email_addresses and not subjects:
            _LOGGER.debug(
                "Skipping email search for %s: no email addresses configured",
                sensor_type,
            )
            return {ATTR_COUNT: 0, ATTR_TRACKING: []}

        forwarding_header, email_addresses = self._resolve_forwarding(email_addresses)

        # _delivering/_exception/_packages use the extended window so in-transit
        # packages remain visible across the midnight boundary.
        # _delivered uses today's date for the sensor count (resets at midnight)
        # but also searches the extended window to obtain tracking numbers for
        # deduplication — without those, a package delivered yesterday would still
        # appear as "delivering" today because the delivering email is in the window
        # but the delivered email is not.
        is_delivered = sensor_type.endswith("_delivered")
        search_date = date
        if since_date and sensor_type.endswith(
            ("_delivering", "_exception", "_delivered", "_packages")
        ):
            search_date = since_date

        result = {ATTR_COUNT: 0, ATTR_TRACKING: []}

        # Skip email search for sensors with no email addresses configured
        # (e.g. *_packages sensors that are empty dicts in SENSOR_DATA)
        if not email_addresses:
            _LOGGER.debug(
                "Skipping email search for %s: no email addresses configured",
                sensor_type,
            )
            return result

        image_path = self.config.get("image_path")
        # Setup image extraction
        shipper_cfg = await self._setup_image_extraction(sensor_type, image_path)
        image_found = False

        count, found_data, image_found = await self._search_for_emails(
            account,
            email_addresses,
            search_date,
            subjects,
            config,
            shipper_cfg,
            sensor_type,
            result,
            cache,
            forwarding_header,
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

        # For _delivered sensors, the extended-window search gives us tracking
        # numbers needed for deduplication (above), but the count must reflect
        # only today's deliveries so the sensor resets at midnight.
        if is_delivered and since_date and search_date != date:
            today_result: dict[str, Any] = {ATTR_COUNT: 0, ATTR_TRACKING: []}
            today_count, today_found, _ = await self._search_for_emails(
                account,
                email_addresses,
                date,
                subjects,
                config,
                shipper_cfg,
                sensor_type,
                today_result,
                cache,
                forwarding_header,
            )
            today_tracking = await self._process_tracking_numbers(
                sensor_type, today_found, account, cache
            )
            count = len(today_tracking) if today_tracking else today_count

        result[ATTR_COUNT] = count
        if shipper_cfg:
            image_attr = f"{shipper_cfg['name']}_image"
            result[image_attr] = shipper_cfg["image_name"]
            result["image_path"] = image_path

            if not image_found:
                await self._copy_generic_placeholder(shipper_cfg)

        return result

    def _resolve_forwarding(self, email_addresses: list[str]) -> tuple[str, list[str]]:
        """Return (forwarding_header, resolved_email_addresses).

        Header mode: uses original-sender header for matching; address list
        is passed as-is so IMAP can match via HEADER substring.
        Address-list mode: prepends the user's forwarded addresses so that
        emails arriving through a forwarding service are also matched.
        """
        forwarding_header = self.config.get(CONF_FORWARDING_HEADER, "")
        if forwarding_header and forwarding_header != "(none)":
            return forwarding_header, email_addresses
        forwarding_header = ""
        forwarded_emails = self.config.get("forwarded_emails", [])
        if isinstance(forwarded_emails, str):
            forwarded_emails = [
                e.strip() for e in forwarded_emails.split(",") if e.strip()
            ]
        if forwarded_emails:
            email_addresses = forwarded_emails + email_addresses
        return forwarding_header, email_addresses

    async def process_batch(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> dict[str, Any]:
        """Process multiple generic sensors in batch."""
        batch_results, all_tracking = await self._process_individual_sensors(
            account, date, sensors, cache, since_date
        )

        self._deduplicate_batch_tracking(batch_results)
        self._compute_package_totals(batch_results)

        # Merge results and aggregate global tracking
        res = {}
        for sensor, sensor_res in batch_results:
            res.update(sensor_res)
            # Expose per-sensor raw tracking for coordinator state management.
            # Keyed as "_tracking_details" to distinguish from the public data dict.
            tracking = sensor_res.get(ATTR_TRACKING)
            if tracking and sensor.endswith(
                ("_delivering", "_delivered", "_exception")
            ):
                res.setdefault("_tracking_details", {})[sensor] = list(tracking)

        if all_tracking:
            res[ATTR_TRACKING] = list(all_tracking)

        return res

    async def _process_individual_sensors(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> tuple[list[tuple[str, dict[str, Any]]], set[str]]:
        """Process each sensor independently and aggregate tracking."""
        batch_results = []
        all_tracking = set()

        for sensor in sensors:
            sensor_res = await self.process(
                account, date, sensor, cache, since_date=since_date
            )
            # Replicate coordinator dictionary logic for local sensor counts
            if sensor not in sensor_res and ATTR_COUNT in sensor_res:
                sensor_res[sensor] = sensor_res[ATTR_COUNT]

            # Record results for post-processing
            batch_results.append((sensor, sensor_res))

            # Aggregate all tracking numbers found
            if ATTR_TRACKING in sensor_res:
                all_tracking.update(sensor_res[ATTR_TRACKING])

        return batch_results, all_tracking

    def _deduplicate_batch_tracking(
        self,
        batch_results: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Deduplicate tracking numbers across sensors based on shipper prefix."""
        shippers = {}
        for sensor, sensor_res in batch_results:
            # Prefix is everything before the last underscore (e.g., 'ups', 'fedex')
            prefix = "_".join(sensor.split("_")[:-1])
            if prefix not in shippers:
                shippers[prefix] = {
                    "delivered": set(),
                    "delivering": set(),
                    "update_targets": [],
                    "package_targets": [],
                }

            tracking = set(sensor_res.get(ATTR_TRACKING, []))
            if sensor.endswith("_delivered"):
                shippers[prefix]["delivered"].update(tracking)
            elif sensor.endswith(("_delivering", "_exception")):
                shippers[prefix]["delivering"].update(tracking)
                shippers[prefix]["update_targets"].append((sensor, sensor_res))
            elif sensor.endswith("_packages"):
                shippers[prefix]["package_targets"].append((sensor, sensor_res))

        for data in shippers.values():
            # Remove "delivered" tracking numbers from in-transit sensors
            self._apply_deduplication(data["update_targets"], data["delivered"])
            # Remove "delivering" and "delivered" tracking numbers from _packages
            # so _packages only shows packages not yet out for delivery or delivered
            in_pipeline = data["delivering"] | data["delivered"]
            self._apply_deduplication(data["package_targets"], in_pipeline)

    def _apply_deduplication(
        self,
        targets: list[tuple[str, dict[str, Any]]],
        delivered_ids: set[str],
    ) -> None:
        """Apply deduplication logic to a list of target sensors."""
        if not delivered_ids:
            return

        for sensor, sensor_res in targets:
            original_tracking = sensor_res.get(ATTR_TRACKING, [])
            new_tracking = [
                tid for tid in original_tracking if tid not in delivered_ids
            ]

            if len(new_tracking) != len(original_tracking):
                sensor_res[ATTR_TRACKING] = new_tracking
                sensor_res[sensor] = len(new_tracking)
                if ATTR_COUNT in sensor_res:
                    sensor_res[ATTR_COUNT] = len(new_tracking)

    def _compute_package_totals(
        self,
        batch_results: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Compute _packages sensors with empty config as delivering + delivered.

        These sensors have no IMAP search of their own; their value is the
        sum of the shipper's _delivering and _delivered counts (matching the
        original pre-refactor behaviour in helpers.py).
        """
        sensor_counts = {
            sensor: sensor_res.get(sensor, sensor_res.get(ATTR_COUNT, 0))
            for sensor, sensor_res in batch_results
        }

        for sensor, sensor_res in batch_results:
            if not sensor.endswith("_packages"):
                continue
            config = SENSOR_DATA.get(sensor, {})
            if config.get(ATTR_EMAIL) or config.get(ATTR_SUBJECT):
                continue  # sensor has its own IMAP search config
            prefix = sensor.replace("_packages", "")
            computed = sensor_counts.get(f"{prefix}_delivering", 0) + sensor_counts.get(
                f"{prefix}_delivered", 0
            )
            sensor_res[sensor] = computed
            sensor_res[ATTR_COUNT] = computed

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
        forwarding_header: str = "",
    ) -> tuple[int, list[bytes], bool]:
        """Search for and process emails."""
        count = 0
        unique_email_ids = set()
        found_data = []
        image_found = False

        (server_response, sdata) = await email_search(
            account,
            email_addresses,
            date,
            subjects,
            forwarding_header,
        )

        if server_response == "OK" and sdata[0]:
            raw_ids = sdata[0].split()
            _LOGGER.debug(
                "Found %d matching email IDs for %s: %s",
                len(raw_ids),
                sensor_type,
                [eid.decode() if isinstance(eid, bytes) else eid for eid in raw_ids],
            )
            verified_ids = await self._verify_matched_subjects(
                account, raw_ids, sensor_type, subjects, cache
            )
            filtered_new_ids = self._filter_unique_ids(verified_ids, unique_email_ids)

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

        return count, found_data, image_found

    def _decode_subject(self, header_part: bytes | bytearray) -> str | None:
        """Decode MIME encoded subject from email header part."""
        msg = email.message_from_bytes(header_part)
        header_val = msg.get("subject")
        if not header_val:
            return None

        decoded = decode_header(header_val)[0]
        subject_bytes, encoding = decoded
        if encoding:
            try:
                if isinstance(subject_bytes, bytes):
                    return subject_bytes.decode(encoding, "ignore").strip()
                return str(subject_bytes).strip()
            except (LookupError, UnicodeError):
                pass

        if isinstance(subject_bytes, bytes):
            return subject_bytes.decode("utf-8", "ignore").strip()
        return str(subject_bytes).strip()

    async def _verify_matched_subjects(
        self,
        account: IMAP4_SSL,
        email_ids: list[bytes],
        sensor_type: str,
        expected_subjects: list[str],
        cache: EmailCache | None = None,
    ) -> list[bytes]:
        """Verify the subject of each matched email locally and log for debugging."""
        if not expected_subjects:
            return email_ids

        verified_ids = []
        expected_subjects_lower = [s.lower() for s in expected_subjects]

        for eid in email_ids:
            try:
                if cache:
                    header_data = (
                        await cache.fetch(eid, "(BODY[HEADER.FIELDS (SUBJECT)])")
                    )[1]
                else:
                    header_data = (await email_fetch_headers(account, eid))[1]

                subject_found = False
                for part in header_data:
                    if isinstance(part, (bytes, bytearray)):
                        subject = self._decode_subject(part)
                        if not subject:
                            continue

                        _LOGGER.debug(
                            "Matched email for %s (ID %s): %s",
                            sensor_type,
                            eid.decode() if isinstance(eid, bytes) else eid,
                            subject,
                        )
                        subject_lower = subject.lower()
                        if any(
                            expected in subject_lower
                            for expected in expected_subjects_lower
                        ):
                            subject_found = True

                if subject_found:
                    verified_ids.append(eid)
                else:
                    _LOGGER.debug(
                        "Email ID %s rejected for %s: Subject did not match any expected subjects.",
                        eid.decode() if isinstance(eid, bytes) else eid,
                        sensor_type,
                    )
            except (OSError, AttributeError) as err:
                _LOGGER.debug("Could not fetch subject for email %s: %s", eid, err)

        return verified_ids

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
