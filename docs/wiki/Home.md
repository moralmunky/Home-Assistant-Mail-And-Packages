# Home Assistant Mail and Packages

The [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to your email server via IMAP (supporting standard password and OAuth2 authentication) to parse delivery notifications and expose mail and package tracking sensors and camera entities in Home Assistant. All processing occurs locally on your Home Assistant instance.

---

## Features

- **Package Tracking**: Per-shipper sensors for packages in transit, delivered, and exceptions.
- **Delivery Confirmations**: Amazon one-time-password delivery codes, attempted (missed) delivery detection, and exception tracking numbers you can match to a later delivery — see [Amazon Delivery Confirmations](Amazon-Delivery-Confirmations).
- **USPS Informed Delivery**: Mail piece counts, rotating GIF, and grid images of today's mail scans.
- **Dedicated Camera Entities**: Built-in camera entities for USPS and carrier delivery images.
- **OAuth2 Authentication**: Supports standard IMAP credentials as well as OAuth2 authentication for Gmail and Outlook/Microsoft 365.
- **Email Forwarding**: Support for email forwarding services (e.g. SimpleLogin, AnonAddy) via forwarding headers or address lists.
- **AI Vision Grid**: Static grid image generation (`sensor.mail_grid_image_path`) for use with AI vision models (e.g., Gemini, LLM Vision).
- **100% Local Processing**: All processing occurs locally on your Home Assistant instance. No data leaves your network.

---

## How It Works

1. **Email Parsing**: The integration connects to your email account over IMAP (using password or OAuth2 authentication) and searches for subject lines and body text matching [supported carriers](Supported-Shipper-Requirements).
2. **In-Transit Sensors** (`_delivering`): Searches a configurable window of past days (default: 3) so packages shipped prior to today remain tracked until delivered.
3. **Delivered Sensors** (`_delivered`): Counts delivery notification emails received today and resets at midnight local time.
4. **Summary & Total Sensors**: Aggregate sensors (`sensor.mail_packages_in_transit` and `sensor.mail_packages_delivered`) combine counts across all enabled carriers (USPS, FedEx, UPS, Amazon, DHL, Walmart, etc.).

> [!NOTE]
> The integration does not delete or modify your emails. Do not delete delivery emails on the day they arrive, as the integration needs to find them during its scans. To keep your primary inbox clean, you can use email rules to filter shipping emails into a dedicated folder and point the integration at that folder.

---

## Amazon & Carrier Shipping

Amazon uses several third-party carriers (USPS, UPS, FedEx) as well as its own logistics network.
- When Amazon ships via a third-party carrier, the shipment is tracked under that carrier's sensors.
- When Amazon delivers via its own network, notifications with expected arrival dates are tracked under Amazon sensors (`sensor.mail_amazon_packages`).
- Amazon package counts are automatically included in total package counts (`sensor.mail_packages_in_transit` and `sensor.mail_packages_delivered`).

### Amazon expected delivery dates

`sensor.mail_amazon_packages` can include an `order_details` attribute
keyed by pending order number. When an expected delivery date can be
determined from a shipping email, the order's `delivery_date` wll be an ISO
date such as `2026-07-20`. Some orders may not have a date.

The sensor's state remains the number of packages arriving today. To
display order dates, use a template such as this in a Markdown card:

```jinja
{% set details = state_attr('sensor.mail_amazon_packages', 'order_details') or {} %}
{% for order, item in details.items() %}
- {{ order }}: {{ item.get('delivery_date', 'Date unavailable') }}
{% else %}
No pending Amazon order details.
{% endfor %}
```

Adjust the entity ID if yours differs. Results depend on the emails
available within the configured search period.
---

## Wiki Documentation Index

| Guide | Description |
| --- | --- |
| [**Configuration & Email Settings**](Configuration-and-Email-Settings) | Complete setup guide for IMAP, OAuth2, folders, and scan options. |
| [**Supported Shipper Requirements**](Supported-Shipper-Requirements) | Setup steps and notification requirements for all supported carriers. |
| [**Mail Summary Message**](Mail-Summary-Message) | Jinja2 summary templates for Voice/TTS, sensors, and Lovelace cards. |
| [**Notification Examples**](Notifications) | Automation examples for iOS, Android, TTS, and Home Assistant notifications. |
| [**Amazon Delivery Confirmations**](Amazon-Delivery-Confirmations) | Amazon delivery-code (OTP) sensors and recipes, attempted-delivery alerts and cards that clear on delivery, and exception matching. |
| [**USPS Informed Delivery Image**](USPS-Informed-Delivery-Image) | Details on rotating GIF, static grid, and camera entities. |
| [**Email Forwarding**](Email-Forwarding) | How to configure email forwarding (forwarding headers & address lists). |
| [**AI Mail Summary**](AI-Mail-Summary) | Integrating the grid image sensor with AI vision models (e.g. Gemini). |
| [**Multiple Mailboxes & Summary**](Multiple-Mailboxes-and-Summary) | Managing multiple email accounts and the "All mailboxes" deduplicated summary. |
| [**Troubleshooting**](Troubleshooting) | Common issues, debug logging, and resolution steps. |
