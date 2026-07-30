"""Email caching utility for Mail and Packages."""

import datetime
import logging
from typing import Any

from aioimaplib import IMAP4_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .imap import email_fetch, email_fetch_batch, email_fetch_headers, email_fetch_text

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "mail_and_packages.email_cache"


class EmailCache:
    """Cache for IMAP email fetches to avoid duplicate downloads across scans."""

    def __init__(
        self,
        account: IMAP4_SSL | None = None,
        hass: HomeAssistant | None = None,
        store_key: str = STORAGE_KEY,
    ) -> None:
        """Initialize the cache."""
        self.account = account
        self.hass = hass
        self._store: Store | None = (
            Store(hass, STORAGE_VERSION, store_key) if hass else None
        )
        self._cache_rfc822: dict[str, tuple] = {}
        self._cache_text: dict[str, tuple] = {}
        self._cache_headers: dict[str, tuple] = {}
        # Persistent metadata mapping: eid_str -> {"fetched_at": iso_str, "shipper": name, "data": tuple}
        self._persistent_store: dict[str, dict[str, Any]] = {}

    def set_account(self, account: IMAP4_SSL) -> None:
        """Set active IMAP account for the current scan cycle."""
        self.account = account
        # Clear transient per-scan caches while preserving persistent records
        self._cache_rfc822.clear()
        self._cache_text.clear()
        self._cache_headers.clear()

    async def async_load(self) -> None:
        """Load persistent cache from storage."""
        if not self._store:
            return
        try:
            data = await self._store.async_load()
            if isinstance(data, dict):
                self._persistent_store = data.get("entries", {})
        except OSError as err:
            _LOGGER.warning("Failed to load email cache: %s", err)
            self._persistent_store = {}

    async def async_save(self) -> None:
        """Save persistent cache to storage."""
        if not self._store:
            return
        try:
            await self._store.async_save({"entries": self._persistent_store})
        except OSError as err:
            _LOGGER.warning("Failed to save email cache: %s", err)

    async def async_purge_expired(self, custom_days: int = 3) -> None:
        """Purge expired cache entries based on carrier expiration rules."""
        now = datetime.datetime.now(datetime.UTC)
        midnight_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        custom_days_cutoff = now - datetime.timedelta(days=custom_days)

        expired_keys = []
        for key, entry in self._persistent_store.items():
            fetched_at_str = entry.get("fetched_at")
            if not fetched_at_str:
                expired_keys.append(key)
                continue
            try:
                fetched_at = datetime.datetime.fromisoformat(fetched_at_str)
            except ValueError:
                expired_keys.append(key)
                continue

            shipper = entry.get("shipper", "unknown")
            if shipper == "amazon":
                if fetched_at < custom_days_cutoff:
                    expired_keys.append(key)
            elif fetched_at < midnight_today:
                expired_keys.append(key)

        for key in expired_keys:
            self._persistent_store.pop(key, None)

        if expired_keys and self._store:
            await self.async_save()

    async def fetch(  # noqa: C901
        self,
        email_id: str | bytes,
        parts: str = "(RFC822)",
        shipper: str = "generic",
    ) -> tuple:
        """Fetch email content or return from cache."""
        eid_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)

        cache_key = f"{eid_str}:{parts}"

        # Check persistent cache first if available
        if cache_key in self._persistent_store:
            entry = self._persistent_store[cache_key]
            cached_data = entry.get("data")
            if cached_data and isinstance(cached_data, list) and len(cached_data) == 2:
                status, response_list = cached_data
                restored_list = []
                if isinstance(response_list, list):
                    for item in response_list:
                        if isinstance(item, (list, tuple)):
                            restored_list.append(
                                tuple(
                                    x.encode("latin-1") if isinstance(x, str) else x
                                    for x in item
                                )
                            )
                        elif isinstance(item, str):
                            restored_list.append(item.encode("latin-1"))
                        else:
                            restored_list.append(item)
                else:
                    restored_list = response_list
                return (status, restored_list)

        if parts in ("(RFC822)", "BODY[]"):
            if eid_str in self._cache_rfc822:
                return self._cache_rfc822[eid_str]
            if self.account is None:
                return ("NO", ["No active IMAP connection"])
            res = await email_fetch(self.account, eid_str, parts)
            if res[0] == "OK":
                self._cache_rfc822[eid_str] = res
                self._store_persistent(cache_key, res, shipper)
            return res

        if "HEADER" in parts:
            if eid_str in self._cache_headers:
                return self._cache_headers[eid_str]
            if eid_str in self._cache_rfc822:
                return self._cache_rfc822[eid_str]
            if self.account is None:
                return ("NO", ["No active IMAP connection"])
            res = await email_fetch_headers(self.account, eid_str)
            if res[0] == "OK":
                self._cache_headers[eid_str] = res
                self._store_persistent(cache_key, res, shipper)
            return res

        if "TEXT" in parts or parts == "(BODY[1])":
            if eid_str in self._cache_text:
                return self._cache_text[eid_str]
            if eid_str in self._cache_rfc822:
                return self._cache_rfc822[eid_str]
            if self.account is None:
                return ("NO", ["No active IMAP connection"])
            res = await email_fetch_text(self.account, eid_str, parts)
            if res[0] == "OK":
                self._cache_text[eid_str] = res
                self._store_persistent(cache_key, res, shipper)
            return res

        if self.account is None:
            return ("NO", ["No active IMAP connection"])
        return await email_fetch(self.account, eid_str, parts)

    def _store_persistent(self, eid_str: str, data: tuple, shipper: str) -> None:
        """Store fetched email data in persistent structure."""
        # Convert bytes objects inside tuple response for JSON serialization safety using latin-1 encoding to preserve exact 1-to-1 byte representations
        status, response_list = data
        serializable_list = []
        if isinstance(response_list, list):
            for item in response_list:
                if isinstance(item, tuple):
                    serialized_tuple = tuple(
                        x.decode("latin-1") if isinstance(x, (bytes, bytearray)) else x
                        for x in item
                    )
                    serializable_list.append(serialized_tuple)
                elif isinstance(item, (bytes, bytearray)):
                    serializable_list.append(item.decode("latin-1"))
                else:
                    serializable_list.append(item)
        else:
            serializable_list = response_list

        self._persistent_store[eid_str] = {
            "fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "shipper": shipper,
            "data": [status, serializable_list],
        }

    async def fetch_batch(
        self, email_ids: list[str | bytes], parts: str = "(RFC822)"
    ) -> tuple:
        """Fetch multiple emails in a batch."""
        if self.account is None:
            return ("NO", ["No active IMAP connection"])
        return await email_fetch_batch(self.account, email_ids, parts)

    def clear(self) -> None:
        """Clear the transient per-scan cache."""
        self._cache_rfc822.clear()
        self._cache_text.clear()
        self._cache_headers.clear()
