---
name: Persistent Email Cache Architecture
description: Architecture rules, byte-preservation serialization standards, and expiration rules for EmailCache.
---

# Persistent Email Cache Architecture

This skill documents the design patterns, byte-preservation rules, and expiration lifecycle of the persistent IMAP email caching system (`EmailCache`).

## Architectural Overview

The `EmailCache` utility (`custom_components/mail_and_packages/utils/cache.py`) avoids duplicate IMAP email re-downloads across update cycles by leveraging Home Assistant's `Store` helper (`homeassistant.helpers.storage.Store`).

- **Cache Keying**: Persistent store entries are keyed by `f"{eid_str}:{parts}"` (e.g. `"101:(RFC822)"`, `"102:HEADER"`) to store specific fetch payloads distinctly.
- **Singleton Lifecycle**: Managed as a single persistent instance on `MailDataUpdateCoordinator.email_cache`.
- **Transient Caches**: Cleared on every scan cycle via `set_account()` / `clear()`, while `_persistent_store` retains records across Home Assistant restarts.

## Byte Preservation & Serialization Rules

IMAP email responses contain raw `bytes` (MIME boundaries, binary attachments, headers) that are consumed by carrier parsing logic.

1. **Serialization (`_store_persistent`)**:
   - `bytes` instances inside response lists or tuples are converted to strings using `latin-1` encoding.
   - **Do NOT use UTF-8 with replacement (`utf-8`, `errors="replace"`)**, as non-UTF-8 bytes will be mangled and corrupt header/subject regex matching in downstream carrier parsers.

2. **Deserialization (`fetch`)**:
   - When loading cached payloads from `_persistent_store`, `str` instances are re-encoded back to `bytes` using `latin-1` to restore original byte representations.

## Expiration & Purge Lifecycle

The `async_purge_expired(custom_days: int)` method enforces carrier-specific retention:

- **Amazon Carrier Emails (`shipper="amazon"`)**: Retained up to `custom_days` cutoff (default 3 days).
- **Non-Amazon Carrier Emails (`shipper != "amazon"`)**: Purged daily at midnight local/UTC time (`00:00:00`).
- **Malformed / Missing Dates**: Purged immediately.
