"""Search and email processing mixin for Amazon shipper."""

from __future__ import annotations

import datetime
import email
import logging
import re
from typing import Any

import dateparser
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_DELIVERING_SUBJECT,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_ORDER,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_HUB,
    AMAZON_HUB_BODY,
    AMAZON_HUB_CODE,
    AMAZON_HUB_SUBJECT,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_OTP,
    AMAZON_OTP_CODE,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    DEFAULT_AMAZON_DAYS,
)
from custom_components.mail_and_packages.utils.amazon import (
    amazon_email_addresses,
    extract_order_numbers,
    get_decoded_subject,
    get_email_body,
    parse_amazon_arrival_date,
    search_amazon_emails,
)
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.date import get_today
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_search,
)

from .amazon_helpers import (
    _amazon_attr,
    _calculate_delivering_count,
    _calculate_final_count,
    _extract_exception_from_parts,
    _extract_first_order_id,
    _extract_hub_code_from_parts,
)
from .amazon_image import AmazonImageMixin

_LOGGER = logging.getLogger(__name__)


class AmazonSearchMixin(AmazonImageMixin):
    """Mixin providing search, email processing, and image handling for Amazon shipper."""

    hass: Any
    config: dict[str, Any]

    async def _parse_amazon_emails(
        self,
        account: IMAP4_SSL,
        param: str,
        fwds: list[str] | None = None,
        days: int = DEFAULT_AMAZON_DAYS,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> list[str] | int:
        """Parse Amazon emails for delivery date and order number."""
        today_date = _amazon_attr("get_today", get_today)()
        email_addresses_fn = _amazon_attr(
            "amazon_email_addresses", amazon_email_addresses
        )
        address_list = email_addresses_fn(fwds, domain)
        search_emails_fn = _amazon_attr("search_amazon_emails", search_amazon_emails)
        unique_emails = await search_emails_fn(
            account, address_list, days, domain, cache, forwarding_header
        )
        order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

        context = {
            "today": today_date,
            "packages_arriving_today": {},
            "packages_delivering_today": {},
            "delivered_packages": {},
            "amazon_delivered": [],
            "deliveries_today": [],
            "delivering_today": [],
            "all_shipped_orders": set(),
            "order_pattern": order_pattern,
        }

        for email_id in unique_emails:
            await self._process_amazon_email(account, email_id, context, cache)

        if param == "delivering":
            orders = list(context["packages_delivering_today"].keys())
            return _calculate_delivering_count(context), orders

        final_count = _calculate_final_count(context)

        if param == "count":
            return final_count

        return [
            order_id
            for order_id in context["all_shipped_orders"]
            if context["packages_arriving_today"].get(order_id, 0)
            > context["delivered_packages"].get(order_id, 0)
            or (
                context["packages_arriving_today"].get(order_id, 0) == 0
                and context["delivered_packages"].get(order_id, 0) == 0
            )
        ]

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
            fetch_fn = _amazon_attr("email_fetch", email_fetch)
            data = (await fetch_fn(account, fetch_id, "(RFC822)"))[1]

        email_mod = _amazon_attr("email", email)
        for response_part in data:
            if not isinstance(response_part, (bytes, bytearray)):
                continue

            msg = email_mod.message_from_bytes(response_part)
            email_date = await self._parse_email_date(msg)
            email_subject = get_decoded_subject(msg)

            if any(s.lower() in email_subject.lower() for s in AMAZON_ORDERED_SUBJECT):
                continue

            email_msg_fn = _amazon_attr("get_email_body", get_email_body)
            email_msg = email_msg_fn(msg)
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
        extract_fn = _amazon_attr("extract_order_numbers", extract_order_numbers)
        orders = extract_fn(subject, ctx["order_pattern"])
        if not orders and body:
            orders = extract_fn(body, ctx["order_pattern"])
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
        order_id = _extract_first_order_id(subject, body, ctx["order_pattern"])
        if order_id:
            ctx["all_shipped_orders"].add(order_id)

        delivering_subjects = _amazon_attr(
            "AMAZON_DELIVERING_SUBJECT", AMAZON_DELIVERING_SUBJECT
        )
        is_delivering = any(s.lower() in subject.lower() for s in delivering_subjects)

        parsed_arrival = None
        if body:
            parse_arrival_fn = _amazon_attr(
                "parse_amazon_arrival_date", parse_amazon_arrival_date
            )
            parsed_arrival = await parse_arrival_fn(self.hass, body, date)

        # OFD emails received today imply delivery today, even if the body
        # time-window parsing fails (e.g. "Zustellung heute 15:15 - 17:15").
        if is_delivering and date == ctx["today"] and parsed_arrival is None:
            parsed_arrival = ctx["today"]

        if parsed_arrival == ctx["today"]:
            if order_id:
                ctx["packages_arriving_today"][order_id] = (
                    ctx["packages_arriving_today"].get(order_id, 0) + 1
                )
            else:
                ctx["deliveries_today"].append("Amazon Order")

        # Out-for-delivery emails count as delivering when arriving today,
        # or when the OFD email itself arrived today.
        if is_delivering and (parsed_arrival == ctx["today"] or date == ctx["today"]):
            if order_id:
                ctx["packages_delivering_today"][order_id] = (
                    ctx["packages_delivering_today"].get(order_id, 0) + 1
                )
            else:
                ctx["delivering_today"].append("Amazon Order")

    async def _amazon_hub(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> dict[str, Any]:
        """Find Amazon Hub code."""
        _LOGGER.debug("=== AMAZON HUB SEARCH START ===")
        count = 0
        code = []
        processed_ids = []
        today = _amazon_attr("get_today", get_today)().strftime("%d-%b-%Y")
        email_addresses_fn = _amazon_attr(
            "amazon_email_addresses", amazon_email_addresses
        )
        address_list = email_addresses_fn(fwds, domain)
        subjects = _amazon_attr("AMAZON_HUB_SUBJECT", AMAZON_HUB_SUBJECT)
        search_fn = _amazon_attr("email_search", email_search)
        fetch_fn = _amazon_attr("email_fetch", email_fetch)
        for search_subject in subjects:
            (server_response, data) = await search_fn(
                account,
                address_list,
                today,
                search_subject,
                body=AMAZON_HUB_BODY,
                header=forwarding_header,
            )
            if server_response != "OK" or data[0] is None:
                continue

            for num in data[0].split():
                if num in processed_ids:
                    continue
                processed_ids.append(num)
                if cache:
                    msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                else:
                    msg_parts = (await fetch_fn(account, num, "(RFC822)"))[1]

                if hub_code := _extract_hub_code_from_parts(msg_parts):
                    count += 1
                    if hub_code not in code:
                        code.append(hub_code)
        return {AMAZON_HUB: count, AMAZON_HUB_CODE: code}

    async def _amazon_otp(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> dict[str, Any]:
        """Find Amazon OTP code."""
        code = []
        today = _amazon_attr("get_today", get_today)().strftime("%d-%b-%Y")
        email_addresses_fn = _amazon_attr(
            "amazon_email_addresses", amazon_email_addresses
        )
        address_list = email_addresses_fn(fwds, domain)
        subject = _amazon_attr("AMAZON_OTP_SUBJECT", AMAZON_OTP_SUBJECT)
        regex = _amazon_attr("AMAZON_OTP_REGEX", AMAZON_OTP_REGEX)
        search_fn = _amazon_attr("email_search", email_search)
        fetch_fn = _amazon_attr("email_fetch", email_fetch)
        (server_response, data) = await search_fn(
            account,
            address_list,
            today,
            subject,
            body=regex,
            header=forwarding_header,
        )
        if server_response == "OK" and data[0] is not None:
            email_mod = _amazon_attr("email", email)
            for num in data[0].split():
                if cache:
                    msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                else:
                    msg_parts = (await fetch_fn(account, num, "(RFC822)"))[1]
                for response_part in msg_parts:
                    if isinstance(response_part, (bytes, bytearray)):
                        msg = email_mod.message_from_bytes(response_part)
                        body = get_email_body(msg)
                        if (found := re.compile(regex).search(body)) is not None:
                            code.append(found.group(2))
        return {AMAZON_OTP: len(code), AMAZON_OTP_CODE: code}

    async def _amazon_exception(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> dict[str, Any]:
        """Find Amazon exception emails."""
        count = 0
        orders = []
        today = _amazon_attr("get_today", get_today)().strftime("%d-%b-%Y")
        email_addresses_fn = _amazon_attr(
            "amazon_email_addresses", amazon_email_addresses
        )
        address_list = email_addresses_fn(fwds, domain)
        subject = _amazon_attr("AMAZON_EXCEPTION_SUBJECT", AMAZON_EXCEPTION_SUBJECT)
        search_fn = _amazon_attr("email_search", email_search)
        fetch_fn = _amazon_attr("email_fetch", email_fetch)
        (server_response, data) = await search_fn(
            account=account,
            address=address_list,
            date=today,
            subject=subject,
            header=forwarding_header,
        )
        if server_response == "OK" and data[0] is not None:
            order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")
            for num in data[0].split():
                if cache:
                    msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                else:
                    msg_parts = (await fetch_fn(account, num, "(RFC822)"))[1]

                if extracted_orders := _extract_exception_from_parts(
                    msg_parts, order_pattern
                ):
                    count += 1
                    orders.extend(extracted_orders)
        return {AMAZON_EXCEPTION: count, AMAZON_EXCEPTION_ORDER: orders}
