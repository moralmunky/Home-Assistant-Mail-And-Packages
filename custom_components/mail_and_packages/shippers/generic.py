"""Generic Shipper class."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages import const
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
from custom_components.mail_and_packages.utils.email import find_text
from custom_components.mail_and_packages.utils.imap import email_fetch, email_search
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

    async def process(
        self, account: IMAP4_SSL, date: str, sensor_type: str
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

        count = 0
        unique_email_ids = set()
        found_data = []
        result = {ATTR_COUNT: 0, ATTR_TRACKING: []}

        # Image extraction setup
        shipper_name = None
        if sensor_type.endswith("_delivered"):
            potential_shipper = sensor_type.replace("_delivered", "")
            camera_key = f"{potential_shipper}_camera"
            if camera_key in CAMERA_DATA and camera_key not in (
                "usps_camera",
                "generic_camera",
            ):
                shipper_name = potential_shipper

        image_path = self.config.get("image_path")
        self.config.get("image_name") # This is likely wrong for generic
        # In helpers.py, image_name is derived from shipper_name

        if shipper_name:
            image_attr_name = f"ATTR_{shipper_name.upper()}_IMAGE"
            getattr(const, image_attr_name, None)
            image_name_val = f"{shipper_name}_delivery.jpg" # Default

            # We need to get the actual image name from coordinator data if available
            # but Shipper doesn't have direct access to coordinator data yet.
            # In helpers.py, 'data' is passed to get_count.
            # For now, let's use the default or a derived one.

            extraction_config = CAMERA_EXTRACTION_CONFIG.get(shipper_name, {})
            image_type = extraction_config.get("image_type", "jpeg")
            cid_name = extraction_config.get("cid_name")
            attachment_filename_pattern = extraction_config.get(
                "attachment_filename_pattern"
            )

            absolute_image_path = image_path.rstrip("/") + "/"
            absolute_shipper_path = f"{absolute_image_path}{shipper_name}/"

            # Create directory
            if not Path(absolute_shipper_path).exists():
                Path(absolute_shipper_path).mkdir(parents=True, exist_ok=True)

        for subject in subjects:
            (server_response, sdata) = await email_search(
                account, email_addresses, date, subject
            )
            if server_response == "OK" and sdata[0]:
                email_ids = sdata[0].split()
                new_email_ids = []
                for eid in email_ids:
                    eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
                    if eid_str not in unique_email_ids:
                        unique_email_ids.add(eid_str)
                        new_email_ids.append(eid)

                if not new_email_ids:
                    continue

                if ATTR_BODY in config:
                    body_count = config.get(ATTR_BODY_COUNT, False)
                    # find_text expects sdata as (b"ids",)
                    mock_sdata = (b" ".join(new_email_ids),)
                    count += await find_text(
                        mock_sdata, account, config[ATTR_BODY], body_count
                    )
                else:
                    count += len(new_email_ids)

                found_data.append(b" ".join(new_email_ids))

                # Image extraction
                if shipper_name:
                    for eid in new_email_ids:
                        msg_parts = (await email_fetch(account, eid, "(RFC822)"))[1]
                        for response_part in msg_parts:
                            if isinstance(response_part, (bytes, bytearray)):
                                if generic_delivery_image_extraction(
                                    response_part,
                                    absolute_image_path,
                                    image_name_val,
                                    shipper_name,
                                    image_type,
                                    cid_name,
                                    attachment_filename_pattern,
                                ):
                                    _LOGGER.debug("Extracted image for %s", shipper_name)
                                    # result[image_attr] = image_name_val

                # Amazon mentions
                if sensor_type.endswith("_delivered") and sensor_type != AMAZON_DELIVERED:
                    mock_sdata = (b" ".join(new_email_ids),)
                    amazon_mentions = await find_text(
                        mock_sdata,
                        account,
                        AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
                        False,
                    )
                    if amazon_mentions > 0:
                        result["amazon_delivered_by_others"] = (
                            result.get("amazon_delivered_by_others", 0) + amazon_mentions
                        )

        # Tracking numbers
        tracking_sensor_key = f"{'_'.join(sensor_type.split('_')[:-1])}_tracking"
        if (
            tracking_sensor_key in SENSOR_DATA
            and ATTR_PATTERN in SENSOR_DATA[tracking_sensor_key]
        ):
            track_pattern = SENSOR_DATA[tracking_sensor_key][ATTR_PATTERN][0]
            tracking_nums = []
            for sdata in found_data:
                tracking_nums.extend(await get_tracking(sdata.decode(), account, track_pattern))

            unique_tracking = list(dict.fromkeys(tracking_nums))
            result[ATTR_TRACKING] = unique_tracking
            if unique_tracking:
                count = len(unique_tracking)

        result[ATTR_COUNT] = count
        return result
