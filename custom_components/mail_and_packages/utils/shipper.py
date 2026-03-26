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
    sdata: Any, account: type[IMAP4_SSL], the_format: str | None = None
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
            if isinstance(response_part, (bytes, bytearray)):
                msg = email.message_from_bytes(response_part)
                _LOGGER.debug("Checking message subject...")

                # Search subject for a tracking number
                email_subject = msg["subject"]
                if email_subject:
                    email_subject = str(email_subject)
                    if (found := pattern.findall(email_subject)) and len(found) > 0:
                        _LOGGER.debug(
                            "Found tracking number in email subject: %s", found[0]
                        )
                        if found[0] not in tracking:
                            tracking.append(found[0])
                        continue

                # Search in email body for tracking number
                _LOGGER.debug("Checking message body using %s ...", the_format)

                # Special handling for UPS tracking - use simplified approach
                if the_format == "1Z?[0-9A-Z]{16}":
                    try:
                        # Get the raw email content
                        email_content = str(response_part, "utf-8", errors="ignore")

                        # Search for tracking number in the entire email content
                        if (found := pattern.findall(email_content)) and len(found) > 0:
                            _LOGGER.debug(
                                "Found tracking number in email: %s", found[0]
                            )
                            if found[0] not in tracking:
                                tracking.append(found[0])
                    except (TypeError, UnicodeError) as err:
                        _LOGGER.debug("Error processing email content: %s", err)
                else:
                    # Original logic for all other tracking types
                    for part in msg.walk():
                        if part.get_content_type() not in ["text/html", "text/plain"]:
                            continue
                        email_msg = part.get_payload(decode=True)
                        email_msg = email_msg.decode("utf-8", "ignore")
                        if (found := pattern.findall(email_msg)) and len(found) > 0:
                            # DHL is special
                            if " " in the_format:
                                found[0] = found[0].split(" ")[1]

                            _LOGGER.debug(
                                "Found tracking number in email body: %s", found[0]
                            )
                            if found[0] not in tracking:
                                tracking.append(found[0])
                            continue

    return tracking


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
            "%s - Writing %d bytes to file: %s", shipper_name, len(image_data), path
        )
        with Path(path).open("wb") as the_file:
            the_file.write(image_data)

    except OSError as err:
        _LOGGER.error(
            "Error saving %s delivery photo to %s: %s", shipper_name, path, err
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

    # Check for both bytes and bytearray
    if isinstance(sdata, (bytes, bytearray)):
        msg = email.message_from_bytes(sdata)
    else:
        msg = email.message_from_string(sdata)

    normalized_image_path = image_path.rstrip("/") + "/"
    shipper_path = f"{normalized_image_path}{shipper_name}/"
    content_type = f"image/{image_type}"
    base64_pattern = rf"data:image/{image_type};base64,((?:[A-Za-z0-9+/]{{4}})*(?:[A-Za-z0-9+/]{{2}}==|[A-Za-z0-9+/]{{3}}=)?)"

    # First pass: look for CID embedded images (if CID name provided)
    cid_images = {}
    if cid_name:
        for part in msg.walk():
            if part.get_content_type() == content_type:
                content_id = part.get("Content-ID")
                if content_id:
                    cid = content_id.strip("<>")
                    cid_images[cid] = part.get_payload(decode=True)

    # Second pass: look for HTML content with CID references or base64
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            part_payload = part.get_payload(decode=True)
            if isinstance(part_payload, bytes):
                part_content = part_payload.decode("utf-8", "ignore")
            else:
                part_content = str(part_payload)

            # Check for CID reference
            if cid_name and cid_name in part_content:
                if cid_name in cid_images:
                    try:
                        full_path = shipper_path + image_name
                        image_data_bytes = cid_images[cid_name]
                        if save_image_data_to_disk(
                            shipper_name, full_path, image_data_bytes
                        ):
                            return True
                    except (OSError, ValueError, TypeError) as err:
                        _LOGGER.error(
                            "Error saving %s delivery photo from CID: %s",
                            shipper_name,
                            err,
                        )
                        return False

            # Look for base64 encoded images
            matches = re.findall(base64_pattern, part_content)
            if matches:
                try:
                    base64_data = matches[0].replace(" ", "").replace("=3D", "=")
                    full_path = shipper_path + image_name
                    image_data_bytes = base64.b64decode(base64_data)
                    if save_image_data_to_disk(
                        shipper_name, full_path, image_data_bytes
                    ):
                        return True
                except (OSError, ValueError, TypeError) as err:
                    _LOGGER.error(
                        "Error saving %s delivery photo from base64: %s",
                        shipper_name,
                        err,
                    )
                    return False

    # Third pass: look for attachments
    for part in msg.walk():
        if part.get_content_type() == content_type:
            filename = part.get_filename()
            if filename:
                if attachment_filename_pattern:
                    if attachment_filename_pattern.lower() not in filename.lower():
                        continue
                try:
                    full_path = shipper_path + image_name
                    image_data_bytes = part.get_payload(decode=True)
                    if save_image_data_to_disk(
                        shipper_name, full_path, image_data_bytes
                    ):
                        return True
                except (OSError, ValueError, TypeError) as err:
                    _LOGGER.error(
                        "Error saving %s delivery photo to %s: %s",
                        shipper_name,
                        shipper_path + image_name,
                        err,
                    )
                    return False

    return False
