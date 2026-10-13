"""Combined "All mailboxes" totals for Mail and Packages.

A summary config entry owns no mailbox of its own. It reads the latest data of
every loaded mailbox entry and publishes one set of totals, counting a package
only once when the same tracking (or Amazon order) number shows up in more
than one mailbox, e.g. when shipping emails are forwarded between accounts.
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant

from .const import (
    AMAZON_ORDER,
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_TYPE_SUMMARY,
    SHIPPERS,
    SUMMARY_UNIQUE_ID,
)
from .entity import mailbox_device_name

# Totals that are already sums across shippers inside each mailbox.
TOTAL_KEYS = {"zpackages_transit", "zpackages_delivering", "zpackages_delivered"}
PACKAGE_SUFFIXES = ("_packages", "_delivering", "_delivered", "_exception")
TIMESTAMP_KEYS = {"mail_updated"}


@dataclass
class SummaryData:
    """Runtime data for the summary entry."""

    keys: set[str] = field(default_factory=set)


def is_summary_entry(entry: ConfigEntry) -> bool:
    """Return True if the entry is the combined summary, not a mailbox."""
    return ENTRY_TYPE_SUMMARY in (
        entry.data.get(CONF_ENTRY_TYPE),
        entry.options.get(CONF_ENTRY_TYPE),
    )


def mailbox_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return every mailbox entry (all entries except the summary)."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if not is_summary_entry(entry)
    ]


def summary_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the summary entry if one exists (including ignored ones)."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(
                DOMAIN, include_ignore=True
            )
            if is_summary_entry(entry) or entry.unique_id == SUMMARY_UNIQUE_ID
        ),
        None,
    )


def summary_keys(hass: HomeAssistant, sensor_types: Iterable[str]) -> set[str]:
    """Return the sensor keys any mailbox tracks, limited to known sensor types."""
    known = set(sensor_types)
    keys: set[str] = set()
    for entry in mailbox_entries(hass):
        config = {**entry.data, **entry.options}
        keys.update(key for key in config.get(CONF_RESOURCES, []) if key in known)
    return keys


def loaded_mailbox_data(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return the latest coordinator data of each loaded mailbox, by address."""
    result: dict[str, dict[str, Any]] = {}
    for entry in mailbox_entries(hass):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        runtime = getattr(entry, "runtime_data", None)
        coordinator = getattr(runtime, "coordinator", None)
        data = getattr(coordinator, "data", None)
        if isinstance(data, Mapping):
            result[mailbox_device_name(entry.data)] = dict(data)
    return result


def tracking_key(sensor_key: str) -> str:
    """Return the coordinator key holding identifiers for a sensor.

    Mirrors PackagesSensor: delivered sensors use <shipper>_delivered_tracking,
    the others share <shipper>_tracking. Amazon is identified by order number.
    """
    if sensor_key.startswith("amazon"):
        return AMAZON_ORDER
    prefix, _, last = sensor_key.rpartition("_")
    if not prefix:
        return f"{sensor_key}_tracking"
    if last == "delivered":
        return f"{prefix}_delivered_tracking"
    return f"{prefix}_tracking"


def _identifiers(data: Mapping[str, Any], key: str) -> set[str]:
    """Return the set of identifiers stored under key, ignoring junk values."""
    value = data.get(key)
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _total_identifiers(data: Mapping[str, Any], sensor_key: str) -> set[str]:
    """Return identifiers behind a cross-shipper total (zpackages_*)."""
    delivered = sensor_key == "zpackages_delivered"
    ids: set[str] = set()
    for shipper in SHIPPERS:
        if shipper == "amazon":
            continue
        key = f"{shipper}_delivered_tracking" if delivered else f"{shipper}_tracking"
        ids |= _identifiers(data, key)
    if not delivered:
        ids |= _identifiers(data, AMAZON_ORDER)
    return ids


def deduplicated_count(counts: list[int], id_sets: list[set[str]]) -> int:
    """Combine per-mailbox counts, counting shared identifiers once.

    Each identifier seen in k mailboxes was counted k times, so k - 1 is
    subtracted. Counts without identifiers (e.g. letters) simply add. The
    result never drops below the largest single mailbox count, and never
    exceeds the plain sum.
    """
    if not counts:
        return 0
    total = sum(counts)
    occurrences = Counter(item for ids in id_sets for item in ids)
    duplicates = sum(seen - 1 for seen in occurrences.values() if seen > 1)
    return min(total, max(max(counts), total - duplicates))


def _as_int(value: Any) -> int | None:
    """Return value as a non-negative int, or None if it is not a count."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, int(value))


def _as_datetime(value: Any) -> datetime.datetime | None:
    """Return value as an aware datetime, or None."""
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.UTC)
    return None


def combine(
    sensor_key: str, mailboxes: Mapping[str, Mapping[str, Any]]
) -> tuple[Any, dict[str, Any]]:
    """Return (value, attributes) for one combined sensor."""
    if sensor_key in TIMESTAMP_KEYS:
        stamps = [
            stamp
            for data in mailboxes.values()
            if (stamp := _as_datetime(data.get(sensor_key))) is not None
        ]
        return (max(stamps) if stamps else None), {}

    counts: dict[str, int] = {}
    id_sets: dict[str, set[str]] = {}
    for name, data in mailboxes.items():
        count = _as_int(data.get(sensor_key))
        if count is None:
            continue
        counts[name] = count
        if sensor_key in TOTAL_KEYS:
            id_sets[name] = _total_identifiers(data, sensor_key)
        elif sensor_key.endswith(PACKAGE_SUFFIXES):
            id_sets[name] = _identifiers(data, tracking_key(sensor_key))
        else:
            id_sets[name] = set()

    if not counts:
        return None, {}

    value = deduplicated_count(list(counts.values()), list(id_sets.values()))
    attributes: dict[str, Any] = {"mailboxes": counts}
    combined_ids = sorted(set().union(*id_sets.values()))
    if combined_ids:
        attributes["tracking_#"] = combined_ids
    return value, attributes

