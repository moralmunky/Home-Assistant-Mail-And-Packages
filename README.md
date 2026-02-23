![GitHub](https://img.shields.io/github/license/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub Repo stars](https://img.shields.io/github/stars/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/moralmunky/Home-Assistant-Mail-And-Packages)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
![Pytest](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/workflows/Pytest/badge.svg?branch=master)
![CodeQL](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/workflows/CodeQL/badge.svg?branch=master)
![Validate with hassfest](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/workflows/Validate%20with%20hassfest/badge.svg?branch=master)

# Mail and Packages

A [Home Assistant](https://www.home-assistant.io/) custom integration that creates sensors for mail and package tracking. It connects to your IMAP email server, parses shipping notification emails from supported carriers, and creates sensors showing delivery counts and statuses. It also generates animated GIFs from USPS Informed Delivery mail images.

## Features

- **13 supported carriers** with automatic email parsing
- **USPS Informed Delivery** mail image GIF/MP4 generation
- **Amazon delivery images** and Hub Locker pickup codes
- **Universal email scanning** for tracking numbers across all emails
- **Package Tracking Registry** for persistent end-to-end package lifecycle tracking
- **Tracking service forwarding** to 17track, AfterShip, or AliExpress
- **AI/LLM analysis** of emails for tracking numbers (Ollama, Anthropic, OpenAI)
- **Amazon cookie-based tracking** for direct order status polling
- **Reauth flow** with automatic credential failure detection and notification
- **HACS compatible** with guided setup wizard

## Privacy-First Design

**All core processing is local by default. No data ever leaves your network unless you explicitly enable an optional feature.**

- Core email parsing, image processing, and regex matching all happen locally
- Advanced features (LLM cloud APIs, tracking service forwarding) are **disabled by default** and require explicit opt-in
- When using Ollama for LLM analysis, everything stays on your local network
- Clear privacy notices are shown during setup when configuring cloud-based features

## Supported Carriers

| Carrier | Delivered | In Transit | Exceptions | Tracking Numbers |
|---------|:---------:|:----------:|:----------:|:----------------:|
| USPS | X | X | | X |
| UPS | X | X | | X |
| FedEx | X | X | | X |
| Amazon | X | | X | X |
| DHL | X | X | | X |
| Canada Post | X | X | | |
| Hermes (UK) | X | X | | |
| Royal Mail | X | X | | |
| Australia Post | X | X | | |
| Poczta Polska | | X | | |
| InPost (PL) | X | X | | X |
| DPD (PL) | X | X | | X |
| GLS | X | X | | X |

**Aggregate sensors:** Total packages delivered and in transit across all carriers.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations**
3. Click the **+** button and search for "Mail and Packages"
4. Click **Install**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/mail_and_packages` directory to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

Configuration is done entirely through the UI. No YAML configuration is needed.

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Mail and Packages**
3. Follow the setup wizard

### Step 1: IMAP Credentials

| Option | Description | Default |
|--------|-------------|---------|
| Host | IMAP server address | *required* |
| Port | IMAP port (SSL) | 993 |
| Username | Email account username | *required* |
| Password | Email account password | *required* |

### Step 2: Sensors & Email Processing

| Option | Description | Default |
|--------|-------------|---------|
| Mail Folder | IMAP folder to monitor | INBOX |
| Sensors List | Which carrier sensors to enable | *select* |
| Scan Interval | Minutes between email checks (min: 5) | 5 |
| IMAP Timeout | Connection timeout in seconds (min: 10) | 30 |
| Image Path | Where to store mail images | /config/www/mail_and_packages/ |
| GIF Duration | Seconds per frame in mail GIF | 5 |
| Generate MP4 | Create MP4 video from mail images (requires ffmpeg) | Off |
| Create External Image | Copy images to www folder for notifications | Off |
| Amazon Forwarded Emails | Comma-separated forwarding addresses | *blank* |
| Amazon Days | Days back to search for Amazon emails | 3 |
| Custom Image | Use a custom "no mail" placeholder image | Off |

**Advanced Tracking Options** (all disabled by default):

| Option | Description | Default |
|--------|-------------|---------|
| Scan All Emails | Scan today's emails for tracking numbers using regex | Off |
| Package Registry | Persistent package lifecycle tracking with deduplication | Off |
| Forward to Tracking Service | Send discovered numbers to a tracking service | Off |
| AI/LLM Analysis | Use AI to extract tracking numbers from emails | Off |
| Amazon Cookie Tracking | Poll Amazon orders directly via session cookies | Off |

### Step 3: Advanced Tracking Configuration

Only shown if you enabled any advanced tracking features in Step 2.

**Tracking Service Forwarding:**

| Service | Entry ID Required | Notes |
|---------|:-----------------:|-------|
| 17track | Yes | Enter config entry ID from Settings > Devices & Services |
| AfterShip | No | Uses HA AfterShip integration |
| AliExpress | No | Requires HACS AliExpress Package Tracker |

**AI/LLM Providers:**

| Provider | Local | API Key | Notes |
|----------|:-----:|:-------:|-------|
| Ollama | Yes | No | Runs on your network, no data leaves. Default: `llama3.2` |
| Anthropic | No | Yes | Sends email content to Anthropic servers. Default: `claude-haiku-4-5-20251001` |
| OpenAI | No | Yes | Sends email content to OpenAI servers. Default: `gpt-4o-mini` |

**Amazon Cookie Tracking:**

This feature lets the integration check your Amazon order history directly for tracking numbers, without relying on email notifications. It works by using your Amazon session cookies to access your order pages.

**How to get your Amazon cookies (step-by-step):**

1. Open your web browser (Chrome, Firefox, Edge, etc.) and go to [amazon.com](https://www.amazon.com) (or your regional Amazon site)
2. **Log in** to your Amazon account if you aren't already
3. **Open Developer Tools:**
   - **Chrome/Edge:** Press `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
   - **Firefox:** Press `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
   - **Safari:** Enable "Develop" menu in Preferences > Advanced, then press `Cmd+Option+I`
4. In Developer Tools, click the **"Application"** tab (Chrome/Edge) or **"Storage"** tab (Firefox)
5. In the left sidebar, expand **"Cookies"** and click on `https://www.amazon.com`
6. You'll see a table of cookies. You need to copy them in `name=value; name2=value2` format. The key cookies are:
   - `session-id`
   - `session-id-time`
   - `ubid-main` (or `ubid-acbxx` for non-US)
   - `at-main` (or regional variant)
   - `sess-at-main` (or regional variant)
   - `x-main`
   - `csm-hit`

   **Quick method:** In the browser console (Console tab), paste this and press Enter:
   ```javascript
   document.cookie
   ```
   This prints all cookies as a single string you can copy directly.

7. Paste the full cookie string into the **"Amazon browser cookies"** field in the integration setup
8. Set the **"Amazon domain"** to match your region (e.g., `amazon.com`, `amazon.co.uk`, `amazon.de`)

**Important notes:**
- Amazon cookies **expire periodically** (typically every few weeks). When they expire, the integration will log a warning and you'll need to repeat the process
- This feature **only accesses your Amazon order pages** - no other Amazon data is accessed
- All processing happens locally on your Home Assistant instance
- Supports: amazon.com, .ca, .co.uk, .de, .it, .in, .com.au, .pl

### Package Tracking Registry

The Package Tracking Registry provides persistent, end-to-end package lifecycle tracking that goes beyond the daily email count sensors. When enabled, it:

- **Tracks packages across their full lifecycle:** detected → in_transit → out_for_delivery → delivered
- **Deduplicates automatically:** A tracking number found in a forwarded email and later in a carrier notification is recognized as the same package
- **Persists across restarts:** Package state is stored on disk via Home Assistant's `Store` API and survives reboots
- **Context-aware scanning:** Uses keyword proximity matching to reduce false positives when scanning email bodies for tracking numbers
- **Auto-expires stale entries:** Delivered packages clear after 3 days (configurable), unconfirmed detections after 14 days, cleared packages after 30 days
- **Fires events for automations:** Each status transition fires a `mail_and_packages_package_*` event you can use in HA automations

**How it works:**

Each scan cycle, the registry:
1. Scans unprocessed emails for tracking numbers (using carrier regex patterns with context-aware matching)
2. Reconciles carrier sensor data (delivered/in-transit counts) with registry entries
3. Advances package statuses forward only (a package can't go from "delivered" back to "in_transit")
4. Fires HA events for any status transitions
5. Auto-expires old entries based on configurable thresholds

**Configuration options** (shown in Advanced Tracking when registry is enabled):

| Option | Description | Default |
|--------|-------------|---------|
| Package Registry | Enable persistent package lifecycle tracking | Off |
| Auto-clear delivered (days) | Days after delivery before auto-clearing a package | 3 |
| Auto-expire detected (days) | Days before removing unconfirmed tracking numbers | 14 |

**Status lifecycle:**

| Status | Meaning |
|--------|---------|
| `detected` | Tracking number found in email, not yet confirmed by carrier |
| `in_transit` | Carrier confirms package is in transit |
| `out_for_delivery` | Carrier reports out for delivery |
| `delivered` | Carrier confirms delivery |
| `cleared` | Manually or automatically cleared (hidden from counts, prevents re-detection) |

**Automation events:**

The registry fires events on the Home Assistant event bus when package statuses change:

- `mail_and_packages_package_detected` - New tracking number discovered
- `mail_and_packages_package_in_transit` - Package confirmed in transit
- `mail_and_packages_package_out_for_delivery` - Package out for delivery
- `mail_and_packages_package_delivered` - Package delivered

Each event includes `tracking_number`, `carrier`, `status`, `source`, and `previous_status` in the event data.

**Example automation:**

```yaml
automation:
  - alias: "Notify on package delivery"
    trigger:
      - platform: event
        event_type: mail_and_packages_package_delivered
    action:
      - service: notify.mobile_app
        data:
          title: "Package Delivered"
          message: "{{ trigger.event.data.carrier | upper }} package {{ trigger.event.data.tracking_number }} has been delivered."
```

## Sensors

### Package Sensors

For each enabled carrier, the integration creates:
- `sensor.mail_{carrier}_delivered` - Packages delivered today
- `sensor.mail_{carrier}_delivering` - Packages in transit
- `sensor.mail_{carrier}_packages` - Total active packages

### Aggregate Sensors

- `sensor.mail_packages_delivered` - Total delivered across all carriers
- `sensor.mail_packages_in_transit` - Total in transit across all carriers
- `sensor.mail_updated` - Timestamp of last email scan

### Amazon-Specific Sensors

- `sensor.mail_amazon_packages` - Total Amazon packages
- `sensor.mail_amazon_delivered` - Delivered Amazon packages
- `sensor.mail_amazon_exception` - Amazon delivery exceptions
- `sensor.mail_amazon_hub` - Packages at Amazon Hub Lockers (includes pickup code)

### Image Sensors

- `sensor.mail_image_system_path` - Local filesystem path to the mail GIF
- `sensor.mail_image_url` - URL to the mail image. By default, this uses the **authenticated** camera proxy URL (`/api/camera_proxy/camera.mail_usps_camera`) which requires Home Assistant login. If you enable "Copy images to www/ folder", it uses the `/local/` URL instead (publicly accessible without authentication).

### Registry Sensors (when Package Registry is enabled)

- `sensor.mail_registry_tracked` - Total active packages being tracked (all statuses except cleared)
- `sensor.mail_registry_in_transit` - Packages in transit (detected, in_transit, or out_for_delivery)
- `sensor.mail_registry_delivered` - Packages delivered (not yet cleared)

Each registry sensor includes a `packages` attribute with a list of package details (tracking number, carrier, status, source, timestamps, exception flag).

### Camera Entities

- `camera.mail_usps_camera` - Displays the USPS Informed Delivery mail image GIF (served through HA's authenticated API)
- `camera.mail_amazon_camera` - Displays Amazon delivery images (served through HA's authenticated API)

### Services

- `mail_and_packages.update_image` - Force refresh camera images on demand

**Registry Services** (available when Package Registry is enabled):

| Service | Description | Fields |
|---------|-------------|--------|
| `mail_and_packages.clear_package` | Clear a tracked package by tracking number | `tracking_number` (required) |
| `mail_and_packages.clear_all_delivered` | Clear all packages with "delivered" status | *none* |
| `mail_and_packages.mark_delivered` | Manually mark a package as delivered | `tracking_number` (required) |
| `mail_and_packages.add_package` | Manually add a tracking number to the registry | `tracking_number` (required), `carrier` (optional, default: "unknown") |

## Re-authentication

If your IMAP credentials become invalid (password change, token expiration, etc.), the integration will automatically:

1. Detect the authentication failure during the next scan
2. Show a notification in Home Assistant that re-authentication is needed
3. Guide you through a reauth flow to enter updated credentials
4. Resume normal operation after successful re-authentication

## Security

### Image Privacy

By default, mail images are stored in a **private directory** inside the integration folder and are only accessible through Home Assistant's **authenticated camera proxy API**. This means images require a valid HA login to view.

The "Copy images to www/ folder" option (`allow_external`) is **disabled by default**. If enabled, images are copied to the `www/mail_and_packages/` directory, which is [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) without authentication via `/local/` URLs. Only enable this if you specifically need unauthenticated access (e.g., for legacy notification apps that can't use HA authentication).

**For notification apps:** Most modern HA notification services (Companion App, Telegram, etc.) can use the camera entity directly via `camera.mail_usps_camera`. You do **not** need to enable the www copy for notifications.

### Other Security Measures

- **Path traversal protection** on all file operations (image extraction, custom images)
- **SSRF prevention** on LLM endpoints and Amazon cookie domains
- **IMAP connection lifecycle management** with guaranteed cleanup (try/finally)
- **UUID-based image filenames** to prevent enumeration attacks
- **Credential redaction** in diagnostics output
- **Endpoint validation** blocks known cloud metadata endpoints (AWS, Azure, GCP)

## Troubleshooting

1. **Enable debug logging** by adding to `configuration.yaml`:
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.mail_and_packages: debug
   ```

2. **Check diagnostics**: Go to the device page and download diagnostics. Sensitive data (credentials, tracking numbers) is automatically redacted.

3. **Common issues**:
   - Ensure your email provider allows IMAP access (Gmail requires App Passwords)
   - Email must not be deleted until the next day
   - Use a dedicated folder with email filters for best results
   - Scan interval minimum is 5 minutes to avoid rate limiting

## Development

### Requirements

- Python 3.12+
- Home Assistant 2024.3+

### Running Tests

```bash
# Full test suite via tox
tox

# Direct pytest
pytest --timeout=30 --cov=custom_components/mail_and_packages/ --cov-report=xml

# Single test file
pytest tests/test_helpers.py -v

# Single test
pytest tests/test_helpers.py::test_function_name -v
```

### Linting

```bash
# All linters via tox
tox -e lint

# Individual tools
black --check custom_components/mail_and_packages/
flake8 custom_components/mail_and_packages/
pylint custom_components/mail_and_packages/
isort --check custom_components/mail_and_packages/
```

### Code Style

- **Formatter:** [black](https://github.com/psf/black) (88 character line length)
- **Import sorting:** [isort](https://pycqa.github.io/isort/) (black-compatible profile)
- **PR titles:** Follow [Conventional Commits](https://www.conventionalcommits.org/)
- **Branch PRs** from `dev`, not `master`

## Credits

- **[@moralmunky](https://github.com/moralmunky)** - Creator and maintainer
- **[@firstof9](https://github.com/firstof9)** - Major contributor, keeping the project active
- **[@brandon-claps](https://github.com/brandon-claps)** - Advanced tracking features (universal email scanning, tracking service forwarding, LLM analysis, Amazon cookie tracking), security hardening, HA modern patterns conformance

<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Links

- [Configuration Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings)
- [Supported Shipper Requirements](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements)
- [Troubleshooting Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Troubleshooting)
- [USPS Informed Delivery Image Examples](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/USPS-Informed-Delivery-Image)
- [Notification Examples](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Notifications)
- [Issue Tracker](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/issues)
