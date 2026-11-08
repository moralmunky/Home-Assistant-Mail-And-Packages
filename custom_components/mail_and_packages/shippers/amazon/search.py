"""Search and email processing mixin for Amazon shipper."""

from __future__ import annotations

import datetime as dt
import email
import logging
import re
from email.utils import parsedate_to_datetime
from typing import Any

import dateparser
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    AMAZON_ATTEMPTED,
    AMAZON_ATTEMPTED_COUNT,
    AMAZON_ATTEMPTED_ORDER,
    AMAZON_ATTEMPTED_SUBJECT,
    AMAZON_ATTEMPTED_SUBJECT_LIST,
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
    AMAZON_OTP_DELIVERY_DATE,
    AMAZON_OTP_DELIVERY_WINDOW,
    AMAZON_OTP_DELIVERY_WINDOW_END,
    AMAZON_OTP_DELIVERY_WINDOW_REGEX,
    AMAZON_OTP_DELIVERY_WINDOW_START,
    AMAZON_OTP_ORDER,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    AMAZON_PATTERN,
    DEFAULT_AMAZON_DAYS,
)
from custom_components.mail_and_packages.utils.amazon import (
    amazon_email_addresses,
    extract_amazon_order_details,
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

from .helpers import (
    _calculate_delivering_count,
    _calculate_final_count,
    _extract_attempted_from_parts,
    _extract_exception_from_parts,
    _extract_first_order_id,
    _extract_hub_code_from_parts,
    _iter_visible_texts,
)
from .image import AmazonImageMixin

_LOGGER = logging.getLogger(__name__)


def _extract_amazon_otp_code(msg: email.message.Message, regex: str) -> str | None:
    """Return an OTP found in the visible plain-text or HTML message body."""
    pattern = re.compile(regex)

    for body in _iter_visible_texts(msg):
        if found := pattern.search(body):
            return found.group(found.lastindex or 0)

    return None


def _format_window_time(value: str) -> str | None:
    """Format a window time such as '1 PM' or '1:30 PM' as 24-hour HH:MM."""
    normalized = " ".join(value.upper().split())
    for fmt in ("%I %p", "%I:%M %p"):
        try:
            return dt.datetime.strptime(normalized, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None


def _extract_window_details(body: str, details: dict[str, str]) -> None:
    """Add the delivery window from a body text to the details, if any."""
    if AMAZON_OTP_DELIVERY_WINDOW in details:
        return
    if found := re.compile(AMAZON_OTP_DELIVERY_WINDOW_REGEX).search(body):
        start_raw = " ".join(found.group(1).upper().split())
        end_raw = " ".join(found.group(2).upper().split())
        details[AMAZON_OTP_DELIVERY_WINDOW] = f"{start_raw} - {end_raw}"
        if start := _format_window_time(start_raw):
            details[AMAZON_OTP_DELIVERY_WINDOW_START] = start
        if end := _format_window_time(end_raw):
            details[AMAZON_OTP_DELIVERY_WINDOW_END] = end


def _extract_amazon_otp_details(msg: email.message.Message) -> dict[str, str]:
    """Return delivery details found alongside an Amazon OTP.

    Extracts the delivery window (for example "Arriving today 1 PM - 4 PM"
    in an out-for-delivery email), the order number, and the delivery
    date (the date of the email, which is the delivery day for these
    same-day notices). Only values actually found are returned.
    """
    details: dict[str, str] = {}
    order_pattern = re.compile(AMAZON_PATTERN)

    for body in _iter_visible_texts(msg):
        _extract_window_details(body, details)
        if AMAZON_OTP_ORDER not in details:
            if order := order_pattern.search(body):
                details[AMAZON_OTP_ORDER] = order.group(0)
        if AMAZON_OTP_DELIVERY_WINDOW in details and AMAZON_OTP_ORDER in details:
            break

    date_str = msg.get("Date")
    if date_str:
        try:
            parsed = parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            details[AMAZON_OTP_DELIVERY_DATE] = parsed.date().isoformat()

    return details


class AmazonSearchMixin(AmazonImageMixin):
    """Mixin providing search, email processing, and image handling for Amazon shipper."""

    hass: Any
    config: dict[str, Any]
    _parsed_context_cache: (
        dict[tuple[int, tuple[str, ...] | None, int, str | None, str], dict[str, Any]]
        | None
    ) = None

    async def _get_amazon_context(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        days: int = DEFAULT_AMAZON_DAYS,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> dict[str, Any]:
        """Build or return the memoized Amazon email parsing context."""
        cache_key = (
            id(account),
            tuple(fwds) if fwds is not None else None,
            days,
            domain,
            forwarding_header,
        )
        if (
            self._parsed_context_cache is not None
            and cache_key in self._parsed_context_cache
        ):
            return self._parsed_context_cache[cache_key]

        today_date = get_today()
        address_list = amazon_email_addresses(fwds, domain)
        unique_emails = await search_amazon_emails(
            account, address_list, days, domain, cache, forwarding_header
        )
        order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

        context: dict[str, Any] = {
            "today": today_date,
            "packages_arriving_today": {},
            "packages_delivering_today": {},
            "delivered_packages": {},
            "amazon_delivered": [],
            "deliveries_today": [],
            "delivering_today": [],
            "all_shipped_orders": set(),
            "order_details": {},
            "order_pattern": order_pattern,
        }

        for email_id in unique_emails:
            await self._process_amazon_email(account, email_id, context, cache)

        if self._parsed_context_cache is not None:
            self._parsed_context_cache[cache_key] = context

        return context

    async def _parse_amazon_emails(
        self,
        account: IMAP4_SSL,
        param: str,
        fwds: list[str] | None = None,
        days: int = DEFAULT_AMAZON_DAYS,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> Any:
        """Parse Amazon emails for delivery date and order number."""
        context = await self._get_amazon_context(
            account, fwds, days, domain, cache, forwarding_header
        )

        if param == "delivering":
            orders = list(context["packages_delivering_today"].keys())
            return _calculate_delivering_count(context), orders

        if param == "delivered":
            return list(context["amazon_delivered"])

        final_count = _calculate_final_count(context)

        if param == "count":
            return final_count

        orders = [
            order_id
            for order_id in context["all_shipped_orders"]
            if context["packages_arriving_today"].get(order_id, 0)
            > context["delivered_packages"].get(order_id, 0)
            or (
                context["packages_arriving_today"].get(order_id, 0) == 0
                and context["delivered_packages"].get(order_id, 0) == 0
            )
        ]

        if param == "details":
            return {
                order_id: context["order_details"][order_id]
                for order_id in orders
                if order_id in context["order_details"]
            }

        return orders

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

            await self._handle_shipping_email(
                email_subject, email_msg, email_date, ctx, msg=msg
            )

    async def _parse_email_date(
        self,
        msg: email.message.Message,
    ) -> dt.date | None:
        """Parse the date from an email message."""
        date_str = msg.get("Date")
        if not date_str:
            return None
        parsed = await self.hass.async_add_executor_job(dateparser.parse, date_str)
        if not parsed:
            return None
        return parsed.astimezone().date() if parsed.tzinfo else parsed.date()

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
        date: dt.date | None,
        ctx: dict,
        msg: email.message.Message | None = None,
    ):
        """Handle an Amazon 'shipping' or 'arriving' email."""
        order_id = _extract_first_order_id(subject, body, ctx["order_pattern"])
        if order_id:
            ctx["all_shipped_orders"].add(order_id)
            if details := extract_amazon_order_details(subject, body, msg):
                ctx["order_details"].setdefault(order_id, details)

        delivering_subjects = AMAZON_DELIVERING_SUBJECT
        is_delivering = any(s.lower() in subject.lower() for s in delivering_subjects)

        parsed_arrival = None
        if body:
            parsed_arrival = await parse_amazon_arrival_date(self.hass, body, date)

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
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, domain)
        subjects = AMAZON_HUB_SUBJECT
        for search_subject in subjects:
            (server_response, data) = await email_search(
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
                    msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]

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
        details: dict[str, list[str]] = {}
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, domain)
        subject = AMAZON_OTP_SUBJECT
        regex = AMAZON_OTP_REGEX
        (server_response, data) = await email_search(
            account,
            address_list,
            today,
            subject,
            body=regex,
            header=forwarding_header,
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
                        if otp_code := _extract_amazon_otp_code(msg, regex):
                            if otp_code not in code:
                                code.append(otp_code)
                                for key, value in _extract_amazon_otp_details(
                                    msg
                                ).items():
                                    details.setdefault(key, []).append(value)
        result: dict[str, Any] = {AMAZON_OTP: len(code), AMAZON_OTP_CODE: code}
        result.update(details)
        return result

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
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, domain)
        subject = AMAZON_EXCEPTION_SUBJECT
        (server_response, data) = await email_search(
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
                    msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]

                if extracted_orders := _extract_exception_from_parts(
                    msg_parts, order_pattern
                ):
                    count += 1
                    orders.extend(extracted_orders)
        return {AMAZON_EXCEPTION: count, AMAZON_EXCEPTION_ORDER: orders}

    async def _amazon_attempted(
        self,
        account: IMAP4_SSL,
        fwds: list[str] | None = None,
        domain: str | None = None,
        cache: EmailCache | None = None,
        forwarding_header: str = "",
    ) -> dict[str, Any]:
        """Find Amazon delivery attempted emails.

        Mirrors _amazon_exception: a standalone search that does not
        take part in the amazon_packages counting context, so an attempt
        never inflates the package counts. Orders are deduplicated
        preserving order, matching the delivered extraction which checks
        the subject and falls back to the body (both paths are searched
        here, like the exception extraction).
        """
        count = 0
        orders: list[str] = []
        subjects: list[str] = []
        today = get_today().strftime("%d-%b-%Y")
        address_list = amazon_email_addresses(fwds, domain)
        subject = AMAZON_ATTEMPTED_SUBJECT
        (server_response, data) = await email_search(
            account=account,
            address=address_list,
            date=today,
            subject=subject,
            header=forwarding_header,
        )
        if server_response == "OK" and data[0] is not None:
            order_pattern = re.compile(AMAZON_PATTERN)
            for num in data[0].split():
                if cache:
                    msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
                else:
                    msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]

                if extracted := _extract_attempted_from_parts(msg_parts, order_pattern):
                    extracted_orders, email_subject = extracted
                    count += 1
                    for order in extracted_orders:
                        if order not in orders:
                            orders.append(order)
                    if email_subject and email_subject not in subjects:
                        subjects.append(email_subject)
        return {
            AMAZON_ATTEMPTED: count,
            AMAZON_ATTEMPTED_COUNT: count,
            AMAZON_ATTEMPTED_ORDER: orders,
            AMAZON_ATTEMPTED_SUBJECT_LIST: subjects,
        }
