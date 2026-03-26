"""Base Shipper class."""
from __future__ import annotations

import email
import logging
import re
from pathlib import Path
from shutil import copyfile
from typing import Any

import dateparser
import homeassistant.helpers.config_validation as cv
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED,
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_BODY,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_HUB,
    AMAZON_HUB_BODY,
    AMAZON_HUB_SUBJECT,
    AMAZON_HUB_SUBJECT_SEARCH,
    AMAZON_ORDER,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_OTP,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    AMAZON_PACKAGES,
    ATTR_CODE,
    ATTR_COUNT,
    ATTR_ORDER,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    DEFAULT_AMAZON_DAYS,
)
from custom_components.mail_and_packages.utils.amazon import (
    _extract_hub_code,
    amazon_email_addresses,
    download_amazon_img,
    extract_order_numbers,
    get_amazon_image_url,
    get_decoded_subject,
    get_email_body,
    parse_amazon_arrival_date,
    search_amazon_emails,
)
from custom_components.mail_and_packages.utils.date import get_today
from custom_components.mail_and_packages.utils.image import cleanup_images
from custom_components.mail_and_packages.utils.imap import email_fetch, email_search

from .base import Shipper

_LOGGER = logging.getLogger(__name__)


class AmazonShipper(Shipper):
    """Amazon shipper implementation."""

    @property
    def name(self) -> str:
        """Return shipper name."""
        return "amazon"

    async def process(
        self, account: IMAP4_SSL, date: str, sensor_type: str
    ) -> dict[str, Any]:
        """Process Amazon-specific emails."""
        fwds = cv.ensure_list_csv(self.config.get(CONF_AMAZON_FWDS))
        days = self.config.get(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)
        domain = self.config.get(CONF_AMAZON_DOMAIN)

        if sensor_type in [AMAZON_PACKAGES, AMAZON_ORDER]:
            param = "count" if sensor_type == AMAZON_PACKAGES else "order"
            result = await self._parse_amazon_emails(account, param, fwds, days, domain)
            return {sensor_type: result}

        if sensor_type == AMAZON_HUB:
            return await self._amazon_hub(account, fwds)

        if sensor_type == AMAZON_OTP:
            result = await self._amazon_otp(account, fwds)
            return {sensor_type: result}

        if sensor_type == AMAZON_EXCEPTION:
            return await self._amazon_exception(account, fwds, domain)

        if sensor_type == AMAZON_DELIVERED:
            image_path = self.config.get("image_path")
            image_name = self.config.get("image_name")
            result = await self._amazon_search(
                account, image_path, image_name, domain, fwds
            )
            return {sensor_type: result}

        return {ATTR_COUNT: 0}

    # Internal helper methods (migrated from helpers.py)

    async def _parse_amazon_emails(
        self,
        account: IMAP4_SSL,
        param: str,
        fwds: list[str] | None = None,
        days: int = DEFAULT_AMAZON_DAYS,
        domain: str | None = None,
    ) -> list[str] | int:
        """Parse Amazon emails for delivery date and order number."""
        today_date = get_today()
        packages_arriving_today = {}
        delivered_packages = {}
        amazon_delivered = []
        deliveries_today = []
        all_shipped_orders = set()

        address_list = amazon_email_addresses(fwds, domain)
        unique_emails = await search_amazon_emails(account, address_list, days)
        order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

        for email_id in unique_emails:
            fetch_id = email_id.decode() if isinstance(email_id, bytes) else email_id
            data = (await email_fetch(account, fetch_id, "(RFC822)"))[1]

            for response_part in data:
                if not isinstance(response_part, (bytes, bytearray)):
                    continue

                msg = email.message_from_bytes(response_part)
                email_date_str = msg.get("Date")
                email_date = None
                if email_date_str:
                    parsed_date = await self.hass.async_add_executor_job(
                        dateparser.parse, email_date_str
                    )
                    if parsed_date:
                        email_date = parsed_date.date()

                email_subject = get_decoded_subject(msg)
                if any(
                    s.lower() in email_subject.lower() for s in AMAZON_ORDERED_SUBJECT
                ):
                    continue

                email_msg = get_email_body(msg)

                if any(
                    s.lower() in email_subject.lower() for s in AMAZON_DELIVERED_SUBJECT
                ):
                    orders = extract_order_numbers(email_subject, order_pattern)
                    if not orders and email_msg:
                        orders = extract_order_numbers(email_msg, order_pattern)
                    for o in orders:
                        delivered_packages[o] = delivered_packages.get(o, 0) + 1
                        if o not in amazon_delivered:
                            amazon_delivered.append(o)
                    continue

                order_id = None
                orders = extract_order_numbers(email_subject, order_pattern)
                if orders:
                    order_id = orders[0]
                elif email_msg:
                    orders = extract_order_numbers(email_msg, order_pattern)
                    if orders:
                        order_id = orders[0]

                if order_id:
                    all_shipped_orders.add(order_id)

                if email_msg:
                    parsed_arrival = await parse_amazon_arrival_date(
                        self.hass, email_msg, email_date
                    )
                    if parsed_arrival == today_date:
                        if order_id:
                            packages_arriving_today[order_id] = (
                                packages_arriving_today.get(order_id, 0) + 1
                            )
                        else:
                            deliveries_today.append("Amazon Order")

        deliveries_today = [
            item for item in deliveries_today if item not in amazon_delivered
        ]
        final_count = 0
        for order_id, arriving_count in packages_arriving_today.items():
            delivered_count = delivered_packages.get(order_id, 0)
            final_count += max(0, arriving_count - delivered_count)
        final_count += len(deliveries_today)

        if param == "count":
            return final_count
        return list(all_shipped_orders)

    async def _amazon_search(
        self,
        account: IMAP4_SSL,
        image_path: str,
        amazon_image_name: str,
        amazon_domain: str,
        fwds: list[str] | None = None,
    ) -> int:
        """Find Amazon Delivered email."""
        _LOGGER.debug("=== AMAZON DELIVERED SEARCH START ===")
        subjects = AMAZON_DELIVERED_SUBJECT
        today = get_today().strftime("%d-%b-%Y")
        count = 0
        image_found = False

        await self.hass.async_add_executor_job(
            cleanup_images, f"{image_path or ''}amazon/"
        )

        address_list = amazon_email_addresses(fwds, amazon_domain)
        _LOGGER.debug("Amazon email search addresses: %s", address_list)
        for subject in subjects:
            (server_response, data) = await email_search(
                account, address_list, today, subject
            )
            if server_response == "OK" and data[0] is not None and data[0] != b"":
                email_count = len(data[0].split())
                count += email_count

                img_url = await get_amazon_image_url(data[0], account)
                if img_url and image_path and amazon_image_name:
                    await download_amazon_img(img_url, image_path, amazon_image_name, self.hass)
                    image_found = True

        if (count == 0 or not image_found) and image_path and amazon_image_name:
            nomail = f"{Path(__file__).parent.parent}/no_deliveries_amazon.jpg"
            try:
                await self.hass.async_add_executor_job(
                    copyfile, nomail, f"{image_path}amazon/" + amazon_image_name
                )
            except OSError as err:
                _LOGGER.error("Error attempting to copy image: %s", err)
        return count

    async def _amazon_hub(
        self, account: IMAP4_SSL, fwds: list[str] | None = None
    ) -> dict[str, Any]:
        """Find Amazon Hub code."""
        _LOGGER.debug("=== AMAZON HUB SEARCH START ===")
        count = 0
        code = []
        processed_ids = []
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, "amazon.com")
        for search_subject in AMAZON_HUB_SUBJECT:
            (server_response, data) = await email_search(
                account, address_list, today, search_subject
            )
            if server_response == "OK" and data[0] is not None:
                for num in data[0].split():
                    if num in processed_ids:
                        continue
                    processed_ids.append(num)
                    msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
                    for response_part in msg_parts:
                        if isinstance(response_part, (bytes, bytearray)):
                            msg = email.message_from_bytes(response_part)
                            actual_subject = get_decoded_subject(msg)
                            body = get_email_body(msg)
                            if (
                                hub_code := _extract_hub_code(
                                    body,
                                    AMAZON_HUB_BODY,
                                    actual_subject,
                                    AMAZON_HUB_SUBJECT_SEARCH,
                                )
                            ):
                                count += 1
                                if hub_code not in code:
                                    code.append(hub_code)
        return {ATTR_COUNT: count, ATTR_CODE: code}

    async def _amazon_otp(
        self, account: IMAP4_SSL, fwds: list[str] | None = None
    ) -> dict[str, Any]:
        """Find Amazon OTP code."""
        code = []
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, "amazon.com")
        (server_response, data) = await email_search(
            account, address_list, today, AMAZON_OTP_SUBJECT
        )
        if server_response == "OK" and data[0] is not None:
            for num in data[0].split():
                msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
                for response_part in msg_parts:
                    if isinstance(response_part, (bytes, bytearray)):
                        msg = email.message_from_bytes(response_part)
                        body = get_email_body(msg)
                        if (
                            found := re.compile(AMAZON_OTP_REGEX).search(body)
                        ) is not None:
                            code.append(found.group(2))
        return {ATTR_CODE: code}

    async def _amazon_exception(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Find Amazon exception emails."""
        count = 0
        orders = []
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, domain)
        (server_response, data) = await email_search(
            account, address_list, today, AMAZON_EXCEPTION_SUBJECT
        )
        if server_response == "OK" and data[0] is not None:
            order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")
            for num in data[0].split():
                msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
                for response_part in msg_parts:
                    if isinstance(response_part, (bytes, bytearray)):
                        msg = email.message_from_bytes(response_part)
                        body = get_email_body(msg)
                        subject = get_decoded_subject(msg)
                        if AMAZON_EXCEPTION_BODY in body:
                            count += 1
                            if found := order_pattern.findall(body):
                                orders.extend(found)
                            if found := order_pattern.findall(subject):
                                orders.extend(found)
        return {ATTR_COUNT: count, ATTR_ORDER: orders}
