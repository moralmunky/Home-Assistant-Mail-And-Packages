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

The [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to your email account and creates sensors tracking mail and packages scheduled for delivery **today**. It counts in-transit and delivered packages per shipper, generates a rotating GIF of USPS Informed Delivery mail images, and keeps everything completely local — no external services involved.

## Credits

Huge contributions from [@firstof9](https://github.com/firstof9) moving the project forward and keeping it active!

<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## Features

- Per-shipper sensors for packages in transit, delivered, and exceptions
- USPS Informed Delivery — mail piece count and rotating GIF of today's mail images
- Camera entities per shipper with delivery images pulled directly from emails
- OAuth2 authentication support for Microsoft (Outlook/Exchange) and Google (Gmail)
- Email forwarding service support — match carrier emails via a forwarding header (e.g. SimpleLogin) or a per-carrier address list
- LLM vision grid image generation for use with AI-based automations
- All processing done locally on your Home Assistant instance — no data leaves your network

## How it works

From your Home Assistant instance, the integration connects via IMAP to the email account where your shipment notifications are sent. It checks the subject lines of today's emails from [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements) against known delivery status language and counts matches. For USPS Informed Delivery emails it also downloads the mail piece images and combines them into a rotating GIF.

See the [wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki) for full details.

> **Note:** Emails cannot be deleted until the next day, but you can filter them into a dedicated folder and point the integration at that folder. Delivery images revert to the no-mail placeholder after the first scan past midnight, local time.

> **Privacy / Security:** All processing is done locally. No data is sent outside your Home Assistant instance. Files stored in the `www` folder are [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) by default — image filenames are randomised to reduce exposure. Two sensors are available for use in notifications:
> - `sensor.mail_image_system_path`
> - `sensor.mail_image_url` *(requires `External_URL`, `Internal_URL`, or Home Assistant Cloud to be configured)*

## Support & Documentation

| Resource | Link |
|---|---|
| Configuration & email settings | [Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings) |
| Supported shippers & requirements | [Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements) |
| Troubleshooting | [Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Troubleshooting) |
| USPS Informed Delivery image | [Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/USPS-Informed-Delivery-Image) |
| Text summary templates | [Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Mail-Summary-Message) |
| Notification examples | [Wiki](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Notifications) |
