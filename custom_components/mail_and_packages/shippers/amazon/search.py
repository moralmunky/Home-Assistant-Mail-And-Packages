"""Search and email processing mixin for Amazon shipper."""

from __future__ import annotations

import datetime as dt
import email
import logging
import re
from html.parser import HTMLParser
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
    _extract_exception_from_parts,
    _extract_first_order_id,
    _extract_hub_code_from_parts,
)
from .image import AmazonImageMixin

_LOGGER = logging.getLogger(__name__)


class _AmazonOTPHTMLParser(HTMLParser):
    """Extract visible text from an Amazon HTML email."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Ignore CSS and scripts, which may contain unrelated six-digit values."""
        if tag in ("style", "script"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Resume collecting visible text after CSS or scripts."""
        if tag in ("style", "script") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        """Collect visible text nodes."""
        if not self._skip_depth and data.strip():
            self.text_parts.append(data)


def _extract_amazon_otp_code(msg: email.message.Message, regex: str) -> str | None:
    """Return an OTP found in the visible plain-text or HTML message body."""
    pattern = re.compile(regex)

    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue

        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue

        charset = part.get_content_charset() or "utf-8"
        try:
            body = payload.decode(charset, "ignore")
        except LookupError:
            body = payload.decode("utf-8", "ignore")

        if content_type == "text/html":
            parser = _AmazonOTPHTMLParser()
            parser.feed(body)
            body = "\n".join(parser.text_parts)

        if found := pattern.search(body):
            return found.group(found.lastindex or 0)

    return None


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
                            code.append(otp_code)
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
