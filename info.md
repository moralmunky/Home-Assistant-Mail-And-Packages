{% if prerelease %}
### This is a pre-release version
It may contain bugs or break functionality in addition to adding new features and fixes. Please review open issues and submit new issues to the [GitHub issue tracker](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/issues).

{% endif %}

![GitHub release (latest by date)](https://img.shields.io/github/v/release/moralmunky/Home-Assistant-Mail-And-Packages)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
![GitHub contributors](https://img.shields.io/github/contributors/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub commit activity](https://img.shields.io/github/commit-activity/y/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub last commit](https://img.shields.io/github/last-commit/moralmunky/Home-Assistant-Mail-And-Packages/dev)

## About Mail and Packages

The [Mail and Packages](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) integration creates sensors for supported carriers to show a snapshot of mail and **packages that are scheduled to be delivered the current day**. It provides counts of in-transit and delivered packages, generates rotating GIFs from USPS Informed Delivery mail images, and optionally scans all emails for tracking numbers.

### Supported Carriers

USPS, UPS, FedEx, Amazon, DHL, Canada Post, Hermes, Royal Mail, Australia Post, Poczta Polska, InPost, DPD, and GLS.

### Key Features

- **Email-based tracking** - Monitors your IMAP inbox for shipping notifications from 13 carriers
- **USPS Mail Images** - Animated GIF/MP4 from Informed Delivery with camera entity
- **Amazon Hub Lockers** - Detects Hub deliveries and extracts pickup codes
- **Universal email scanning** - Regex-based tracking number discovery across all emails (opt-in)
- **Tracking service forwarding** - Forward numbers to 17track, AfterShip, or AliExpress (opt-in)
- **AI/LLM analysis** - Use Ollama (local), Anthropic, or OpenAI to find tracking numbers in emails (opt-in)
- **Amazon cookie tracking** - Poll Amazon orders directly via browser cookies (opt-in)
- **Automatic reauth** - Detects credential failures and guides you through re-authentication

### Privacy First

All core processing happens locally on your Home Assistant instance. No data is sent to external services unless you explicitly enable optional advanced features. When using Ollama for AI analysis, even that stays on your local network.

## How It Works

The integration connects to your IMAP email account and reviews the subject lines (and optionally body text) of the current day's emails from supported carriers. It counts matches against known shipping notification patterns to determine delivery counts and statuses. For USPS Informed Delivery, it extracts mail images and combines them into a rotating GIF.

_**Important:** Emails must not be deleted until the next day._ You can use email filters to route shipping notifications into a dedicated folder.

### Privacy / Security Note

Files stored in the Home Assistant `www` folder are [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) unless you have taken additional security measures. Image filenames use random UUIDs to prevent enumeration. Two sensors provide paths for use in notifications:

- `sensor.mail_image_system_path` - Local filesystem path
- `sensor.mail_image_url` - Web-accessible URL (requires External/Internal URL configured in HA)

## Credits

- **[@moralmunky](https://github.com/moralmunky)** - Creator and maintainer
- **[@firstof9](https://github.com/firstof9)** - Major contributor
- **[@brandon-claps](https://github.com/brandon-claps)** - Advanced tracking features, security hardening

<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## Support

- [Configuration & Email Settings](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings)
- [Supported Shipper Requirements](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements)
- [Troubleshooting](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Troubleshooting)
- [USPS Informed Delivery Image](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/USPS-Informed-Delivery-Image)
- [Notifications](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Notifications)
