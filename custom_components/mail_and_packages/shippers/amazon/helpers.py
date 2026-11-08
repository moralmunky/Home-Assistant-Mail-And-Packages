"""Helper functions for Amazon shipper email parsing and extraction."""

from __future__ import annotations

import email
import logging
import re
from html.parser import HTMLParser
from typing import Any

from custom_components.mail_and_packages import const
from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERING_SUBJECT,
    AMAZON_EXCEPTION_BODY,
    AMAZON_HUB_BODY,
    AMAZON_HUB_SUBJECT_SEARCH,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_SHIPMENT_SUBJECT,
)
from custom_components.mail_and_packages.utils.amazon import (
    _extract_hub_code,
    extract_order_numbers,
    get_decoded_subject,
    get_email_body,
)

_LOGGER = logging.getLogger(__name__)


class _AmazonVisibleTextParser(HTMLParser):
    """Extract visible text from an Amazon HTML email."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Ignore CSS and scripts, which may contain unrelated numbers."""
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


def _iter_visible_texts(msg: email.message.Message) -> list[str]:
    """Return the visible text of each plain-text or HTML message part."""
    texts = []
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
            parser = _AmazonVisibleTextParser()
            parser.feed(body)
            body = "\n".join(parser.text_parts)

        texts.append(body)
    return texts


def _extract_first_order_id(
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


def _calculate_final_count(ctx: dict) -> int:
    """Calculate the final count of packages arriving today."""
    deliveries_today = [
        item for item in ctx["deliveries_today"] if item not in ctx["amazon_delivered"]
    ]
    final_count = 0
    for order_id, arriving_count in ctx["packages_arriving_today"].items():
        delivered_count = ctx["delivered_packages"].get(order_id, 0)
        final_count += max(0, arriving_count - delivered_count)
    return final_count + len(deliveries_today)


def _calculate_delivering_count(ctx: dict) -> int:
    """Calculate packages currently out for delivery today."""
    delivering_today = [
        item for item in ctx["delivering_today"] if item not in ctx["amazon_delivered"]
    ]
    final_count = 0
    for order_id, delivering_count in ctx["packages_delivering_today"].items():
        delivered_count = ctx["delivered_packages"].get(order_id, 0)
        final_count += max(0, delivering_count - delivered_count)
    return final_count + len(delivering_today)


def _extract_amazon_image_urls(msg: email.message.Message) -> list[str]:
    """Extract image URLs from Amazon email body."""
    urls = []
    pattern = re.compile(rf"{const.AMAZON_IMG_PATTERN}")
    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue
        part_payload = part.get_payload(decode=True)
        if part_payload:
            part_content = part_payload.decode("utf-8", "ignore")
            found = pattern.findall(part_content)
            for url in found:
                if url[1] not in const.AMAZON_IMG_LIST:
                    continue
                full_url = url[0] + url[1] + url[2]
                if full_url not in urls:
                    urls.append(full_url)
    return urls


def _is_amazon_delivered(msg_data: list, subjects: list[str]) -> tuple[bool, list[str]]:
    """Verify if email is a delivered notification and return image URLs."""
    for response_part in msg_data:
        if not isinstance(response_part, (bytes, bytearray)):
            continue
        msg = email.message_from_bytes(response_part)
        subject = get_decoded_subject(msg)
        if not subject:
            continue

        # Check if subject contains any delivered keyword (case-insensitive)
        has_delivered = any(s.lower() in subject.lower() for s in subjects)
        # Check if subject contains ordered or shipped keywords (case-insensitive)
        has_ordered = any(s.lower() in subject.lower() for s in AMAZON_ORDERED_SUBJECT)
        has_shipped = any(s.lower() in subject.lower() for s in AMAZON_SHIPMENT_SUBJECT)
        has_delivering = any(
            s.lower() in subject.lower() for s in AMAZON_DELIVERING_SUBJECT
        )

        if has_delivered and not has_ordered and not has_shipped and not has_delivering:
            urls = _extract_amazon_image_urls(msg)
            return True, urls
    return False, []


def _extract_hub_code_from_parts(
    msg_parts: list[Any],
) -> str | None:
    """Extract hub code from email message parts."""
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
                return hub_code
    return None


def _extract_exception_from_parts(
    msg_parts: list[Any],
    order_pattern: re.Pattern[str],
) -> list[str] | None:
    """Extract matching order numbers if email matches exception body."""
    for response_part in msg_parts:
        if isinstance(response_part, (bytes, bytearray)):
            msg = email.message_from_bytes(response_part)
            body = get_email_body(msg)
            subject = get_decoded_subject(msg)
            if AMAZON_EXCEPTION_BODY in body:
                orders = []
                if found := order_pattern.findall(body):
                    orders.extend(found)
                if found := order_pattern.findall(subject):
                    orders.extend(found)
                return orders
    return None


def _extract_attempted_from_parts(
    msg_parts: list[Any],
    order_pattern: re.Pattern[str],
) -> tuple[list[str], str] | None:
    """Extract order numbers and subject from a delivery attempted email.

    The attempted search already matches on the "Delivery attempted"
    subject, so unlike the exception extraction there is no body phrase
    to confirm; an email only counts when at least one order number is
    found in its visible body text or subject. Only visible text is
    searched: numbers inside HTML style or script content are not
    orders (the same pollution #1556 removed from OTP extraction).
    """
    for response_part in msg_parts:
        if isinstance(response_part, (bytes, bytearray)):
            msg = email.message_from_bytes(response_part)
            subject = get_decoded_subject(msg)
            orders = []
            for body in _iter_visible_texts(msg):
                if found := order_pattern.findall(body):
                    orders.extend(found)
            if found := order_pattern.findall(subject):
                orders.extend(found)
            if orders:
                return orders, subject
    return None
