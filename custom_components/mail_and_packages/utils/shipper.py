"""Shipper utility functions for Mail and Packages."""

from __future__ import annotations

import base64
import email
import logging
import re
from pathlib import Path
from typing import Any

from aioimaplib import IMAP4_SSL

from .imap import email_fetch

_LOGGER = logging.getLogger(__name__)


async def get_tracking(
    sdata: Any,
    account: type[IMAP4_SSL],
    the_format: str | None = None,
) -> list:
    """Parse tracking numbers from email.

    Returns list of tracking numbers
    """
    tracking = []
    pattern = re.compile(rf"{the_format}")
    mail_list = sdata.split()
    _LOGGER.debug("Searching for tracking numbers in %s messages...", len(mail_list))

    for i in mail_list:
        data = (await email_fetch(account, i, "(RFC822)"))[1]
        for response_part in data:
            if not isinstance(response_part, (bytes, bytearray)):
                continue

            msg = email.message_from_bytes(response_part)

            # 1. Search subject
            if found := _find_tracking_in_subject(msg, pattern):
                if found not in tracking:
                    tracking.append(found)
                continue

            # 2. Search body
            if the_format == "1Z?[0-9A-Z]{16}":
                found = _find_ups_tracking_in_raw(response_part, pattern)
            else:
                found = _find_tracking_in_body(msg, pattern, the_format)

            if found and found not in tracking:
                tracking.append(found)

    return tracking


def _find_tracking_in_subject(
    msg: email.message.Message,
    pattern: re.Pattern,
) -> str | None:
    """Find tracking number in email subject."""
    email_subject = msg["subject"]
    if email_subject:
        email_subject = str(email_subject)
        if (found := pattern.findall(email_subject)) and len(found) > 0:
            _LOGGER.debug("Found tracking number in email subject: %s", found[0])
            return found[0]
    return None


def _find_ups_tracking_in_raw(
    response_part: bytes | bytearray,
    pattern: re.Pattern,
) -> str | None:
    """UPS specific tracking search in raw email bytes."""
    try:
        email_content = str(response_part, "utf-8", errors="ignore")
        if (found := pattern.findall(email_content)) and len(found) > 0:
            _LOGGER.debug("Found tracking number in email: %s", found[0])
            return found[0]
    except (TypeError, UnicodeError) as err:
        _LOGGER.debug("Error processing email content: %s", err)
    return None


def _find_tracking_in_body(
    msg: email.message.Message,
    pattern: re.Pattern,
    the_format: str,
) -> str | None:
    """Search for tracking number in email body parts."""
    for part in msg.walk():
        if part.get_content_type() not in ["text/html", "text/plain"]:
            continue
        email_msg = part.get_payload(decode=True)
        email_msg = email_msg.decode("utf-8", "ignore")
        if (found := pattern.findall(email_msg)) and len(found) > 0:
            tracking_num = found[0]
            # DHL is special
            if " " in the_format:
                tracking_num = tracking_num.split(" ")[1]

            _LOGGER.debug("Found tracking number in email body: %s", tracking_num)
            return tracking_num
    return None


def save_image_data_to_disk(shipper_name: str, path: str, image_data: bytes) -> bool:
    """Write image bytes to disk and verify."""
    try:
        # Ensure directory exists
        directory = Path(path).parent
        if not directory.is_dir():
            _LOGGER.debug("%s - Creating directory: %s", shipper_name, directory)
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                _LOGGER.error("Error creating directory: %s", err)
                return False

        _LOGGER.debug(
            "%s - Writing %d bytes to file: %s",
            shipper_name,
            len(image_data),
            path,
        )
        with Path(path).open("wb") as the_file:
            the_file.write(image_data)

    except OSError as err:
        _LOGGER.error(
            "Error saving %s delivery photo to %s: %s",
            shipper_name,
            path,
            err,
        )
        return False
    else:
        if Path(path).exists():
            return True

        _LOGGER.error(
            "%s - ERROR: File write reported success but file doesn't exist: %s",
            shipper_name,
            path,
        )
        return False


def generic_delivery_image_extraction(
    sdata: Any,
    image_path: str,
    image_name: str,
    shipper_name: str,
    image_type: str,
    cid_name: str | None = None,
    attachment_filename_pattern: str | None = None,
) -> bool:
    """Extract delivery photos from email."""
    _LOGGER.debug("Attempting to extract %s delivery photo", shipper_name)

    msg = (
        email.message_from_bytes(sdata)
        if isinstance(sdata, (bytes, bytearray))
        else email.message_from_string(sdata)
    )

    normalized_image_path = image_path.rstrip("/") + "/"
    shipper_path = f"{normalized_image_path}{shipper_name}/"
    full_path = shipper_path + image_name

    # Pass 1: CID search
    if cid_name and (
        found := _extract_from_cid(msg, cid_name, shipper_name, full_path, image_type)
    ):
        return found

    # Pass 2: HTML/Base64 search
    if found := _extract_from_html(msg, cid_name, shipper_name, full_path, image_type):
        return found

    # Pass 3: Attachment search
    return _extract_from_attachments(
        msg,
        attachment_filename_pattern,
        shipper_name,
        full_path,
        image_type,
    )


def _extract_from_cid(
    msg: email.message.Message,
    cid_name: str,
    shipper_name: str,
    full_path: str,
    image_type: str,
) -> bool:
    """Pass 1: Look for CID embedded images."""
    content_type = f"image/{image_type}"
    for part in msg.walk():
        if part.get_content_type() == content_type:
            content_id = part.get("Content-ID")
            if content_id and content_id.strip("<>") == cid_name:
                return save_image_data_to_disk(
                    shipper_name,
                    full_path,
                    part.get_payload(decode=True),
                )
    return False


def _extract_from_html(
    msg: email.message.Message,
    cid_name: str | None,
    shipper_name: str,
    full_path: str,
    image_type: str,
) -> bool:
    """Pass 2: Look for HTML content with CID references or base64."""
    base64_pattern = rf"data:image/{image_type};base64,((?:[A-Za-z0-9+/]{{4}})*(?:[A-Za-z0-9+/]{{2}}==|[A-Za-z0-9+/]{{3}}=)?)"

    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue

        payload = part.get_payload(decode=True)
        content = (
            payload.decode("utf-8", "ignore")
            if isinstance(payload, bytes)
            else str(payload)
        )

        # Base64 check
        if matches := re.findall(base64_pattern, content):
            try:
                base64_data = matches[0].replace(" ", "").replace("=3D", "=")
                return save_image_data_to_disk(
                    shipper_name,
                    full_path,
                    base64.b64decode(base64_data),
                )
            except (OSError, ValueError, TypeError) as err:
                _LOGGER.error(
                    "Error saving %s delivery photo from base64: %s",
                    shipper_name,
                    err,
                )
                return False

    return False


def _extract_from_attachments(
    msg: email.message.Message,
    pattern: str | None,
    shipper_name: str,
    full_path: str,
    image_type: str,
) -> bool:
    """Pass 3: Look for attachments."""
    content_type = f"image/{image_type}"
    for part in msg.walk():
        if part.get_content_type() == content_type:
            filename = part.get_filename()
            if not filename:
                continue
            if pattern and pattern.lower() not in filename.lower():
                continue

            try:
                return save_image_data_to_disk(
                    shipper_name,
                    full_path,
                    part.get_payload(decode=True),
                )
            except (OSError, ValueError, TypeError) as err:
                _LOGGER.error(
                    "Error saving %s delivery photo to %s: %s",
                    shipper_name,
                    full_path,
                    err,
                )
                return False
    return False
