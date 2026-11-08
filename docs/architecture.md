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
| **`*_exception`** | Delivery exceptions/delays found in carrier emails; the extracted tracking numbers are retained as `<prefix>_exception_tracking` and shown on the sensor's `tracking_#` attribute so templates can match an exception to a later delivery | List of `email` senders, `subject` patterns, optional `body` patterns | **Yes** |

Two coordinator behaviors soften the midnight reset without changing the rules above: an exception sighting for an already-tracked package refreshes its last-seen date (exceptions still never create in-transit entries or set delivering counts on their own), and a delivered package stays confirmed past midnight while an exception for the same tracking number is still open, clearing once nothing references it or it ages past the tracking TTL. Amazon attempted orders likewise stay open until the delivered order list matches them.

Amazon converts timezone-aware email `Date` headers to the host's local date before using them for arrival-date parsing and today's delivery counts, matching `get_today()` and the generic carrier header parser. Headers without a timezone retain their calendar date.

### Amazon Delivery-Confirmation Sensors

Beyond the generic taxonomy, Amazon has bespoke sensors for matching a delivery across its email lifecycle by **order number**:

- **`amazon_attempted`** ("Mail Amazon Attempted", opt-in): Counts today's "Delivery attempted" emails (sender `order-update@amazon.*`, subject "Delivery attempted"). The attempted order numbers are retained as `amazon_attempted_order` and exposed on the sensor's `order` attribute, so a template or conditional card can show the order — and any delivery code — while the attempt is outstanding. The sensor is a standalone search that deliberately does **not** take part in the `amazon_packages` counting context.
- **`amazon_delivered` order attribute**: The order numbers the Amazon parser already collects for delivered emails are exported as `amazon_delivered_order` and exposed as the delivered sensor's `order` attribute. Comparing `amazon_attempted`'s `order` list against `amazon_delivered`'s is how a missed-delivery card clears itself once the same order is delivered.
- **`amazon_exception`** ("Mail Amazon Exception"): Amazon's running-late notices, with order numbers exposed the same way.

Generic-carrier exception sensors follow the same matching pattern by **tracking number**: `<prefix>_exception_tracking` is retained during the scan and shown on the exception sensor's `tracking_#` attribute (for `usps`, `ups`, `fedex`, `walmart`, `home_depot`, and `post_nl`). Exceptions still never set or override the delivering counts — the retained numbers exist only so templates can match an exception to a later delivery.

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

> **Note:** Steps 4–6 below (marketplace carrier attribution, Shopify store senders, and eBay) land in [PR #1579](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/pull/1579), which is open and not yet merged. On the current codebase only the remaining steps apply; the #1579 steps are marked *(in #1579, open)* where they appear.

1. **Per-Carrier IMAP Search**: Shippers search IMAP for delivered and out-for-delivery messages within the configured time window (`custom_days`).
2. **Extended Window Delivery Filtering**: `_deduplicate_batch_tracking` removes tracking numbers found in delivered emails from the active delivering list so delivered items do not continue to show as out for delivery.
3. **Embedded Carrier Tracking Extraction**: For retailers and marketplace platforms (such as Home Depot or Shopify) that embed third-party carrier tracking numbers (UPS, FedEx, Canada Post, etc.) in their order notification emails, `GenericShipper` extracts the underlying carrier tracking ID to prevent duplicate counts when both merchant and courier emails are received for the same package.
4. **Marketplace Carrier Attribution** *(in #1579, open)*: When a marketplace email's tracking number belongs to a carrier family that no direct carrier email reports — DHL eCommerce numbers (the `420…` format) found in marketplace mail from sources such as eBay, Temu, and Shopify — the package is *attributed* to that carrier (`dhl`) instead of counting under the marketplace. Direct DHL Express email is unaffected and continues to count under `dhl` as before.
5. **Shopify Store Senders** *(in #1579, open)*: Shopify stores that mail order updates from their own domain (rather than Shopify's own senders) are matched by the sample-backed subject shape plus a Shopify body fingerprint in the message; lookalike mail without the fingerprint is skipped. Their extracted carrier tracking numbers take part in deduplication and DHL attribution like any other marketplace mail.
6. **eBay** *(in #1579, open)*: eBay order email from `ebay@ebay.com` counts under `ebay_delivering`; a body line naming the carrier ("Carrier: DHL eCommerce America") or a `420…` tracking number attributes the package to DHL. There is no `ebay_delivered` sensor yet — no genuine delivered sample has been available to build one from.
7. **Email Caching (`EmailCache`)**: Uses Home Assistant's `Store` helper (`custom_components/mail_and_packages/utils/cache.py`) to persist email body hashes and message IDs across updates, preventing redundant fetches of unchanged messages.

---

## 6. Camera Entities & Delivery Image Processing

Mail and Packages provides camera entities for mail visualization and shipper delivery photos:

### USPS Informed Delivery Camera
- **Digest Date Filtering**: The date in the decoded email subject takes precedence over the email's `Date` header when excluding prior-day digests, including MIME-encoded and folded subjects. Undecodable subjects retain the existing raw-subject and `Date` header fallback.
- **Mail Piece Assembly**: Images attached to USPS Informed Delivery emails are parsed and converted into an animated GIF or MP4 showing all scanned letters for the day.
- **Attachment Filtering**: Known announcement filenames are excluded before JPEG attachments receive randomized output names. Saved attachments still use generated names, never untrusted email paths.
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

---

## 9. Delivery Confirmation Support Matrix

Delivery-confirmation support is **not** uniform across carriers. This matrix states what each source actually supports today; unsupported cells are marked honestly rather than implied. "Exception w/ numbers" means the exception sensor exposes the identifiers (tracking numbers, or order numbers for Amazon) that let a template match the exception to a later delivery. Cells marked *(in #1579, open)* describe support that lands in [PR #1579](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/pull/1579), which is open and not yet merged; everything unmarked is implemented today.

| Source | Delivering / Delivered | Exception w/ numbers | Attempted / missed detection | Dedup / attribution |
| :--- | :--- | :--- | :--- | :--- |
| **Amazon** (direct) | Yes / Yes | Yes — `amazon_exception` (running late), order numbers | **Yes** — `amazon_attempted`, order numbers | Matched across the lifecycle by order number (`amazon_attempted_order` vs `amazon_delivered_order`) |
| **USPS** | Yes / Yes | Yes — `usps_exception`, tracking on `tracking_#` | No | — |
| **UPS** | Yes / Yes | Yes — `ups_exception`, tracking on `tracking_#` | No | — |
| **FedEx** | Yes / Yes | Yes — `fedex_exception`, tracking on `tracking_#` | No | Carrier side of marketplace dedup |
| **Walmart** | Yes / Yes | Yes — `walmart_exception`, tracking on `tracking_#` | No | — |
| **Home Depot** | Yes / Yes | Yes — `home_depot_exception`, tracking on `tracking_#` | No | Embedded carrier tracking extracted; carrier email wins on duplicates |
| **PostNL** | Yes / Yes | Yes — `post_nl_exception`, tracking on `tracking_#` | **Yes** — the "we missed you" notice is the `post_nl_exception` email | — |
| **DHL** (direct Express email) | Yes / Yes | No — no `dhl_exception` entry | No | Receives DHL eCommerce packages attributed from marketplace mail *(in #1579, open)* |
| **Canada Post** | Yes / Yes | No — no `capost_exception` entry | No | Carrier side of Etsy/Shopify dedup |
| **eBay** | **No** *(delivering in #1579, open)* / **No** — no `ebay_delivered` yet; a genuine delivered sample is still needed | No | No | Source for DHL eCommerce attribution (carrier line or `420…` number) *(in #1579, open)* |
| **Shopify** (standard senders; store-domain senders in #1579, open) | Yes / Yes | No | No | Dedup against carrier email; source for DHL attribution *(in #1579, open)* |
| **Temu / Etsy** | Yes / Yes | No | No | Dedup against carrier email (carrier wins); Temu is a DHL attribution source *(attribution in #1579, open)* |
| **Post AT / REWE Lieferservice** | Yes / Yes | No — `post_at_exception` / `rewe_lieferservice_exception` exist only as empty placeholders | No | — |
| **All other supported carriers** | Yes / Yes (per `SENSOR_DATA`) | No — no exception entries | No | — |

Known gaps, stated plainly:

- **Attempted/missed-delivery detection exists only for Amazon and PostNL.** No other carrier's "attempted" email is detected today.
- **Exception entries exist only for USPS, UPS, FedEx, Walmart, Home Depot, PostNL, and Amazon.** DHL, Canada Post, and every other carrier have no exception sensor with identifiers.
- **DHL eCommerce attribution, eBay delivering, and Shopify store-domain senders are not implemented yet.** They land in [PR #1579](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/pull/1579) (open); until it merges, marketplace mail counts under the marketplace and only the standard senders above are matched.
- **eBay delivered-side support is missing** until a genuine eBay delivered email sample is available to build from.
- **The USPS Informed Delivery Daily Digest's PACKAGES section is not parsed.** The digest is processed for mailpiece images and counts only; packages that appear solely in the digest are not tracked.
