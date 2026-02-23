"""Persistent package tracking registry for Mail and Packages.

Provides end-to-end package lifecycle tracking with persistent storage.
Packages progress through: detected -> in_transit -> out_for_delivery -> delivered.
Users can manually clear packages or they auto-expire after configurable days.

All processing is local. No data is sent externally.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "mail_and_packages.packages"

# Status rank for forward-only transitions
STATUS_RANK = {
    "detected": 0,
    "in_transit": 1,
    "out_for_delivery": 2,
    "delivered": 3,
    "cleared": 4,
}


class PackageRegistry:
    """Persistent registry for tracking packages across their lifecycle.

    Each package is keyed by its tracking number (or Amazon order number).
    Status transitions are forward-only: detected < in_transit <
    out_for_delivery < delivered < cleared.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the package registry."""
        self._hass = hass
        self._entry_id = entry_id
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry_id}",
        )
        self._packages: dict[str, dict[str, Any]] = {}
        self._processed_uids: dict[str, str] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load registry from persistent storage."""
        data = await self._store.async_load()
        if data:
            self._packages = data.get("packages", {})
            self._processed_uids = data.get("processed_uids", {})
        self._loaded = True
        _LOGGER.debug(
            "Package registry loaded: %s packages, %s processed UIDs",
            len(self._packages),
            len(self._processed_uids),
        )

    async def async_save(self) -> None:
        """Save registry to persistent storage."""
        await self._store.async_save(
            {
                "packages": self._packages,
                "processed_uids": self._processed_uids,
            }
        )

    async def async_remove(self) -> None:
        """Remove the storage file (for config entry cleanup)."""
        await self._store.async_remove()

    @property
    def packages(self) -> dict[str, dict[str, Any]]:
        """Return all packages."""
        return self._packages

    def get_active_packages(self) -> dict[str, dict[str, Any]]:
        """Return packages that are not cleared."""
        return {k: v for k, v in self._packages.items() if v.get("status") != "cleared"}

    def get_by_status(self, status: str) -> dict[str, dict[str, Any]]:
        """Return packages with a specific status."""
        return {k: v for k, v in self._packages.items() if v.get("status") == status}

    def register_package(
        self,
        tracking_number: str,
        carrier: str,
        status: str = "detected",
        source: str = "unknown",
        source_from: str = "",
        description: str = "",
    ) -> bool:
        """Register a new package or update an existing one.

        Returns True if the package was newly added or its status changed.
        Only allows forward status transitions.
        """
        now = datetime.now(timezone.utc).isoformat()

        if tracking_number in self._packages:
            existing = self._packages[tracking_number]

            # Don't re-add cleared packages (prevents re-detection)
            if existing.get("status") == "cleared":
                return False

            # Forward-only status transitions
            existing_rank = STATUS_RANK.get(existing.get("status", "detected"), 0)
            new_rank = STATUS_RANK.get(status, 0)

            if new_rank <= existing_rank:
                # Still update carrier_confirmed if carrier email sees it
                if source == "carrier_email" and not existing.get("carrier_confirmed"):
                    existing["carrier_confirmed"] = True
                    existing["last_updated"] = now
                    return True
                return False

            # Advance status
            existing["status"] = status
            existing["last_updated"] = now
            if source == "carrier_email":
                existing["carrier_confirmed"] = True
            # Clear exception flag on forward progress
            if existing.get("exception"):
                existing["exception"] = False
            return True

        # New package
        self._packages[tracking_number] = {
            "carrier": carrier,
            "status": status,
            "exception": False,
            "source": source,
            "source_from": source_from,
            "description": description,
            "first_seen": now,
            "last_updated": now,
            "carrier_confirmed": source == "carrier_email",
        }
        return True

    def set_exception(self, tracking_number: str, value: bool = True) -> bool:
        """Set or clear the exception flag on a package.

        Returns True if the flag changed.
        """
        if tracking_number not in self._packages:
            return False
        pkg = self._packages[tracking_number]
        if pkg.get("status") == "cleared":
            return False
        if pkg.get("exception") == value:
            return False
        pkg["exception"] = value
        pkg["last_updated"] = datetime.now(timezone.utc).isoformat()
        return True

    def clear_package(self, tracking_number: str) -> bool:
        """Mark a package as cleared.

        Returns True if the package existed and was cleared.
        """
        if tracking_number not in self._packages:
            return False
        pkg = self._packages[tracking_number]
        if pkg.get("status") == "cleared":
            return False
        pkg["status"] = "cleared"
        pkg["last_updated"] = datetime.now(timezone.utc).isoformat()
        return True

    def clear_all_delivered(self) -> int:
        """Clear all packages in 'delivered' status.

        Returns count of packages cleared.
        """
        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for pkg in self._packages.values():
            if pkg.get("status") == "delivered":
                pkg["status"] = "cleared"
                pkg["last_updated"] = now
                count += 1
        return count

    def mark_delivered(self, tracking_number: str) -> bool:
        """Manually mark a package as delivered.

        Returns True if the status was changed.
        """
        if tracking_number not in self._packages:
            return False
        pkg = self._packages[tracking_number]
        if pkg.get("status") in ("delivered", "cleared"):
            return False
        pkg["status"] = "delivered"
        pkg["last_updated"] = datetime.now(timezone.utc).isoformat()
        if pkg.get("exception"):
            pkg["exception"] = False
        return True

    def add_package(
        self,
        tracking_number: str,
        carrier: str = "unknown",
    ) -> bool:
        """Manually add a package (or re-add a cleared one).

        Returns True if the package was added.
        """
        now = datetime.now(timezone.utc).isoformat()

        if tracking_number in self._packages:
            existing = self._packages[tracking_number]
            if existing.get("status") == "cleared":
                # Re-add a cleared package
                existing["status"] = "detected"
                existing["carrier"] = carrier
                existing["exception"] = False
                existing["source"] = "manual"
                existing["last_updated"] = now
                existing["carrier_confirmed"] = False
                return True
            # Already tracked
            return False

        self._packages[tracking_number] = {
            "carrier": carrier,
            "status": "detected",
            "exception": False,
            "source": "manual",
            "source_from": "",
            "description": "Manually added",
            "first_seen": now,
            "last_updated": now,
            "carrier_confirmed": False,
        }
        return True

    def auto_expire(
        self,
        delivered_days: int = 3,
        detected_days: int = 14,
        cleared_days: int = 30,
    ) -> int:
        """Remove expired packages from the registry.

        - Delivered packages: removed after delivered_days
        - Detected (never confirmed): removed after detected_days
        - Cleared packages: removed after cleared_days

        Returns count of packages removed.
        """
        now = datetime.now(timezone.utc)
        to_remove = []

        for tracking, pkg in self._packages.items():
            try:
                last_updated = datetime.fromisoformat(pkg["last_updated"])
            except (KeyError, ValueError):
                continue

            age_days = (now - last_updated).days
            status = pkg.get("status", "detected")

            if status == "delivered" and age_days >= delivered_days:
                to_remove.append(tracking)
            elif status == "cleared" and age_days >= cleared_days:
                to_remove.append(tracking)
            elif (
                status == "detected"
                and not pkg.get("carrier_confirmed")
                and age_days >= detected_days
            ):
                to_remove.append(tracking)

        for tracking in to_remove:
            del self._packages[tracking]

        if to_remove:
            _LOGGER.debug("Auto-expired %s packages", len(to_remove))

        return len(to_remove)

    def expire_processed_uids(self, max_age_days: int = 7) -> None:
        """Remove old processed UIDs to prevent unbounded growth."""
        now = datetime.now(timezone.utc)
        to_remove = []

        for uid, date_str in self._processed_uids.items():
            try:
                processed_date = datetime.fromisoformat(date_str)
            except ValueError:
                to_remove.append(uid)
                continue
            if (now - processed_date).days > max_age_days:
                to_remove.append(uid)

        for uid in to_remove:
            del self._processed_uids[uid]

    def is_uid_processed(self, uid: str) -> bool:
        """Check if an email UID has already been processed."""
        return uid in self._processed_uids

    def mark_uid_processed(self, uid: str) -> None:
        """Mark an email UID as processed."""
        self._processed_uids[uid] = datetime.now(timezone.utc).isoformat()

    def get_counts(self) -> dict[str, int]:
        """Return summary counts by status (excluding cleared)."""
        counts = {
            "tracked": 0,
            "in_transit": 0,
            "delivered": 0,
        }
        for pkg in self._packages.values():
            status = pkg.get("status", "detected")
            if status == "cleared":
                continue
            counts["tracked"] += 1
            if status in ("detected", "in_transit", "out_for_delivery"):
                counts["in_transit"] += 1
            elif status == "delivered":
                counts["delivered"] += 1
        return counts

    def get_packages_list(self, status_filter: str | None = None) -> list[dict]:
        """Return packages as a list of dicts (for sensor attributes).

        If status_filter is provided, only return packages with that status.
        For 'in_transit', also includes 'detected' and 'out_for_delivery'.
        """
        result = []
        for tracking, pkg in self._packages.items():
            pkg_status = pkg.get("status", "detected")
            if pkg_status == "cleared":
                continue

            if status_filter:
                if status_filter == "in_transit":
                    if pkg_status not in ("detected", "in_transit", "out_for_delivery"):
                        continue
                elif status_filter != pkg_status:
                    continue

            result.append(
                {
                    "tracking_number": tracking,
                    "carrier": pkg.get("carrier", "unknown"),
                    "status": pkg_status,
                    "exception": pkg.get("exception", False),
                    "source": pkg.get("source", "unknown"),
                    "source_from": pkg.get("source_from", ""),
                    "description": pkg.get("description", ""),
                    "first_seen": pkg.get("first_seen", ""),
                    "last_updated": pkg.get("last_updated", ""),
                    "carrier_confirmed": pkg.get("carrier_confirmed", False),
                }
            )
        return result
