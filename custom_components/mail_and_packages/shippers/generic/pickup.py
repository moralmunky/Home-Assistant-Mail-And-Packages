"""Parse USPS pickup confirmation and completion messages."""

from __future__ import annotations

import email
import re
from datetime import date, datetime
from html import unescape
from typing import Any


def parse_pickup(raw: bytes) -> dict[str, Any] | None:
    """Extract a pickup event from a USPS message, without address information."""
    message = email.message_from_bytes(raw)
    subject = str(message.get("Subject", ""))
    if not subject.startswith("USPS - Your Package Pickup Request"):
        return None
    completed = subject.strip() == "USPS - Your Package Pickup Request"
    if (
        not completed
        and subject.strip() != "USPS - Your Package Pickup Request Confirmation"
    ):
        return None
    text = _pickup_text(message)
    if not text:
        return None
    if completed and "successfully completed your Package Pickup" not in text:
        return None
    label = "Scheduled Pickup Date" if completed else "Requested Pickup Date"
    match = re.search(
        rf"{label}\s*:?.*?(\d{{1,2}}/\d{{1,2}}/\d{{4}})", text, re.IGNORECASE
    )
    if not match:
        return None
    try:
        pickup_date = datetime.strptime(match.group(1), "%m/%d/%Y").date()
    except ValueError:
        return None
    # Confirmation messages have the heading before the date and reference.
    # Completion messages also include a standalone confirmation near the top.
    if completed:
        reference = re.search(
            r"Confirmation\s*#\s*:?\s*([A-Z]{2,}[A-Z0-9-]+)", text, re.IGNORECASE
        )
    else:
        reference = re.search(
            r"Requested Pickup Date\s+Confirmation\s*#\s*\d{1,2}/\d{1,2}/\d{4}\s+([A-Z]{2,}[A-Z0-9-]+)",
            text,
            re.IGNORECASE,
        )
    if not reference:
        return None
    count_label = "Collected Piece Count" if completed else "Total Packages"
    count = re.search(rf"{count_label}\s*:?\s*(\d+)", text, re.IGNORECASE)
    return {
        "confirmation": reference.group(1),
        "pickup_date": pickup_date,
        "packages": int(count.group(1)) if count else None,
        "completed": completed,
    }


def _pickup_text(message: email.message.Message) -> str:
    """Strip HTML markup from the first HTML body part."""
    for part in message.walk():
        if part.get_content_type() != "text/html":
            continue
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            html = payload.decode(part.get_content_charset() or "utf-8", "replace")
            return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())
    return ""


def summarize_pickups(events: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Select the next uncompleted pickup and latest completed pickup."""
    booked: dict[str, dict[str, Any]] = {}
    done: dict[str, dict[str, Any]] = {}
    for event in events:
        ref = event["confirmation"]
        if event["completed"]:
            done[ref] = event
        else:
            booked[ref] = event  # Later message for same confirmation replaces earlier.
    upcoming = [
        item
        for ref, item in booked.items()
        if ref not in done and item["pickup_date"] >= today
    ]
    upcoming.sort(key=lambda item: item["pickup_date"])
    result: dict[str, Any] = {
        "pickup_date": None,
        "pickup_today": False,
        "pickup_tomorrow": False,
        "days_until": None,
        "confirmation": None,
        "packages": None,
        "last_pickup_completed_date": None,
        "last_pickup_completed_confirmation": None,
        "last_pickup_completed_packages": None,
    }
    if upcoming:
        first = upcoming[0]
        days = (first["pickup_date"] - today).days
        result.update(
            pickup_date=first["pickup_date"].isoformat(),
            pickup_today=days == 0,
            pickup_tomorrow=days == 1,
            days_until=days,
            confirmation=first["confirmation"],
            packages=first["packages"],
        )
    if done:
        latest = max(done.values(), key=lambda item: item["pickup_date"])
        result.update(
            last_pickup_completed_date=latest["pickup_date"].isoformat(),
            last_pickup_completed_confirmation=latest["confirmation"],
            last_pickup_completed_packages=latest["packages"],
        )
    return result
