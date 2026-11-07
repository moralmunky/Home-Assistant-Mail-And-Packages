"""Tracking and marketplace helpers for Mail and Packages data update coordinator."""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass

from custom_components.mail_and_packages import const

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

    # Add or update delivering tracking numbers (record last-seen date)
    for tid in delivering:
        if tid:
            in_transit[tid] = today_iso

    # Remove delivered tracking numbers
    for tid in delivered:
        in_transit.pop(tid, None)

    # Expire entries older than TTL
    cutoff = (
        dt.date.fromisoformat(today_iso) - dt.timedelta(days=ttl_days)
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
        has_delivering_details = f"{prefix}_delivering" in tracking_details
        if in_transit or has_delivering_details:
            if not in_transit and data.get(f"{prefix}_delivering"):
                _LOGGER.debug(
                    "Prefix '%s': no tracked packages remain in transit — "
                    "overriding delivering count %s -> 0",
                    prefix,
                    data.get(f"{prefix}_delivering"),
                )
            data[f"{prefix}_tracking"] = list(in_transit.keys())
            data[f"{prefix}_delivering"] = sum(
                1 for seen in in_transit.values() if seen == today_iso
            )
        if in_transit:
            delivered_count = data.get(f"{prefix}_delivered", 0)
            data[f"{prefix}_packages"] = len(in_transit) + (
                delivered_count if isinstance(delivered_count, int) else 0
            )


@dataclass(frozen=True, slots=True)
class MailDeliveredLatchState:
    """State for latched USPS mail delivered sensor."""

    date: str | None = None
    latched: bool = False


def latch_mail_delivered(
    latch_state: MailDeliveredLatchState | dict[str, object],
    data: dict,
    today_iso: str,
) -> MailDeliveredLatchState:
    """Latch usps_mail_delivered on for the rest of the day once seen."""
    if "usps_mail_delivered" not in data:
        if isinstance(latch_state, MailDeliveredLatchState):
            return latch_state
        return MailDeliveredLatchState(
            date=str(latch_state.get("date")) if latch_state.get("date") else None,
            latched=bool(latch_state.get("latched")),
        )

    if isinstance(latch_state, dict):
        date = latch_state.get("date")
        latched = bool(latch_state.get("latched"))
    else:
        date = latch_state.date
        latched = latch_state.latched

    if date != today_iso:
        date = today_iso
        latched = False

    latched = latched or bool(data["usps_mail_delivered"])
    data["usps_mail_delivered"] = int(latched)

    # For backward compatibility with dict mutations if a dict was passed
    if isinstance(latch_state, dict):
        latch_state["date"] = date
        latch_state["latched"] = latched

    return MailDeliveredLatchState(date=today_iso, latched=latched)


def dedupe_marketplace_duplicates(
    data: dict,
    tracking_details: dict[str, list],
) -> None:
    """Drop marketplace packages already counted by a carrier shipper."""
    marketplace_prefixes = tuple(const.MARKETPLACE_CARRIER_TRACKING)
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


def attribute_dhl_marketplace_packages(
    data: dict,
    tracking_details: dict[str, list],
) -> None:
    """Move marketplace-reported DHL eCommerce packages to the DHL sensors.

    Runs before dedupe_marketplace_duplicates, which consumes (pops) the
    carrier-tracking mappings this step reads: when a marketplace email's
    embedded carrier number is a full DHL eCommerce number and no carrier
    shipper already holds that number, the package was really shipped by
    DHL, so it counts under DHL instead of the marketplace. Numbers a
    carrier already holds are left for the dedup pass to drop from the
    marketplace side. Counts move in
    ``data``; the tracking number joins the DHL tracking-details list for
    its state, so the coordinator's tracking-state step picks it up as
    DHL in-transit/delivered. Marketplace ids are kept on the marketplace
    tracking lists (they are how the marketplace email is referenced);
    the DHL side is keyed by the carrier number itself.
    """
    marketplace_prefixes = tuple(const.MARKETPLACE_CARRIER_TRACKING)

    ecommerce_re = re.compile(const.DHL_ECOMMERCE_TRACKING_PATTERN)
    carrier_numbers = {
        str(num).upper()
        for sensor, ids in tracking_details.items()
        if not sensor.startswith(marketplace_prefixes)
        for num in ids or []
    }

    for prefix in marketplace_prefixes:
        mapping = data.get(f"{prefix}_carrier_tracking") or {}
        if not isinstance(mapping, dict):
            continue
        for marketplace_id, carrier_num in list(mapping.items()):
            carrier_num = str(carrier_num)
            if not ecommerce_re.fullmatch(carrier_num):
                continue
            if carrier_num.upper() in carrier_numbers:
                # A carrier shipper already holds this number; the dedup
                # pass owns that case.
                continue
            if _attribute_dhl_number(
                data,
                tracking_details,
                prefix,
                marketplace_id,
                carrier_num,
                carrier_numbers,
            ):
                _adjust_packages_rollup(data, prefix, -1)
                _adjust_packages_rollup(data, "dhl", 1)


def _attribute_dhl_number(
    data: dict,
    tracking_details: dict[str, list],
    prefix: str,
    marketplace_id: str,
    carrier_num: str,
    carrier_numbers: set[str],
) -> bool:
    """Move one marketplace package to the DHL sensors for its state.

    Returns True when the marketplace id sat on a delivering or
    delivered list and the package moved; the caller then adjusts the
    packages rollups. The carrier number joins the DHL tracking list
    for that state and the carrier-held set, so a second marketplace
    reporting the same number defers to the DHL record.
    """
    moved = False
    for suffix in ("_delivering", "_delivered"):
        sensor = f"{prefix}{suffix}"
        ids = tracking_details.get(sensor)
        if not ids or marketplace_id not in ids:
            continue
        moved = True
        if isinstance(data.get(sensor), int):
            data[sensor] = max(0, data[sensor] - 1)
        dhl_sensor = f"dhl{suffix}"
        if isinstance(data.get(dhl_sensor), int):
            data[dhl_sensor] += 1
        tracking_details.setdefault(dhl_sensor, []).append(carrier_num)
        carrier_numbers.add(carrier_num.upper())
        _LOGGER.debug(
            "Attributed %s package %s to DHL (DHL eCommerce tracking %s)",
            prefix,
            marketplace_id,
            carrier_num,
        )
    return moved


def _adjust_packages_rollup(data: dict, prefix: str, delta: int) -> None:
    """Adjust a computed ``<prefix>_packages`` rollup by delta.

    Only applies when the rollup is a computed sensor (empty SENSOR_DATA
    entry), mirroring remove_marketplace_package.
    """
    packages_sensor = f"{prefix}_packages"
    # Computed <prefix>_packages rollups are the SENSOR_DATA entries whose
    # config is an empty dict, so this truthiness check identifies them
    # (mirroring remove_marketplace_package).
    if not const.SENSOR_DATA.get(packages_sensor) and isinstance(
        data.get(packages_sensor), int
    ):
        data[packages_sensor] = max(0, data[packages_sensor] + delta)


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
