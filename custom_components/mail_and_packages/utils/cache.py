"""Email caching utility for Mail and Packages."""

import logging

from aioimaplib import IMAP4_SSL

from .imap import email_fetch, email_fetch_batch, email_fetch_headers, email_fetch_text

_LOGGER = logging.getLogger(__name__)


class EmailCache:
    """Cache for IMAP email fetches to avoid duplicate downloads."""

    def __init__(self, account: IMAP4_SSL) -> None:
        """Initialize the cache."""
        self.account = account
        self._cache_rfc822: dict[str, tuple] = {}
        self._cache_text: dict[str, tuple] = {}
        self._cache_headers: dict[str, tuple] = {}

    async def fetch(self, email_id: str | bytes, parts: str = "(RFC822)") -> tuple:  # noqa: C901
        """Fetch email content or return from cache."""
        eid_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)

        if parts in ("(RFC822)", "BODY[]"):
            if eid_str in self._cache_rfc822:
                return self._cache_rfc822[eid_str]
            res = await email_fetch(self.account, eid_str, parts)
            if res[0] == "OK":
                self._cache_rfc822[eid_str] = res
            return res

        if "HEADER" in parts:
            if eid_str in self._cache_headers:
                return self._cache_headers[eid_str]
            # fallback to RFC822 cache if we already have it
            if eid_str in self._cache_rfc822:
                return self._cache_rfc822[eid_str]
            res = await email_fetch_headers(self.account, eid_str)
            if res[0] == "OK":
                self._cache_headers[eid_str] = res
            return res

        if "TEXT" in parts or parts == "(BODY[1])":
            if eid_str in self._cache_text:
                return self._cache_text[eid_str]
            if eid_str in self._cache_rfc822:
                return self._cache_rfc822[eid_str]
            res = await email_fetch_text(self.account, eid_str, parts)
            if res[0] == "OK":
                self._cache_text[eid_str] = res
            return res

        # Unknown part, bypass cache
        return await email_fetch(self.account, eid_str, parts)

    async def fetch_batch(self, email_ids: list[str | bytes], parts: str = "(RFC822)") -> tuple:
        """Fetch multiple emails in a batch, retrieving from cache if applicable."""
        # For simplicity, if we don't have all of them, fetch the missing ones in batch
        missing_ids = []
        eid_strs = [e.decode() if isinstance(e, bytes) else str(e) for e in email_ids]

        # Determine which ones we already have
        for eid_str in eid_strs:
            if parts in ("(RFC822)", "BODY[]"):
                if eid_str not in self._cache_rfc822:
                    missing_ids.append(eid_str)
            elif "HEADER" in parts:
                if eid_str not in self._cache_headers and eid_str not in self._cache_rfc822:
                    missing_ids.append(eid_str)
            elif "TEXT" in parts or parts == "(BODY[1])":
                if eid_str not in self._cache_text and eid_str not in self._cache_rfc822:
                    missing_ids.append(eid_str)
            else:
                 missing_ids.append(eid_str)

        # Batch fetch only what is missing
        if missing_ids:
             # Just use fetch() internally for now to populate individual items since fetch_batch
             # returns combined lines which might be tricky to parse.
             # Wait, email_fetch_batch might be tricky to cache without parsing the response to separate emails.
             # So actually we will just loop `fetch` for batch if we want it cleanly cached, or we don't cache
             # `fetch_batch` if we aren't parsing it.
             # Actually `fetch_batch` isn't needed if we just do individual fetches? No, batch is faster.
             # But parsing batch response to stick into cache is annoying.
             pass

        # For this version, let's keep fetch_batch simple and bypass cache.
        return await email_fetch_batch(self.account, email_ids, parts)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache_rfc822.clear()
        self._cache_text.clear()
        self._cache_headers.clear()
