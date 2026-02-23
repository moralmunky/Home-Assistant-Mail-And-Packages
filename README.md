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

Paste your Amazon session cookies from your browser's developer tools. Supports multiple Amazon domains (amazon.com, .co.uk, .ca, .de, .it, .in, .com.au, .pl).

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
- `sensor.mail_image_url` - Web-accessible URL (requires External/Internal URL configured)

### Camera Entities

- `camera.mail_usps_camera` - Displays the USPS Informed Delivery mail image GIF
- `camera.mail_amazon_camera` - Displays Amazon delivery images

### Services

- `mail_and_packages.update_image` - Force refresh camera images on demand

## Re-authentication

If your IMAP credentials become invalid (password change, token expiration, etc.), the integration will automatically:

1. Detect the authentication failure during the next scan
2. Show a notification in Home Assistant that re-authentication is needed
3. Guide you through a reauth flow to enter updated credentials
4. Resume normal operation after successful re-authentication

## Security

- **Path traversal protection** on all file operations (image extraction, custom images)
- **SSRF prevention** on LLM endpoints and Amazon cookie domains
- **IMAP connection lifecycle management** with guaranteed cleanup (try/finally)
- **UUID-based image filenames** to prevent enumeration attacks
- **Credential redaction** in diagnostics output
- **Endpoint validation** blocks known cloud metadata endpoints (AWS, Azure, GCP)
- Files in the `www` folder are [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) by default. The random image filename helps mitigate this.

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
