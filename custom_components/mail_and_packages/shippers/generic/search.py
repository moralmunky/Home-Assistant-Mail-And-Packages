"""Search and delivery processing mixin for generic shipper."""

from __future__ import annotations

import logging
from typing import Any

from aioimaplib import IMAP4_SSL

from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED,
    ATTR_BODY,
    ATTR_TRACKING,
    CONF_FORWARDING_HEADER,
)
from custom_components.mail_and_packages.utils.imap import email_search

from .helpers import SearchContext, _filter_emails_by_date

_LOGGER = logging.getLogger(__name__)


class GenericSearchMixin:
    """Mixin providing search, delivery processing, and image finalization."""

    # These type annotations satisfy mypy for methods provided by other classes/mixins
    config: dict[str, Any]
    hass: Any
    name: str

    @staticmethod
    def _determine_search_date(
        sensor_type: str,
        date: str,
        since_date: str | None,
    ) -> str:
        """Determine whether to use extended search window across midnight."""
        if (
            since_date
            and sensor_type.endswith(
                ("_delivering", "_exception", "_delivered", "_packages")
            )
            and sensor_type not in {"dpd_uk_delivering", "post_de_delivering"}
        ):
            return since_date
        return date

    def _resolve_forwarding(self, email_addresses: list[str]) -> tuple[str, list[str]]:
        """Return (forwarding_header, resolved_email_addresses).

        Header mode: uses original-sender header for matching; address list
        is passed as-is so IMAP can match via HEADER substring.
        Address-list mode: prepends the user's forwarded addresses so that
        emails arriving through a forwarding service are also matched.
        """
        forwarding_header = self.config.get(CONF_FORWARDING_HEADER, "")
        if forwarding_header and forwarding_header != "(none)":
            return forwarding_header, email_addresses
        forwarding_header = ""
        forwarded_emails = self.config.get("forwarded_emails", [])
        if isinstance(forwarded_emails, str):
            forwarded_emails = [
                e.strip() for e in forwarded_emails.split(",") if e.strip()
            ]
        if forwarded_emails:
            email_addresses = forwarded_emails + email_addresses
        return forwarding_header, email_addresses

    async def _process_delivered_today(
        self,
        account: IMAP4_SSL,
        date: str,
        base_ctx: SearchContext,
        result: dict[str, Any],
        found_data: list[Any],
    ) -> int:
        """Filter delivered emails locally to get today-only counts and tracking."""
        candidate_uids: list[bytes] = []
        for sdata in found_data:
            if isinstance(sdata, (bytes, bytearray)):
                candidate_uids.extend(eid for eid in sdata.split() if eid)

        if not candidate_uids:
            result[ATTR_TRACKING] = []
            return 0

        shipper_name = (
            base_ctx.shipper_cfg.get("name", "") if base_ctx.shipper_cfg else ""
        )
        today_uids = await _filter_emails_by_date(
            account,
            candidate_uids,
            date,
            shipper_name,
            base_ctx.cache,
        )

        today_found: list[Any] = [b" ".join(today_uids)] if today_uids else []
        today_tracking = await self._process_tracking_numbers(
            base_ctx.sensor_type, today_found, account, base_ctx.cache
        )
        result[ATTR_TRACKING] = today_tracking
        return len(today_tracking) if today_tracking else len(today_uids)

    async def _finalize_shipper_image(
        self,
        shipper_cfg: dict[str, Any] | None,
        image_path: str | None,
        image_found: bool,
        result: dict[str, Any],
    ) -> None:
        """Set shipper image attributes and placeholder fallback if needed."""
        if shipper_cfg:
            image_attr = f"{shipper_cfg['name']}_image"
            result[image_attr] = shipper_cfg["image_name"]
            result["image_path"] = image_path

            if not image_found:
                await self._copy_generic_placeholder(shipper_cfg)

    async def _search_for_emails(
        self,
        account: IMAP4_SSL,
        email_addresses: list[str],
        date: str,
        subjects: list[str],
        ctx: SearchContext,
    ) -> tuple[int, list[bytes], bool]:
        """Search for and process emails."""
        count = 0
        unique_email_ids: set[str] = set()
        found_data: list[bytes] = []
        image_found = False

        (server_response, sdata) = await email_search(
            account=account,
            address=email_addresses,
            date=date,
            subject=subjects,
            body=ctx.config.get(ATTR_BODY, ""),
            header=ctx.forwarding_header,
        )

        if server_response == "OK" and sdata[0]:
            raw_ids = sdata[0].split()
            _LOGGER.debug(
                "Found %d matching email IDs for %s: %s",
                len(raw_ids),
                ctx.sensor_type,
                [eid.decode() if isinstance(eid, bytes) else eid for eid in raw_ids],
            )
            verified_ids = await self._verify_matched_subjects(
                account, raw_ids, ctx.sensor_type, subjects, ctx.cache
            )
            filtered_new_ids = self._filter_unique_ids(verified_ids, unique_email_ids)

            if filtered_new_ids:
                count, img_found = await self._process_matched_emails(
                    account,
                    filtered_new_ids,
                    count,
                    ctx,
                    found_data,
                )
                if img_found:
                    image_found = True

        return count, found_data, image_found

    async def _process_matched_emails(
        self,
        account: IMAP4_SSL,
        new_ids: list[bytes],
        current_count: int,
        ctx: SearchContext,
        found_data: list[bytes],
    ) -> tuple[int, bool]:
        """Process a batch of matched unique emails."""
        image_found = False
        count, matched_ids = await self._process_emails_by_type(
            account, ctx.config, new_ids, current_count, ctx.cache
        )
        if matched_ids:
            found_data.append(b" ".join(matched_ids))

            if ctx.shipper_cfg:
                if await self._extract_images_for_shipper(
                    account, matched_ids, ctx.shipper_cfg, ctx.cache
                ):
                    image_found = True

            if (
                ctx.sensor_type.endswith("_delivered")
                and ctx.sensor_type != AMAZON_DELIVERED
            ):
                await self._check_amazon_mentions(
                    account, matched_ids, ctx.result, ctx.cache
                )

        return count, image_found
