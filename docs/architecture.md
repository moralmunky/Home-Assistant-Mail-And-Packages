# Mail and Packages Architecture & Design Standards

This document describes the architectural design, sensor taxonomy, data pipeline, and design rationales for the **Home Assistant Mail and Packages** integration.

---

## 1. Core Architecture Overview

Mail and Packages connects to an IMAP email server, parses delivery notifications across multiple shipping carriers and retail merchants, and surfaces sensor and camera entities to Home Assistant.

```
┌─────────────────────────────────────────────────────────────┐
│                    IMAP Mail Server                         │
└──────────────────────────────┬──────────────────────────────┘
                               │ (IMAP RFC 3501 Search & Fetch)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             DataUpdateCoordinator (_async_update_data)      │
│  - EmailCache (Store-backed IMAP email deduplication)       │
│  - Server-aware batch searching                             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     GenericShipper                          │
│  - Carrier regex matching & subject parsing                 │
│  - Embedded marketplace tracking extraction (Shopify, HD)   │
│  - Deduplication (_deduplicate_batch_tracking)              │
│  - Rollup total computation (_compute_package_totals)       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  Home Assistant Entities                    │
│  - Sensor entities (*_delivering, *_delivered, *_packages)  │
│  - Summary rollups (mail_packages_in_transit, etc.)         │
│  - Camera entities (mail_usps_camera, shipper badges)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Sensor Taxonomy & Lifecycle

Each supported carrier defines up to three standard package sensor entities in `const.py` (`SENSOR_DATA`):

| Sensor Suffix | Purpose | Configuration in `SENSOR_DATA` | IMAP Search Executed? |
| :--- | :--- | :--- | :--- |
| **`*_delivering`** | Packages currently **out for delivery** or scheduled for delivery **today** | List of `email` senders, `subject` patterns, optional `body` patterns | **Yes** |
| **`*_delivered`** | Packages successfully **delivered today** (resets at midnight) | List of `email` senders, `subject` patterns, optional `body` patterns | **Yes** |
| **`*_packages`** | Computed rollup total of active package volume for the carrier | `{}` (Empty dictionary) | **No** (Computed dynamically) |

### Additional Global Sensors
- **`sensor.mail_packages_in_transit`**: Total count of all packages across all carriers currently out for delivery today.
- **`sensor.mail_packages_delivered`**: Total count of all packages delivered today across all carriers.
- **`sensor.mail_deliveries_message`**: Formatted summary text for notifications and Lovelace dashboard cards.
- **`sensor.mail_updated`**: Diagnostic timestamp of the last successful mailbox scan.

---

## 3. Why General "Shipped / In-Transit" Packages Are Not Tracked

A foundational design decision of Mail and Packages is that **general "shipped", "picked up", or intermediate "in-transit" emails are excluded from sensor tracking**.

### Rationale

1. **Email-Based Parsing vs. Carrier API Tracking**:
   - The integration operates purely by querying consumer email inboxes over IMAP. It does not interface directly with carrier tracking APIs or webhooks.
   - Most carriers and retailers send an initial "Order Shipped" or "Shipment Notice" email once, followed by days of silence with no intermediate status updates until the final delivery morning.
2. **State Management & Inbox Expiration Ambiguity**:
   - Email inboxes do not automatically update old messages when a physical package advances along transit hubs.
   - Tracking raw "shipped" notifications causes stale messages to linger in search windows, artificially inflating package counts for days or weeks without any reliable mechanism to know when transit has completed (especially if a delivery email is missed, deleted, or formatted differently).
3. **Actionable Daily Automation Scope**:
   - The primary objective of Mail and Packages is to trigger **actionable same-day home automations**—alerting household members when packages are on the truck for delivery today (`*_delivering`) or have been left on the porch (`*_delivered`).
   - Broad long-term parcel tracking across multi-week transit routes is better suited for dedicated parcel tracking integrations backed by carrier web APIs.

---

## 4. Why `*_packages` Sensors Are Configured as `{}` in `SENSOR_DATA`

All carrier `*_packages` sensors must be defined as an empty dictionary (`{}`) in `SENSOR_DATA`:

1. **Entity Registration**:
   - Home Assistant entity generation (`sensor.py`), options flow sensor selection, and `SENSOR_TYPES` descriptions require each entity key to exist in `SENSOR_DATA`.
2. **Explicit Search Exclusion**:
   - An empty dictionary signals to `GenericShipper.process_batch()` and `DataUpdateCoordinator` that the sensor must **not** perform an independent IMAP query.
3. **Dynamic Rollup Total**:
   - In `shippers/generic.py`, `_compute_package_totals()` calculates `*_packages` as:
     $$\text{packages} = \text{delivering} + \text{delivered}$$
   - This ensures total package counts accurately reflect all carrier activity for the day without duplicate network requests or double-counting.

---

## 5. Deduplication & Transit Pipeline

During each coordinator update cycle:
1. **Per-Carrier IMAP Search**: Shippers search IMAP for delivered and out-for-delivery messages within the configured time window (`custom_days`).
2. **Extended Window Delivery Filtering**: `_deduplicate_batch_tracking` removes tracking numbers found in delivered emails from the active delivering list so delivered items do not continue to show as out for delivery.
3. **Embedded Carrier Tracking Extraction**: For retailers and marketplace platforms (such as Home Depot or Shopify) that embed third-party carrier tracking numbers (UPS, FedEx, Canada Post, etc.) in their order notification emails, `GenericShipper` extracts the underlying carrier tracking ID to prevent duplicate counts when both merchant and courier emails are received for the same package.
4. **Email Caching (`EmailCache`)**: Uses Home Assistant's `Store` helper (`custom_components/mail_and_packages/utils/cache.py`) to persist email body hashes and message IDs across updates, preventing redundant fetches of unchanged messages.

---

## 6. Camera Entities & Delivery Image Processing

Mail and Packages provides camera entities for mail visualization and shipper delivery photos:

### USPS Informed Delivery Camera
- **Mail Piece Assembly**: Images attached to USPS Informed Delivery emails are parsed and converted into an animated GIF or MP4 showing all scanned letters for the day.
- **Vision Grid Generation**: An optional composite image grid can be generated containing tiled mail piece images, optimized for downstream LLM vision integrations.
- **Midnight Reset**: Mail cameras revert to a placeholder image after midnight local time or when no new mail images have arrived.

### Carrier Delivery Photos
- **Delivery Confirmation Images**: Shippers supporting delivery verification photos (e.g., FedEx, UPS, Amazon) extract photographic proof of delivery directly from incoming emails.
- **Async Safety**: All disk file I/O and image transformations (Pillow / ImageMagick) are offloaded to executor threads via `hass.async_add_executor_job` to keep the Home Assistant event loop responsive.

---

## 7. Authentication Pipelines

The integration supports multiple authentication schemes configured via Config Entry and Options Flow:

1. **Standard IMAP (Password / App Password)**:
   - Connects over SSL (port 993) or STARTTLS.
   - For providers requiring multi-factor authentication (e.g., Gmail, Yahoo, iCloud), dedicated App Passwords are used.
2. **OAuth2 Authentication**:
   - Native Home Assistant OAuth2 implementation supporting **Google (Gmail)** and **Microsoft (Outlook / Office 365 / Exchange)**.
   - Automatic token refresh is coordinated before initiating IMAP connections, handling revoked or expired access tokens gracefully via `ConfigEntryAuthFailed` reauth flows.

---

## 8. Email Caching & State Persistence

To minimize bandwidth, reduce latency, and prevent hitting IMAP server rate limits:

- **`EmailCache`**: Backed by Home Assistant's `Store` storage helper (`.storage/mail_and_packages_cache`), caching email body hashes and tracking numbers.
- **Cache Eviction**: Entries older than the maximum carrier retention window (`custom_days`) are periodically purged during coordinator cleanup routines.
- **Midnight Rollover**: Package counts and delivery states reset at local midnight, ensuring counters accurately reflect same-day activity.
