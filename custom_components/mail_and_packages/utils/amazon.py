"""Amazon specific utilities."""

from __future__ import annotations

import datetime
import email
import logging
import quopri
import re
from email.header import decode_header
from functools import partial
from pathlib import Path
from typing import Any

import aiohttp
import dateparser
from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_DOMAINS,
    AMAZON_EMAIL,
    AMAZON_IMG_LIST,
    AMAZON_IMG_PATTERN,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_SHIPMENT_SUBJECT,
    AMAZON_SHIPMENT_TRACKING,
    AMAZON_TIME_PATTERN,
    AMAZON_TIME_PATTERN_END,
    AMAZON_TIME_PATTERN_REGEX,
    DEFAULT_AMAZON_DAYS,
)
from custom_components.mail_and_packages.utils.date import get_today
from custom_components.mail_and_packages.utils.image import io_save_file
from custom_components.mail_and_packages.utils.imap import email_fetch, email_search

_LOGGER = logging.getLogger(__name__)


def get_decoded_subject(msg: email.message.Message) -> str:
    """Decode email subject."""
    header_val = msg["subject"]
    if not header_val:
        return ""
    decoded = decode_header(header_val)[0]
    subject_bytes, encoding = decoded
    if encoding:
        try:
            if isinstance(subject_bytes, bytes):
                return subject_bytes.decode(encoding, "ignore")
            return str(subject_bytes)
        except (LookupError, UnicodeError):
            pass
    if isinstance(subject_bytes, bytes):
        return subject_bytes.decode("utf-8", "ignore")
    return str(subject_bytes)


def get_email_body(msg: email.message.Message) -> str:
    """Extract and decode the email body safely."""
    try:
        if msg.is_multipart():
            payload = msg.get_payload(0)
            if isinstance(payload, email.message.Message):
                payload = payload.get_payload()
            email_msg = quopri.decodestring(str(payload))
        else:
            email_msg = quopri.decodestring(str(msg.get_payload()))
        return email_msg.decode("utf-8", "ignore")
    except (ValueError, TypeError, IndexError) as err:
        _LOGGER.debug("Problem decoding email message: %s", err)
        return ""


def extract_order_numbers(text: str, pattern: re.Pattern | str) -> list[str]:
    """Extract order numbers from text."""
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    return pattern.findall(text)


async def parse_amazon_arrival_date(
    hass: Any, email_msg: str, email_date: datetime.date
) -> datetime.date | None:
    """Determine arrival date from email."""
    today_date = get_today()
    for search in AMAZON_TIME_PATTERN:
        if search not in email_msg:
            continue

        start = email_msg.find(search) + len(search)
        chunk = email_msg[start : start + 50]

        dateobj = await hass.async_add_executor_job(
            partial(
                dateparser.parse,
                chunk,
                settings={
                    "PREFER_DATES_FROM": "future",
                    "RELATIVE_BASE": datetime.datetime.combine(
                        email_date or today_date, datetime.time()
                    ),
                    "RETURN_AS_TIMEZONE_AWARE": False,
                },
            )
        )
        if dateobj:
            return dateobj.date()
    return None


def amazon_email_addresses(
    fwds: list[str] | str | None = None, domain: str | None = None
) -> list[str]:
    """Generate Amazon email addresses."""
    if isinstance(fwds, str):
        fwds = [fwds]
    elif not isinstance(fwds, (list, tuple)):
        fwds = None

    if domain is None:
        domain = "amazon.com"

    # Use both AMAZON_EMAIL and AMAZON_SHIPMENT_TRACKING for prefixes
    prefixes = list(AMAZON_EMAIL)
    for p in AMAZON_SHIPMENT_TRACKING:
        if f"{p}@" not in prefixes:
            prefixes.append(f"{p}@")

    value = [f"{e}{domain}" for e in prefixes]
    if fwds:
        for fwd in fwds:
            if any(f in fwd for f in AMAZON_DOMAINS):
                value.append(fwd)
            else:
                value.extend(f"{e}{fwd}" for e in prefixes)
    return value


async def search_amazon_emails(
    account: IMAP4_SSL, address_list: list[str], days: int
) -> list[bytes]:
    """Search for Amazon emails."""
    if not isinstance(days, int):
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = DEFAULT_AMAZON_DAYS

    past_date = get_today() - datetime.timedelta(days=days)
    tfmt = past_date.strftime("%d-%b-%Y")
    amazon_subjects = (
        AMAZON_DELIVERED_SUBJECT + AMAZON_SHIPMENT_SUBJECT + AMAZON_ORDERED_SUBJECT
    )
    all_emails = []
    for subject in amazon_subjects:
        (server_response, sdata) = await email_search(
            account, address_list, tfmt, subject
        )
        if server_response == "OK" and sdata[0] is not None:
            all_emails.extend(sdata[0].split())

    unique_emails = []
    for email_id in all_emails:
        if email_id not in unique_emails:
            unique_emails.append(email_id)
    return unique_emails


async def download_amazon_img(
    img_url: str, img_path: str, img_name: str, hass: Any
) -> None:
    """Download image from url."""
    img_path = Path(img_path) / "amazon"
    filepath = img_path / img_name
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(img_url.replace("&amp;", "&")) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "image" in content_type:
                        data = await resp.read()
                        await hass.async_add_executor_job(io_save_file, filepath, data)
        except aiohttp.ClientError as err:
            _LOGGER.error("Problem downloading file: %s", err)


async def get_amazon_image_url(
    sdata: Any,
    account: IMAP4_SSL,
) -> str | None:
    """Find Amazon delivery image URL."""
    mail_list = sdata.split()
    pattern = re.compile(rf"{AMAZON_IMG_PATTERN}")
    for i in mail_list:
        data = (await email_fetch(account, i, "(RFC822)"))[1]
        for response_part in data:
            if isinstance(response_part, (bytes, bytearray)):
                msg = email.message_from_bytes(response_part)
                for part in msg.walk():
                    if part.get_content_type() != "text/html":
                        continue
                    part_payload = part.get_payload(decode=True)
                    part_content = part_payload.decode("utf-8", "ignore")
                    found = pattern.findall(part_content)
                    for url in found:
                        if url[1] not in AMAZON_IMG_LIST:
                            continue
                        return url[0] + url[1] + url[2]
    return None


def _extract_hub_code(
    body: str, hub_pattern: str, subject: str, subject_pattern: str
) -> str:
    """Extract Amazon Hub code from email body or subject."""
    # Check subject first
    if (found := re.compile(subject_pattern).search(subject)) is not None:
        return found.group(3)

    # Check body
    if (found := re.compile(hub_pattern).search(body)) is not None:
        return found.group(2)
    return ""


def amazon_date_search(email_msg: str, patterns: list[str] | None = None) -> int:
    """Search for a date pattern in an email message and return its index."""
    if patterns is None:
        patterns = AMAZON_TIME_PATTERN_END

    for pattern in patterns:
        if (index := email_msg.find(pattern)) != -1:
            return index
    return -1


def amazon_date_regex(email_msg: str, patterns: list[str] | None = None) -> str | None:
    """Search for a date pattern using regex and return the first capture group."""
    if patterns is None:
        patterns = AMAZON_TIME_PATTERN_REGEX

    for pattern in patterns:
        if (found := re.compile(pattern).search(email_msg)) is not None:
            if found.groups():
                return found.group(1)
    return None
