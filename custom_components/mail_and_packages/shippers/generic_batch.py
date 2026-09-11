"""Batch processing mixin for generic shipper."""

from __future__ import annotations

from typing import Any

from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import ATTR_COUNT, ATTR_TRACKING
from custom_components.mail_and_packages.utils.cache import EmailCache


class GenericBatchMixin:
    """Mixin providing batch processing, deduplication, and package totals for GenericShipper."""

    process: Any

    async def process_batch(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> dict[str, Any]:
        """Process multiple generic sensors in batch."""
        batch_results, all_tracking = await self._process_individual_sensors(
            account, date, sensors, cache, since_date
        )

        self._deduplicate_batch_tracking(batch_results)
        self._compute_package_totals(batch_results)

        # Merge results and aggregate global tracking
        res: dict[str, Any] = {}
        for sensor, sensor_res in batch_results:
            tracking = (
                sensor_res.pop("pre_filtered_tracking", [])
                if sensor.endswith("_delivered")
                else sensor_res.get(ATTR_TRACKING)
            )
            for key, value in list(sensor_res.items()):
                if key.endswith("_carrier_tracking") and isinstance(res.get(key), dict):
                    sensor_res[key] = {**res[key], **value}
            res.update(sensor_res)
            # Expose per-sensor raw tracking for coordinator state management.
            # Keyed as "_tracking_details" to distinguish from the public data dict.
            if tracking and sensor.endswith(
                ("_delivering", "_delivered", "_exception")
            ):
                res.setdefault("_tracking_details", {})[sensor] = list(tracking)

        if all_tracking:
            res[ATTR_TRACKING] = list(all_tracking)

        return res

    async def _process_individual_sensors(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> tuple[list[tuple[str, dict[str, Any]]], set[str]]:
        """Process each sensor independently and aggregate tracking."""
        batch_results: list[tuple[str, dict[str, Any]]] = []
        all_tracking: set[str] = set()

        for sensor in sensors:
            sensor_res = await self.process(
                account, date, sensor, cache, since_date=since_date
            )
            # Replicate coordinator dictionary logic for local sensor counts
            if sensor not in sensor_res and ATTR_COUNT in sensor_res:
                sensor_res[sensor] = sensor_res[ATTR_COUNT]

            # Capture today-only tracking for _delivered sensors BEFORE
            # _deduplicate_batch_tracking runs (which currently only modifies
            # _delivering and _packages sensor results).
            if sensor_res.get(ATTR_TRACKING) and sensor.endswith("_delivered"):
                sensor_res[f"{sensor}_tracking"] = sensor_res[ATTR_TRACKING]

            # Record results for post-processing
            batch_results.append((sensor, sensor_res))

            # Aggregate all tracking numbers found
            if sensor_res.get(ATTR_TRACKING):
                all_tracking.update(sensor_res[ATTR_TRACKING])

        return batch_results, all_tracking

    def _deduplicate_batch_tracking(
        self,
        batch_results: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Deduplicate tracking numbers across sensors based on shipper prefix."""
        shippers: dict[str, dict[str, Any]] = {}
        for sensor, sensor_res in batch_results:
            # Prefix is everything before the last underscore (e.g., 'ups', 'fedex')
            prefix = "_".join(sensor.split("_")[:-1])
            if prefix not in shippers:
                shippers[prefix] = {
                    "delivered": set(),
                    "delivering": set(),
                    "update_targets": [],
                }

            tracking = set(sensor_res.get(ATTR_TRACKING, []))
            if sensor.endswith("_delivered"):
                # ATTR_TRACKING on _delivered sensors holds only TODAY's
                # deliveries (so the sensor resets at midnight); dedup must
                # use the extended-window list or packages delivered on a
                # previous day are never subtracted from _delivering.
                extended = sensor_res.get("pre_filtered_tracking")
                shippers[prefix]["delivered"].update(
                    tracking if extended is None else set(extended)
                )
            elif sensor.endswith(("_delivering", "_exception")):
                shippers[prefix]["delivering"].update(tracking)
                shippers[prefix]["update_targets"].append((sensor, sensor_res))

        for data in shippers.values():
            # Remove "delivered" tracking numbers from in-transit sensors
            self._apply_deduplication(data["update_targets"], data["delivered"])

    def _apply_deduplication(
        self,
        targets: list[tuple[str, dict[str, Any]]],
        delivered_ids: set[str],
    ) -> None:
        """Apply deduplication logic to a list of target sensors."""
        if not delivered_ids:
            return

        for sensor, sensor_res in targets:
            original_tracking = sensor_res.get(ATTR_TRACKING, [])
            new_tracking = [
                tid for tid in original_tracking if tid not in delivered_ids
            ]

            if len(new_tracking) != len(original_tracking):
                sensor_res[ATTR_TRACKING] = new_tracking
                sensor_res[sensor] = len(new_tracking)
                if ATTR_COUNT in sensor_res:
                    sensor_res[ATTR_COUNT] = len(new_tracking)

    def _compute_package_totals(
        self,
        batch_results: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """Compute _packages sensors as delivering + delivered.

        These sensors have no IMAP search of their own; their value is the
        sum of the shipper's _delivering and _delivered counts (matching the
        original pre-refactor behaviour in helpers.py).
        """
        sensor_counts = {
            sensor: sensor_res.get(sensor, sensor_res.get(ATTR_COUNT, 0))
            for sensor, sensor_res in batch_results
        }

        for sensor, sensor_res in batch_results:
            if not sensor.endswith("_packages"):
                continue
            prefix = sensor.replace("_packages", "")
            computed = sensor_counts.get(f"{prefix}_delivering", 0) + sensor_counts.get(
                f"{prefix}_delivered", 0
            )
            sensor_res[sensor] = computed
            sensor_res[ATTR_COUNT] = computed
