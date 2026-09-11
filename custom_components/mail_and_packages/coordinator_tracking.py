"""Tracking and marketplace helpers for Mail and Packages data update coordinator."""

from __future__ import annotations

import datetime
import logging
import sys

from . import const

_LOGGER = logging.getLogger(__name__)


def update_tracking_for_prefix(
    in_transit_tracking: dict[str, dict[str, str]],
    prefix: str,
    delivering: list[str],
    delivered: list[str],
    today_iso: str,
    ttl_days: int,
) -> None:
    """Add/expire delivering tracking numbers and remove delivered ones."""
    if prefix not in in_transit_tracking:
        in_transit_tracking[prefix] = {}

    in_transit = in_transit_tracking[prefix]

    # Add new delivering tracking numbers (record first-seen date)
    for tid in delivering:
        if tid and tid not in in_transit:
            in_transit[tid] = today_iso

    # Remove delivered tracking numbers
    for tid in delivered:
        in_transit.pop(tid, None)

    # Expire entries older than TTL
    cutoff = (
        datetime.date.fromisoformat(today_iso) - datetime.timedelta(days=ttl_days)
    ).isoformat()
    expired = [tid for tid, seen in in_transit.items() if seen < cutoff]
    for tid in expired:
        del in_transit[tid]


def apply_tracking_state(
    in_transit_tracking: dict[str, dict[str, str]],
    data: dict,
    tracking_details: dict[str, list[str]],
    today_iso: str,
    max_tracking_age_days: int,
) -> None:
    """Update in-transit tracking state and override sensor counts."""
    prefixes: set[str] = set(in_transit_tracking.keys())
    for sensor_key in tracking_details:
        prefix = "_".join(sensor_key.split("_")[:-1])
        if prefix:
            prefixes.add(prefix)

    for prefix in prefixes:
        if prefix in in_transit_tracking and not (
            f"{prefix}_delivering" in tracking_details
            or f"{prefix}_exception" in tracking_details
            or f"{prefix}_delivered" in tracking_details
        ):
            _LOGGER.debug(
                "Prefix '%s' has no tracking_details entries — "
                "may be a removed carrier; tracking will persist until TTL expiry",
                prefix,
            )

        delivering = list(tracking_details.get(f"{prefix}_delivering", []))
        delivering += list(tracking_details.get(f"{prefix}_exception", []))
        delivered = list(tracking_details.get(f"{prefix}_delivered", []))

        update_tracking_for_prefix(
            in_transit_tracking,
            prefix,
            delivering,
            delivered,
            today_iso,
            max_tracking_age_days,
        )

        in_transit = in_transit_tracking.get(prefix, {})
        has_details = any(
            f"{prefix}_{suffix}" in tracking_details
            for suffix in ("delivering", "exception")
        )
        if in_transit or has_details:
            if not in_transit and data.get(f"{prefix}_delivering"):
                _LOGGER.debug(
                    "Prefix '%s': no tracked packages remain in transit — "
                    "overriding delivering count %s -> 0",
                    prefix,
                    data.get(f"{prefix}_delivering"),
                )
            data[f"{prefix}_tracking"] = list(in_transit.keys())
            data[f"{prefix}_delivering"] = len(in_transit)
        if in_transit:
            delivered_count = data.get(f"{prefix}_delivered", 0)
            data[f"{prefix}_packages"] = len(in_transit) + (
                delivered_count if isinstance(delivered_count, int) else 0
            )


def latch_mail_delivered(
    latch_state: dict[str, object],
    data: dict,
    today_iso: str,
) -> None:
    """Latch usps_mail_delivered on for the rest of the day once seen."""
    if "usps_mail_delivered" not in data:
        return

    if latch_state.get("date") != today_iso:
        latch_state["date"] = today_iso
        latch_state["latched"] = False

    latch_state["latched"] = bool(latch_state.get("latched")) or bool(
        data["usps_mail_delivered"]
    )
    data["usps_mail_delivered"] = int(bool(latch_state["latched"]))


def dedupe_marketplace_duplicates(
    data: dict,
    tracking_details: dict[str, list],
) -> None:
    """Drop marketplace packages already counted by a carrier shipper."""
    coord_mod = sys.modules.get("custom_components.mail_and_packages.coordinator")
    const_mod = getattr(coord_mod, "const", const) if coord_mod else const
    marketplace_prefixes = tuple(const_mod.MARKETPLACE_CARRIER_TRACKING)
    if not marketplace_prefixes:
        return

    carrier_numbers = {
        str(num).upper()
        for sensor, ids in tracking_details.items()
        if not sensor.startswith(marketplace_prefixes)
        for num in ids or []
    }

    for prefix in marketplace_prefixes:
        mapping = data.pop(f"{prefix}_carrier_tracking", None) or {}
        for marketplace_id, carrier_num in mapping.items():
            if str(carrier_num).upper() in carrier_numbers:
                remove_marketplace_package(
                    data, tracking_details, prefix, marketplace_id, carrier_num
                )


def remove_marketplace_package(
    data: dict,
    tracking_details: dict[str, list],
    prefix: str,
    marketplace_id: str,
    carrier_num: str,
) -> None:
    """Remove one de-duplicated package from a marketplace's sensors."""
    removed = False
    for suffix in ("_delivering", "_delivered"):
        sensor = f"{prefix}{suffix}"
        ids = tracking_details.get(sensor)
        if ids and marketplace_id in ids:
            ids.remove(marketplace_id)
            if isinstance(data.get(sensor), int):
                data[sensor] = max(0, data[sensor] - 1)
            removed = True
            _LOGGER.debug(
                "De-duplicated %s package %s (carrier tracking %s already "
                "counted by a carrier shipper)",
                prefix,
                marketplace_id,
                carrier_num,
            )
    packages_sensor = f"{prefix}_packages"
    if (
        removed
        and not const.SENSOR_DATA.get(packages_sensor)
        and isinstance(data.get(packages_sensor), int)
    ):
        data[packages_sensor] = max(0, data[packages_sensor] - 1)
