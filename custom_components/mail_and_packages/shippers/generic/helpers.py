"""Helper functions and data structures for generic shipper."""

from __future__ import annotations

import email
import logging
import re
import sys
from dataclasses import dataclass
from email.header import decode_header
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio
from aioimaplib import IMAP4_SSL
from homeassistant.core import HomeAssistant

from custom_components.mail_and_packages.const import (
    AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
    ATTR_BODY,
    ATTR_BODY_COUNT,
    ATTR_PATTERN,
    CAMERA_DATA,
    CAMERA_EXTRACTION_CONFIG,
    MARKETPLACE_CARRIER_TRACKING,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.email import find_text, find_text_matches
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_fetch_headers,
)
from custom_components.mail_and_packages.utils.shipper import (
    generic_delivery_image_extraction,
    get_tracking,
)

_LOGGER = logging.getLogger(__name__)


def _generic_attr(name: str, default: Any = None) -> Any:
    """Dynamically get an attribute from the generic module if available."""
    mod = sys.modules.get("custom_components.mail_and_packages.shippers.generic")
    return getattr(mod, name, default) if mod is not None else default


@dataclass
class SearchContext:
    """Context for generic shipper email search and processing."""

    sensor_type: str
    config: dict[str, Any]
    shipper_cfg: dict[str, Any] | None
    result: dict[str, Any]
    cache: EmailCache | None = None
    forwarding_header: str = ""


def _find_carrier_number(msg_parts: list, carrier_re: re.Pattern) -> str | None:
    """Return the first carrier tracking number found in an email's text parts."""
    email_mod = _generic_attr("email", email)
    for response_part in msg_parts:
        if not isinstance(response_part, (bytes, bytearray)):
            continue
        msg = email_mod.message_from_bytes(response_part)
        for part in msg.walk():
            if part.get_content_type() not in ("text/plain", "text/html"):
                continue
            try:
                text = part.get_payload(decode=True).decode("utf-8", "ignore")
            except (AttributeError, ValueError):
                continue
            if found := carrier_re.search(text):
                return found.group(1)
    return None


def _decode_subject(header_part: bytes | bytearray) -> str | None:
    """Decode MIME encoded subject from email header part."""
    email_mod = _generic_attr("email", email)
    msg = email_mod.message_from_bytes(header_part)
    header_val = msg.get("subject")
    if not header_val:
        return None

    decoded_parts = []
    decoder = _generic_attr("decode_header", decode_header)
    for subject_bytes, encoding in decoder(header_val):
        if encoding:
            try:
                if isinstance(subject_bytes, bytes):
                    decoded_parts.append(subject_bytes.decode(encoding, "ignore"))
                    continue
                decoded_parts.append(str(subject_bytes))
                continue
            except (LookupError, UnicodeError):
                pass

        if isinstance(subject_bytes, bytes):
            decoded_parts.append(subject_bytes.decode("utf-8", "ignore"))
        else:
            decoded_parts.append(str(subject_bytes))

    return " ".join("".join(decoded_parts).split())


def _extract_subject_from_headers(
    header_data: list[Any],
    sensor_type: str,
    eid: bytes,
    expected_subjects_lower: list[str],
) -> bool:
    """Check if any header part matches the expected subjects."""
    for part in header_data:
        if not isinstance(part, (bytes, bytearray)):
            continue
        subject = _decode_subject(part)
        if not subject:
            continue

        _LOGGER.debug(
            "Matched email for %s (ID %s): %s",
            sensor_type,
            eid.decode() if isinstance(eid, bytes) else eid,
            subject,
        )
        subject_lower = subject.lower()
        if any(expected in subject_lower for expected in expected_subjects_lower):
            return True
    return False


async def _verify_matched_subjects(
    account: IMAP4_SSL,
    email_ids: list[bytes],
    sensor_type: str,
    expected_subjects: list[str],
    shipper_name: str,
    cache: EmailCache | None = None,
) -> list[bytes]:
    """Verify the subject of each matched email locally and log for debugging."""
    if not expected_subjects:
        return email_ids

    verified_ids = []
    expected_subjects_lower = [s.lower() for s in expected_subjects]

    for eid in email_ids:
        try:
            if cache:
                header_data = (
                    await cache.fetch(
                        eid, "(BODY[HEADER.FIELDS (SUBJECT)])", shipper=shipper_name
                    )
                )[1]
            else:
                fetch_headers = _generic_attr(
                    "email_fetch_headers", email_fetch_headers
                )
                header_data = (await fetch_headers(account, eid))[1]

            if _extract_subject_from_headers(
                header_data, sensor_type, eid, expected_subjects_lower
            ):
                verified_ids.append(eid)
            else:
                _LOGGER.debug(
                    "Email ID %s rejected for %s: Subject did not match any expected subjects.",
                    eid.decode() if isinstance(eid, bytes) else eid,
                    sensor_type,
                )
        except (OSError, AttributeError) as err:
            _LOGGER.debug("Could not fetch subject for email %s: %s", eid, err)

    return verified_ids


def _filter_unique_ids(email_ids: list[bytes], unique_email_ids: set) -> list[bytes]:
    """Filter out already processed email IDs."""
    new_ids = []
    for eid in email_ids:
        eid_str = eid.decode() if isinstance(eid, bytes) else str(eid)
        if eid_str not in unique_email_ids:
            unique_email_ids.add(eid_str)
            new_ids.append(eid)
    return new_ids


async def _setup_image_extraction(
    hass: HomeAssistant,
    config: dict[str, Any],
    sensor_type: str,
    image_path: str,
) -> dict | None:
    """Set up image extraction configuration."""
    if not sensor_type.endswith("_delivered"):
        return None

    shipper_name = sensor_type.replace("_delivered", "")
    camera_key = f"{shipper_name}_camera"
    if camera_key not in CAMERA_DATA or camera_key in ("usps_camera", "generic_camera"):
        return None

    extraction_config = CAMERA_EXTRACTION_CONFIG.get(shipper_name, {})
    absolute_image_path = image_path.rstrip("/") + "/"

    def _create_dir() -> None:
        path_cls = _generic_attr("Path", Path)
        path = path_cls(absolute_image_path) / shipper_name
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

    await hass.async_add_executor_job(_create_dir)

    return {
        "name": shipper_name,
        "image_path": absolute_image_path,
        "image_name": config.get(f"{shipper_name}_image")
        or f"{shipper_name}_delivery.jpg",
        "image_type": extraction_config.get("image_type", "jpeg"),
        "cid_name": extraction_config.get("cid_name"),
        "pattern": extraction_config.get("attachment_filename_pattern"),
    }


async def _copy_generic_placeholder(
    hass: HomeAssistant,
    shipper_cfg: dict[str, Any],
) -> None:
    """Copy the generic placeholder for the shipper."""
    shipper_name = shipper_cfg["name"]
    base_dir = Path(__file__).parents[2]
    placeholder = base_dir / f"no_deliveries_{shipper_name}.jpg"
    if not await anyio.Path(placeholder).exists():
        placeholder = base_dir / "mail_none.gif"

    target = Path(shipper_cfg["image_path"]) / shipper_name / shipper_cfg["image_name"]
    _LOGGER.debug(
        "No %s images found in emails, using placeholder: %s",
        shipper_name,
        placeholder.name,
    )
    try:
        copier = _generic_attr("copyfile", copyfile)
        await hass.async_add_executor_job(copier, str(placeholder), str(target))
    except OSError as err:
        _LOGGER.error("Error attempting to copy placeholder: %s", err)


async def _process_tracking_numbers(
    sensor_type: str,
    found_data: list,
    account: IMAP4_SSL,
    cache: EmailCache | None = None,
) -> list:
    """Process tracking numbers for the sensor."""
    tracking_key = f"{'_'.join(sensor_type.split('_')[:-1])}_tracking"
    if tracking_key not in SENSOR_DATA or ATTR_PATTERN not in SENSOR_DATA[tracking_key]:
        return []

    pattern = SENSOR_DATA[tracking_key][ATTR_PATTERN][0]
    tracking_nums = []
    tracker = _generic_attr("get_tracking", get_tracking)
    for sdata in found_data:
        tracking_nums.extend(await tracker(sdata.decode(), account, pattern, cache))

    return list(dict.fromkeys(tracking_nums))


async def _collect_carrier_tracking(
    sensor_type: str,
    found_data: list,
    account: IMAP4_SSL,
    cache: EmailCache | None = None,
) -> dict[str, dict]:
    """Map marketplace tracking id -> embedded carrier tracking number."""
    prefix = "_".join(sensor_type.split("_")[:-1])
    pattern = MARKETPLACE_CARRIER_TRACKING.get(prefix)
    tracking_key = f"{prefix}_tracking"
    if (
        not pattern
        or not found_data
        or tracking_key not in SENSOR_DATA
        or ATTR_PATTERN not in SENSOR_DATA[tracking_key]
    ):
        return {}

    carrier_re = re.compile(pattern, re.IGNORECASE)
    id_pattern = SENSOR_DATA[tracking_key][ATTR_PATTERN][0]
    mapping: dict[str, str] = {}
    tracker = _generic_attr("get_tracking", get_tracking)
    fetcher = _generic_attr("email_fetch", email_fetch)
    for sdata in found_data:
        for eid in sdata.split():
            tracking = await tracker(
                eid.decode() if isinstance(eid, bytes) else str(eid),
                account,
                id_pattern,
                cache,
            )
            if not tracking:
                continue
            if cache:
                msg_parts = (await cache.fetch(eid, "(RFC822)"))[1]
            else:
                msg_parts = (await fetcher(account, eid, "(RFC822)"))[1]
            find_num = _generic_attr("_find_carrier_number", _find_carrier_number)
            if number := find_num(msg_parts, carrier_re):
                mapping.setdefault(tracking[0], number)
    if not mapping:
        return {}
    return {f"{prefix}_carrier_tracking": mapping}


async def _process_emails_by_type(
    account: IMAP4_SSL,
    config: dict,
    ids: list,
    current_count: int,
    cache: EmailCache | None = None,
) -> tuple[int, list]:
    """Process emails based on body search or just count."""
    if ATTR_BODY in config:
        body_count = config.get(ATTR_BODY_COUNT, False)
        mock_data = (b" ".join(ids),)
        matcher = _generic_attr("find_text_matches", find_text_matches)
        count, matched_ids = await matcher(
            mock_data,
            account,
            config[ATTR_BODY],
            body_count,
            cache,
        )
        return current_count + count, matched_ids
    return current_count + len(ids), list(ids)


async def _extract_images_for_shipper(
    hass: HomeAssistant,
    account: IMAP4_SSL,
    ids: list,
    s_config: dict,
    shipper_name: str,
    cache: EmailCache | None = None,
) -> bool:
    """Extract delivery images from emails."""
    image_found = False
    fetcher = _generic_attr("email_fetch", email_fetch)
    extractor = _generic_attr(
        "generic_delivery_image_extraction", generic_delivery_image_extraction
    )
    for eid in ids:
        if cache:
            msg_parts = (await cache.fetch(eid, "(RFC822)", shipper=shipper_name))[1]
        else:
            msg_parts = (await fetcher(account, eid, "(RFC822)"))[1]
        for response_part in msg_parts:
            if isinstance(response_part, (bytes, bytearray)):
                # Run sync extraction off event loop (file I/O & CPU parsing)
                if await hass.async_add_executor_job(
                    extractor,
                    response_part,
                    s_config["image_path"],
                    s_config["image_name"],
                    s_config["name"],
                    s_config["image_type"],
                    s_config["cid_name"],
                    s_config["pattern"],
                ):
                    _LOGGER.debug("Extracted image for %s", s_config["name"])
                    image_found = True
    return image_found


async def _check_amazon_mentions(
    account: IMAP4_SSL,
    ids: list,
    result: dict,
    cache: EmailCache | None = None,
) -> None:
    """Check for Amazon mentions in emails."""
    mock_data = (b" ".join(ids),)
    finder = _generic_attr("find_text", find_text)
    amazon_mentions = await finder(
        mock_data,
        account,
        AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
        False,
        cache,
    )
    if amazon_mentions > 0:
        result["amazon_delivered_by_others"] = (
            result.get("amazon_delivered_by_others", 0) + amazon_mentions
        )
