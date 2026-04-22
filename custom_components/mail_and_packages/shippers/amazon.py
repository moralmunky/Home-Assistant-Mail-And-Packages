"""Base Shipper class."""

from __future__ import annotations

import datetime
import email
import logging
import re
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio
import dateparser
import homeassistant.helpers.config_validation as cv
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages import const
from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED,
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_BODY,
    AMAZON_EXCEPTION_ORDER,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_HUB,
    AMAZON_HUB_BODY,
    AMAZON_HUB_CODE,
    AMAZON_HUB_SUBJECT,
    AMAZON_HUB_SUBJECT_SEARCH,
    AMAZON_ORDER,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_OTP,
    AMAZON_OTP_CODE,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    AMAZON_PACKAGES,
    ATTR_COUNT,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_DURATION,
    DEFAULT_AMAZON_DAYS,
)
from custom_components.mail_and_packages.utils.amazon import (
    _extract_hub_code,
    amazon_email_addresses,
    download_amazon_img,
    extract_order_numbers,
    get_amazon_image_urls,
    get_decoded_subject,
    get_email_body,
    parse_amazon_arrival_date,
    search_amazon_emails,
)
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.date import get_today
from custom_components.mail_and_packages.utils.image import (
    cleanup_images,
    generate_delivery_gif,
    random_filename,
    resize_images,
)
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_search,
)

from .base import Shipper

_LOGGER = logging.getLogger(__name__)


class AmazonShipper(Shipper):
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
        fwds = cv.ensure_list_csv(self.config.get(CONF_AMAZON_FWDS))
        days = self.config.get(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)
        domain = self.config.get(CONF_AMAZON_DOMAIN)

        if sensor_type in [AMAZON_PACKAGES, AMAZON_ORDER]:
            param = "count" if sensor_type == AMAZON_PACKAGES else "order"
            result = await self._parse_amazon_emails(
                account, param, fwds, days, domain, cache
            )
            return {sensor_type: result}

        if sensor_type == AMAZON_HUB:
            return await self._amazon_hub(account, fwds, cache)

        if sensor_type == AMAZON_OTP:
            return await self._amazon_otp(account, fwds, cache)

        if sensor_type == AMAZON_EXCEPTION:
            return await self._amazon_exception(account, fwds, domain, cache)

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
        since_date: str | None = None,  # noqa: ARG002 — Amazon manages its own date window
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

    # Internal helper methods (migrated from helpers.py)

    async def _parse_amazon_emails(
        self,
        account: IMAP4_SSL,
        param: str,
        fwds: list[str] | None = None,
        days: int = DEFAULT_AMAZON_DAYS,
        domain: str | None = None,
        cache: EmailCache | None = None,
    ) -> list[str] | int:
        """Parse Amazon emails for delivery date and order number."""
        today_date = get_today()
        address_list = amazon_email_addresses(fwds, domain)
        unique_emails = await search_amazon_emails(
            account, address_list, days, domain, cache
        )
        order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

        context = {
            "today": today_date,
            "packages_arriving_today": {},
            "delivered_packages": {},
            "amazon_delivered": [],
            "deliveries_today": [],
            "all_shipped_orders": set(),
            "order_pattern": order_pattern,
        }

        for email_id in unique_emails:
            await self._process_amazon_email(account, email_id, context, cache)

        final_count = self._calculate_final_count(context)

        if param == "count":
            return final_count
        return list(context["all_shipped_orders"])

    async def _process_amazon_email(
        self,
        account: IMAP4_SSL,
        email_id: bytes | str,
        ctx: dict,
        cache: EmailCache | None = None,
    ):
        """Process a single Amazon email."""
        fetch_id = email_id.decode() if isinstance(email_id, bytes) else email_id
        if cache:
            data = (await cache.fetch(fetch_id, "(RFC822)"))[1]
        else:
            data = (await email_fetch(account, fetch_id, "(RFC822)"))[1]

        for response_part in data:
            if not isinstance(response_part, (bytes, bytearray)):
                continue

            msg = email.message_from_bytes(response_part)
            email_date = await self._parse_email_date(msg)
            email_subject = get_decoded_subject(msg)

            if any(s.lower() in email_subject.lower() for s in AMAZON_ORDERED_SUBJECT):
                continue

            email_msg = get_email_body(msg)
            if any(
                s.lower() in email_subject.lower() for s in AMAZON_DELIVERED_SUBJECT
            ):
                self._handle_delivered_email(email_subject, email_msg, ctx)
                continue

            await self._handle_shipping_email(email_subject, email_msg, email_date, ctx)

    async def _parse_email_date(
        self,
        msg: email.message.Message,
    ) -> datetime.date | None:
        """Parse the date from an email message."""
        date_str = msg.get("Date")
        if not date_str:
            return None
        parsed = await self.hass.async_add_executor_job(dateparser.parse, date_str)
        return parsed.date() if parsed else None

    def _handle_delivered_email(self, subject: str, body: str | None, ctx: dict):
        """Handle an Amazon 'delivered' email."""
        orders = extract_order_numbers(subject, ctx["order_pattern"])
        if not orders and body:
            orders = extract_order_numbers(body, ctx["order_pattern"])
        for o in orders:
            ctx["delivered_packages"][o] = ctx["delivered_packages"].get(o, 0) + 1
            if o not in ctx["amazon_delivered"]:
                ctx["amazon_delivered"].append(o)

    async def _handle_shipping_email(
        self,
        subject: str,
        body: str | None,
        date: datetime.date | None,
        ctx: dict,
    ):
        """Handle an Amazon 'shipping' or 'arriving' email."""
        order_id = self._extract_first_order_id(subject, body, ctx["order_pattern"])
        if order_id:
            ctx["all_shipped_orders"].add(order_id)

        if body:
            parsed_arrival = await parse_amazon_arrival_date(self.hass, body, date)
            if parsed_arrival == ctx["today"]:
                if order_id:
                    ctx["packages_arriving_today"][order_id] = (
                        ctx["packages_arriving_today"].get(order_id, 0) + 1
                    )
                else:
                    ctx["deliveries_today"].append("Amazon Order")

    def _extract_first_order_id(
        self,
        subject: str,
        body: str | None,
        pattern: re.Pattern,
    ) -> str | None:
        """Extract the first order number found in subject or body."""
        orders = extract_order_numbers(subject, pattern)
        if orders:
            return orders[0]
        if body:
            orders = extract_order_numbers(body, pattern)
            if orders:
                return orders[0]
        return None

    def _calculate_final_count(self, ctx: dict) -> int:
        """Calculate the final count of packages arriving today."""
        deliveries_today = [
            item
            for item in ctx["deliveries_today"]
            if item not in ctx["amazon_delivered"]
        ]
        final_count = 0
        for order_id, arriving_count in ctx["packages_arriving_today"].items():
            delivered_count = ctx["delivered_packages"].get(order_id, 0)
            final_count += max(0, arriving_count - delivered_count)
        return final_count + len(deliveries_today)

    async def _amazon_search(
        self,
        account: IMAP4_SSL,
        image_path: str,
        amazon_image_name: str,
        amazon_domain: str,
        fwds: list[str] | None = None,
        cache: EmailCache | None = None,
    ) -> int:
        """Find Amazon Delivered email and handle images."""
        _LOGGER.debug("=== AMAZON DELIVERED SEARCH START ===")
        subjects = AMAZON_DELIVERED_SUBJECT
        today = get_today().strftime("%d-%b-%Y")
        count = 0
        all_image_urls = []

        await self.hass.async_add_executor_job(
            cleanup_images,
            f"{image_path or ''}amazon/",
        )

        address_list = amazon_email_addresses(fwds, amazon_domain)
        _LOGGER.debug("Amazon email search addresses: %s", address_list)
        (server_response, data) = await email_search(
            account,
            address_list,
            today,
            subjects,
        )
        if server_response == "OK" and data[0]:
            for email_id in data[0].split():
                count += 1
                urls = await get_amazon_image_urls(email_id, account, cache)
                for url in urls:
                    if url not in all_image_urls:
                        all_image_urls.append(url)

        await self._process_amazon_images(
            all_image_urls, image_path, amazon_image_name, count
        )

        return count

    async def _process_amazon_images(
        self,
        image_urls: list[str],
        image_base_path: str,
        image_name: str,
        email_count: int,
    ) -> None:
        """Process and save Amazon delivery images."""
        if not image_base_path or not image_name:
            return

        amazon_path = Path(image_base_path) / "amazon"
        image_files = await self._download_all_images(image_urls, image_base_path)

        if len(image_files) > 1:
            await self._create_amazon_gif(image_files, amazon_path, image_name)
        elif len(image_files) == 1:
            await self._save_single_amazon_image(
                image_files[0], amazon_path, image_name
            )
        else:
            await self._copy_amazon_placeholder(amazon_path, image_name)

    async def _download_all_images(self, urls: list[str], base_path: str) -> list[str]:
        """Download all image URLs to temporary files."""
        image_files = []
        amazon_path = Path(base_path) / "amazon"
        for url in urls:
            temp_filename = random_filename()
            await download_amazon_img(url, base_path, temp_filename, self.hass)
            full_temp_path = amazon_path / temp_filename
            if await anyio.Path(full_temp_path).exists():
                image_files.append(str(full_temp_path))
        return image_files

    async def _create_amazon_gif(
        self, image_files: list[str], amazon_path: Path, image_name: str
    ) -> None:
        """Create animated GIF from multiple images."""
        _LOGGER.debug("Combining %d Amazon images into GIF", len(image_files))
        resized_images = await self.hass.async_add_executor_job(
            resize_images, image_files, 724, 320
        )
        gif_path = str(amazon_path / image_name)
        duration = self.config.get(CONF_DURATION, 5) * 1000
        await self.hass.async_add_executor_job(
            generate_delivery_gif, resized_images, gif_path, duration
        )
        # Cleanup
        for img in image_files + resized_images:
            if await anyio.Path(img).exists():
                await self.hass.async_add_executor_job(
                    cleanup_images, str(Path(img).parent) + "/", Path(img).name
                )

    async def _save_single_amazon_image(
        self, image_file: str, amazon_path: Path, image_name: str
    ) -> None:
        """Save a single image by renaming it to the final name."""
        final_path = amazon_path / image_name
        if await anyio.Path(final_path).exists():
            await anyio.Path(final_path).unlink()
        await self.hass.async_add_executor_job(Path(image_file).rename, final_path)
        _LOGGER.debug("Single Amazon image saved: %s", image_name)

    async def _copy_amazon_placeholder(
        self, amazon_path: Path, image_name: str
    ) -> None:
        """Copy the Amazon no-delivery placeholder."""
        nomail = f"{Path(__file__).parent.parent}/no_deliveries_amazon.jpg"
        _LOGGER.debug("No Amazon images found in emails, using placeholder")
        try:
            await self.hass.async_add_executor_job(
                copyfile, nomail, str(amazon_path / image_name)
            )
        except OSError as err:
            _LOGGER.error("Error attempting to copy image: %s", err)

    async def _amazon_hub(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        cache: EmailCache | None = None,
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
                account,
                address_list,
                today,
                search_subject,
            )
            if server_response == "OK" and data[0] is not None:
                for num in data[0].split():
                    if num in processed_ids:
                        continue
                    processed_ids.append(num)
                    if cache:
                        msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                    else:
                        msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
                    for response_part in msg_parts:
                        if isinstance(response_part, (bytes, bytearray)):
                            msg = email.message_from_bytes(response_part)
                            actual_subject = get_decoded_subject(msg)
                            body = get_email_body(msg)
                            if hub_code := _extract_hub_code(
                                body,
                                AMAZON_HUB_BODY,
                                actual_subject,
                                AMAZON_HUB_SUBJECT_SEARCH,
                            ):
                                count += 1
                                if hub_code not in code:
                                    code.append(hub_code)
        return {AMAZON_HUB: count, AMAZON_HUB_CODE: code}

    async def _amazon_otp(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        cache: EmailCache | None = None,
    ) -> dict[str, Any]:
        """Find Amazon OTP code."""
        code = []
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, "amazon.com")
        (server_response, data) = await email_search(
            account,
            address_list,
            today,
            AMAZON_OTP_SUBJECT,
        )
        if server_response == "OK" and data[0] is not None:
            for num in data[0].split():
                if cache:
                    msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                else:
                    msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
                for response_part in msg_parts:
                    if isinstance(response_part, (bytes, bytearray)):
                        msg = email.message_from_bytes(response_part)
                        body = get_email_body(msg)
                        if (
                            found := re.compile(AMAZON_OTP_REGEX).search(body)
                        ) is not None:
                            code.append(found.group(2))
        return {AMAZON_OTP: len(code), AMAZON_OTP_CODE: code}

    async def _amazon_exception(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        domain: str | None = None,
        cache: EmailCache | None = None,
    ) -> dict[str, Any]:
        """Find Amazon exception emails."""
        count = 0
        orders = []
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, domain)
        (server_response, data) = await email_search(
            account,
            address_list,
            today,
            AMAZON_EXCEPTION_SUBJECT,
        )
        if server_response == "OK" and data[0] is not None:
            order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")
            for num in data[0].split():
                if cache:
                    msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                else:
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
        return {AMAZON_EXCEPTION: count, AMAZON_EXCEPTION_ORDER: orders}
