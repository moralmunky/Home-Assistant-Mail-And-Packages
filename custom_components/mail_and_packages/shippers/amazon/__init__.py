"""Amazon Shipper class."""

from __future__ import annotations

import logging
import re
from typing import Any

import homeassistant.helpers.config_validation as cv
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages import const
from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED,
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_DELIVERING,
    AMAZON_EXCEPTION,
    AMAZON_HUB,
    AMAZON_HUB_SUBJECT,
    AMAZON_ORDER,
    AMAZON_ORDER_DETAILS,
    AMAZON_OTP,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    AMAZON_PACKAGES,
    ATTR_COUNT,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_FORWARDING_HEADER,
    DEFAULT_AMAZON_DAYS,
)
from custom_components.mail_and_packages.shippers.base import Shipper
from custom_components.mail_and_packages.utils.cache import EmailCache

from .helpers import (
    _extract_exception_from_parts as helper_extract_exception_from_parts,
)
from .helpers import (
    _extract_first_order_id as helper_extract_first_order_id,
)
from .helpers import (
    _extract_hub_code_from_parts as helper_extract_hub_code_from_parts,
)
from .helpers import (
    _is_amazon_delivered as helper_is_amazon_delivered,
)
from .image import AmazonImageMixin
from .search import AmazonSearchMixin

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "AMAZON_DELIVERED_SUBJECT",
    "AMAZON_HUB_SUBJECT",
    "AMAZON_OTP_REGEX",
    "AMAZON_OTP_SUBJECT",
    "AmazonImageMixin",
    "AmazonSearchMixin",
    "AmazonShipper",
]


class AmazonShipper(AmazonSearchMixin, Shipper):
    """Amazon shipper implementation."""

    @property
    def name(self) -> str:
        """Return shipper name."""
        return "amazon"

    @classmethod
    def handles_sensor(cls, sensor_type: str) -> bool:
        """Return True if this shipper handles the given sensor type."""
        return sensor_type.startswith("amazon_") or sensor_type == AMAZON_PACKAGES

    async def process(
        self,
        account: IMAP4_SSL,
        date: str,
        sensor_type: str,
        cache: EmailCache | None = None,
    ) -> dict[str, Any]:
        """Process Amazon-specific emails."""
        forwarding_header = self.config.get(CONF_FORWARDING_HEADER, "")
        if forwarding_header and forwarding_header != "(none)":
            # Header mode: use native Amazon addresses; fwds not needed
            fwds = None
        else:
            forwarding_header = ""
            fwds = cv.ensure_list_csv(self.config.get(CONF_AMAZON_FWDS))
        days = self.config.get(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)
        domain = self.config.get(CONF_AMAZON_DOMAIN)

        if sensor_type == AMAZON_PACKAGES:
            count = await self._parse_amazon_emails(
                account, "count", fwds, days, domain, cache, forwarding_header
            )
            orders = await self._parse_amazon_emails(
                account, "order", fwds, days, domain, cache, forwarding_header
            )
            details = await self._parse_amazon_emails(
                account, "details", fwds, days, domain, cache, forwarding_header
            )
            return {
                AMAZON_PACKAGES: count,
                AMAZON_ORDER: orders,
                AMAZON_ORDER_DETAILS: details,
            }

        if sensor_type == AMAZON_DELIVERING:
            count, orders = await self._parse_amazon_emails(
                account, "delivering", fwds, days, domain, cache, forwarding_header
            )
            return {
                AMAZON_DELIVERING: count,
                "amazon_delivering_order": orders,
            }

        if sensor_type == AMAZON_ORDER:
            result = await self._parse_amazon_emails(
                account, "order", fwds, days, domain, cache, forwarding_header
            )
            return {AMAZON_ORDER: result}

        if sensor_type == AMAZON_HUB:
            return await self._amazon_hub(
                account, fwds, domain, cache, forwarding_header
            )

        if sensor_type == AMAZON_OTP:
            result = await self._amazon_otp(
                account, fwds, domain, cache, forwarding_header
            )
            return {sensor_type: result}

        if sensor_type == AMAZON_EXCEPTION:
            return await self._amazon_exception(
                account, fwds, domain, cache, forwarding_header
            )

        if sensor_type == AMAZON_DELIVERED:
            image_path = self.config.get("image_path")
            image_name = self.config.get("amazon_image")
            result = await self._amazon_search(
                account,
                image_path,
                image_name,
                domain,
                fwds,
                cache,
                forwarding_header,
            )
            return {
                sensor_type: result,
                const.ATTR_AMAZON_IMAGE: image_name,
                const.ATTR_IMAGE_PATH: image_path,
            }

        return {ATTR_COUNT: 0}

    async def process_batch(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> dict[str, Any]:
        """Process multiple Amazon sensors in batch."""
        res = {}
        for sensor in sensors:
            sensor_res = await self.process(account, date, sensor, cache)
            res.update(sensor_res)
            # Replicate coordinator dictionary logic
            if sensor not in sensor_res:
                if ATTR_COUNT in sensor_res:
                    res[sensor] = sensor_res[ATTR_COUNT]
        return res

    # Delegate helper methods for backward compatibility with direct callers/tests

    def _extract_first_order_id(
        self,
        subject: str,
        body: str | None,
        pattern: re.Pattern,
    ) -> str | None:
        """Extract the first order number found in subject or body."""
        return helper_extract_first_order_id(subject, body, pattern)

    def _is_amazon_delivered(
        self, msg_data: list, subjects: list[str]
    ) -> tuple[bool, list[str]]:
        """Verify if email is a delivered notification and return image URLs."""
        return helper_is_amazon_delivered(msg_data, subjects)

    def _extract_hub_code_from_parts(
        self,
        msg_parts: list[Any],
    ) -> str | None:
        """Extract hub code from email message parts."""
        return helper_extract_hub_code_from_parts(msg_parts)

    def _extract_exception_from_parts(
        self,
        msg_parts: list[Any],
        order_pattern: re.Pattern[str],
    ) -> list[str] | None:
        """Extract matching order numbers if email matches exception body."""
        return helper_extract_exception_from_parts(msg_parts, order_pattern)
