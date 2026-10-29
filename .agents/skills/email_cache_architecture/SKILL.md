---
name: Persistent Email Cache Architecture
description: Architecture rules, byte-preservation serialization standards, and expiration rules for EmailCache.
---

# Persistent Email Cache Architecture

This skill documents the design patterns, byte-preservation rules, and expiration lifecycle of the persistent IMAP email caching system (`EmailCache`).

## Architectural Overview

The `EmailCache` utility (`custom_components/mail_and_packages/utils/cache.py`) avoids duplicate IMAP email re-downloads across update cycles by leveraging Home Assistant's `Store` helper (`homeassistant.helpers.storage.Store`).

- **Cache Keying**: Persistent store entries are keyed by `f"{eid_str}:{parts}"` (e.g. `"101:(RFC822)"`, `"102:HEADER"`) to store specific fetch payloads distinctly.
- **Entry-Scoped Lifecycle**: Managed as a single persistent instance per mailbox on `MailDataUpdateCoordinator.email_cache`, scoped by `entry_id` (`mail_and_packages.email_cache.<entry_id>` via `get_cache_store_key(entry_id)`), and cleaned up via `async_remove_cache` when the config entry is removed.
- **Transient Caches**: Cleared on every scan cycle via `set_account()` / `clear()`, while `_persistent_store` retains records across Home Assistant restarts.

## Byte Preservation & Serialization Rules

IMAP email responses contain raw `bytes` (MIME boundaries, binary attachments, headers) that are consumed by carrier parsing logic.

1. **Serialization (`_store_persistent`)**:
   - `bytes` instances inside response lists or tuples are converted to strings using `latin-1` encoding.
   - **Do NOT use UTF-8 with replacement (`utf-8`, `errors="replace"`)**, as non-UTF-8 bytes will be mangled and corrupt header/subject regex matching in downstream carrier parsers.

2. **Deserialization (`fetch`)**:
   - When loading cached payloads from `_persistent_store`, `str` instances are re-encoded back to `bytes` using `latin-1` to restore original byte representations.

## Batch Fetching & Cache Coherence

The `fetch_batch` method (`EmailCache.fetch_batch`) optimizes multi-message downloads while maintaining full cache coherence:

1. **Partitioning**: Incoming email UIDs are checked against both memory and persistent storage (`get_cached`). Only uncached UIDs are sent over the network to `email_fetch_batch`.
2. **Dual-Tier Write-Back**: When the batch IMAP response returns, parsed message parts are mapped back to their originating UIDs and stored immediately in both the in-memory tier and persistent store (`store`).
3. **Graceful Fallback**: If a server does not delimit messages or fails during batch fetch, cached lines are safely preserved and combined.
4. **Public Access Methods**:
   - `get_cached(email_id, parts)`: Non-fetching lookup checking persistent store then memory cache.
   - `store(email_id, parts, data, shipper)`: Public dual-tier write-through storage for pre-fetched or batch-parsed entries.

## Expiration & Purge Lifecycle

The `async_purge_expired(custom_days: int)` method enforces carrier-specific retention:

- **Amazon Carrier Emails (`shipper="amazon"`)**: Retained up to `custom_days` cutoff (default 3 days).
- **Non-Amazon Carrier Emails (`shipper != "amazon"`)**: Purged daily at midnight local/UTC time (`00:00:00`).
- **Malformed / Missing Dates**: Purged immediately.
