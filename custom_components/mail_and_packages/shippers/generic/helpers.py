"""Helper functions and data structures for generic shipper."""

from __future__ import annotations

import email
import logging
import re
from dataclasses import dataclass
from email.header import decode_header
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio
import dateparser
from aioimaplib import IMAP4_SSL, AioImapException
from homeassistant.core import HomeAssistant

from custom_components.mail_and_packages.const import (
    AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
    ASSET_ROOT,
    ATTR_BODY,
    ATTR_BODY_COUNT,
    ATTR_DELIVERY_DATE_PATTERN,
    ATTR_PATTERN,
    CAMERA_DATA,
    CAMERA_EXTRACTION_CONFIG,
    MARKETPLACE_CARRIER_TRACKING,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.date import get_today
from custom_components.mail_and_packages.utils.email import find_text, find_text_matches
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_fetch_headers,
    email_fetch_headers_batch,
)
from custom_components.mail_and_packages.utils.shipper import (
    generic_delivery_image_extraction,
    get_tracking,
)

_LOGGER = logging.getLogger(__name__)


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
    for response_part in msg_parts:
        if not isinstance(response_part, (bytes, bytearray)):
            continue
        msg = email.message_from_bytes(response_part)
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
    msg = email.message_from_bytes(header_part)
    header_val = msg.get("subject")
    if not header_val:
        return None

    decoded_parts = []
    for subject_bytes, encoding in decode_header(header_val):
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


def _parse_header_batch_lines(lines: list[Any]) -> dict[str, list[Any]]:
    """Map IMAP batch FETCH response lines back to their UID."""
    chunk_map: dict[str, list[Any]] = {}
    curr_uid: str | None = None
    for line in lines:
        if isinstance(line, tuple):
            prefix = line[0] if len(line) > 0 else b""
            prefix_str = (
                prefix.decode("ascii", "ignore")
                if isinstance(prefix, (bytes, bytearray))
                else str(prefix)
            )
            if uid_match := re.search(r"UID\s+(\d+)", prefix_str):
                curr_uid = uid_match.group(1)
            if curr_uid:
                chunk_map.setdefault(curr_uid, []).extend(line)
        elif isinstance(line, (bytes, bytearray)):
            line_str = line.decode("ascii", "ignore")
            if uid_match := re.search(r"UID\s+(\d+)", line_str):
                curr_uid = uid_match.group(1)
            if curr_uid:
                chunk_map.setdefault(curr_uid, []).append(line)
    return chunk_map


_MAX_HEADER_CHUNK = 50


async def _fetch_single_header(
    account: IMAP4_SSL,
    eid: bytes,
    shipper_name: str,
    cache: EmailCache | None,
) -> list[Any] | None:
    """Fetch header for a single email UID with error handling."""
    try:
        if cache:
            return (
                await cache.fetch(
                    eid, "(BODY[HEADER.FIELDS (SUBJECT)])", shipper=shipper_name
                )
            )[1]
        return (await email_fetch_headers(account, eid))[1]
    except (OSError, AttributeError) as err:
        _LOGGER.debug("Could not fetch subject for email %s: %s", eid, err)
        return None


async def _fetch_headers_scalar(
    account: IMAP4_SSL,
    chunk: list[bytes],
    shipper_name: str,
    cache: EmailCache | None,
) -> dict[bytes, list[Any]]:
    """Fetch email headers one-by-one as fallback."""
    headers = {}
    for eid in chunk:
        if hdata := await _fetch_single_header(account, eid, shipper_name, cache):
            headers[eid] = hdata
    return headers


async def _fetch_header_chunk(
    account: IMAP4_SSL,
    chunk: list[bytes],
    shipper_name: str,
    cache: EmailCache | None,
) -> dict[bytes, list[Any]]:
    """Fetch a chunk of email headers using batch fetch with scalar fallback."""
    if len(chunk) == 1:
        eid = chunk[0]
        header_data = await _fetch_single_header(account, eid, shipper_name, cache)
        return {eid: header_data} if header_data else {}

    try:
        res = await email_fetch_headers_batch(account, chunk)
        if res[0] == "OK":
            chunk_map = _parse_header_batch_lines(res[1])
            headers: dict[bytes, list[Any]] = {}
            for eid in chunk:
                eid_s = eid.decode() if isinstance(eid, bytes) else str(eid)
                # UID may be bare ("100") or folder-prefixed ("INBOX/100")
                raw_uid = eid_s.rsplit("/", 1)[-1]
                if raw_uid in chunk_map:
                    hdata = chunk_map[raw_uid]
                    headers[eid] = hdata
                    if cache:
                        cache.store(
                            eid_s,
                            "(BODY[HEADER.FIELDS (SUBJECT)])",
                            ("OK", hdata),
                            shipper=shipper_name,
                        )
                elif hdata := await _fetch_single_header(
                    account, eid, shipper_name, cache
                ):
                    headers[eid] = hdata
            return headers
    except TimeoutError:
        raise
    except (AioImapException, OSError, AttributeError) as err:
        _LOGGER.debug("Batch header fetch failed, falling back to scalar: %s", err)

    return await _fetch_headers_scalar(account, chunk, shipper_name, cache)


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

    uncached_ids: list[bytes] = []
    headers_by_id: dict[bytes, list[Any]] = {}

    for eid in email_ids:
        # Cache probe — use public API if available (added in this PR)
        if cache:
            cached = getattr(cache, "get_cached", lambda *_: None)(
                eid, "(BODY[HEADER.FIELDS (SUBJECT)])"
            )
            if isinstance(cached, tuple) and len(cached) > 1:
                headers_by_id[eid] = cached[1]
                continue
        uncached_ids.append(eid)

    for i in range(0, len(uncached_ids), _MAX_HEADER_CHUNK):
        chunk = uncached_ids[i : i + _MAX_HEADER_CHUNK]
        chunk_headers = await _fetch_header_chunk(account, chunk, shipper_name, cache)
        headers_by_id.update(chunk_headers)

    for eid in email_ids:
        header_data = headers_by_id.get(eid)
        if not header_data:
            continue
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
        path = Path(absolute_image_path) / shipper_name
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
        "photo_source": extraction_config.get("photo_source"),
    }


async def _copy_generic_placeholder(
    hass: HomeAssistant,
    shipper_cfg: dict[str, Any],
) -> None:
    """Copy the generic placeholder for the shipper."""
    shipper_name = shipper_cfg["name"]
    placeholder = ASSET_ROOT / f"no_deliveries_{shipper_name}.jpg"
    if not await anyio.Path(placeholder).exists():
        placeholder = ASSET_ROOT / "mail_none.gif"

    target = Path(shipper_cfg["image_path"]) / shipper_name / shipper_cfg["image_name"]
    _LOGGER.debug(
        "No %s images found in emails, using placeholder: %s",
        shipper_name,
        placeholder.name,
    )
    try:
        await hass.async_add_executor_job(copyfile, str(placeholder), str(target))
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
    for sdata in found_data:
        tracking_nums.extend(
            await get_tracking(sdata.decode(), account, pattern, cache)
        )

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
    for sdata in found_data:
        for eid in sdata.split():
            tracking = await get_tracking(
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
                msg_parts = (await email_fetch(account, eid, "(RFC822)"))[1]
            if number := _find_carrier_number(msg_parts, carrier_re):
                mapping.setdefault(tracking[0], number)
    if not mapping:
        return {}
    return {f"{prefix}_carrier_tracking": mapping}


def _extract_email_text(response_part: bytes | bytearray) -> str:
    """Extract decoded subject and text parts from an email message part."""
    msg = email.message_from_bytes(response_part)
    text_chunks: list[str] = []
    if subject_str := _decode_subject(response_part):
        text_chunks.append(subject_str)

    for part in msg.walk():
        if part.get_content_type() not in ["text/html", "text/plain"]:
            continue
        try:
            email_msg = part.get_payload(decode=True)
            text_chunks.append(email_msg.decode("utf-8", "ignore"))
        except (AttributeError, UnicodeError):
            continue

    return "\n".join(text_chunks)


def _matches_date_or_body(
    text: str,
    body_patterns: list[re.Pattern],
    date_patterns: list[re.Pattern],
    today_date: Any,
) -> bool:
    """Check if email text matches relative body terms or delivery date for today."""
    if any(p.search(text) for p in body_patterns):
        return True

    for pat in date_patterns:
        if m := pat.search(text):
            date_str = m.group(1) if m.groups() else m.group(0)
            parsed = dateparser.parse(date_str, settings={"DATE_ORDER": "DMY"})
            if parsed and parsed.date() == today_date:
                return True
    return False


def _compile_patterns(terms: Any) -> list[re.Pattern]:
    """Compile term or list of terms into regex patterns."""
    if isinstance(terms, str):
        return [re.compile(terms, re.IGNORECASE)]
    if isinstance(terms, list):
        return [re.compile(t, re.IGNORECASE) for t in terms]
    return []


async def _process_emails_with_date_pattern(
    account: IMAP4_SSL,
    config: dict,
    ids: list,
    cache: EmailCache | None = None,
) -> tuple[int, list]:
    """Process emails matching relative delivery terms or explicit delivery date matching today."""
    date_patterns = _compile_patterns(config.get(ATTR_DELIVERY_DATE_PATTERN))
    body_patterns = _compile_patterns(config.get(ATTR_BODY))
    today_date = get_today()
    matched_ids = []

    for eid in ids:
        if cache:
            data = (await cache.fetch(eid, "(RFC822)"))[1]
        else:
            data = (await email_fetch(account, eid, "(RFC822)"))[1]

        for response_part in data:
            if not isinstance(response_part, (bytes, bytearray)):
                continue

            text = _extract_email_text(response_part)
            if _matches_date_or_body(text, body_patterns, date_patterns, today_date):
                matched_ids.append(eid)
                break

    return len(matched_ids), matched_ids


async def _process_emails_by_type(
    account: IMAP4_SSL,
    config: dict,
    ids: list,
    current_count: int,
    cache: EmailCache | None = None,
) -> tuple[int, list]:
    """Process emails based on body search or just count."""
    if ATTR_DELIVERY_DATE_PATTERN in config:
        count, matched_ids = await _process_emails_with_date_pattern(
            account,
            config,
            ids,
            cache,
        )
        return current_count + count, matched_ids
    if ATTR_BODY in config:
        body_count = config.get(ATTR_BODY_COUNT, False)
        mock_data = (b" ".join(ids),)
        count, matched_ids = await find_text_matches(
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
    for eid in ids:
        if cache:
            msg_parts = (await cache.fetch(eid, "(RFC822)", shipper=shipper_name))[1]
        else:
            msg_parts = (await email_fetch(account, eid, "(RFC822)"))[1]
        for response_part in msg_parts:
            if isinstance(response_part, (bytes, bytearray)):
                # Run sync extraction off event loop (file I/O & CPU parsing)
                if await hass.async_add_executor_job(
                    generic_delivery_image_extraction,
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
    amazon_mentions = await find_text(
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
