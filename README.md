![GitHub](https://img.shields.io/github/license/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub Repo stars](https://img.shields.io/github/stars/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/moralmunky/Home-Assistant-Mail-And-Packages)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
![Pytest](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/workflows/Pytest/badge.svg?branch=0.3.0)
![CodeQL](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/workflows/CodeQL/badge.svg?branch=0.3.0)
![Validate with hassfest](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/workflows/Validate%20with%20hassfest/badge.svg?branch=0.3.0)

![GitHub contributors](https://img.shields.io/github/contributors/moralmunky/Home-Assistant-Mail-And-Packages)
![Maintenance](https://img.shields.io/maintenance/yes/2020)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub commits since tagged version](https://img.shields.io/github/commits-since/moralmunky/Home-Assistant-Mail-And-Packages/0.2.2/0.3.0)
![GitHub last commit](https://img.shields.io/github/last-commit/moralmunky/Home-Assistant-Mail-And-Packages)
![Codecov branch](https://img.shields.io/codecov/c/github/moralmunky/Home-Assistant-Mail-And-Packages/0.3.x)

## About Mail and Packages integration

The [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) creates sensors for [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki#how-it-works) to show a snapshot of mail and packages that are in transit or delviered that are scheduled to be delivered the current day. It also generates the number of USPS mail pieces and provides a rotating GIF of the USPS provided images of the mail, if available, for the current day.

## Credits:

- Huge contributions from [@firstof9](https://github.com/firstof9) moving the project forward and keeping it active!
  <br/>
  <a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## How it works

From your instance of HASS, the [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to the email account you supply where your shipment notifications are sent. It reviews at the subject lines of the current day's emails from the [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki#how-it-works) and counts the subject lines that match known language from the [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki#how-it-works) about their transit status for packages that are scheduled to be delivered the current day. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

- **All procedures are done locally on your machine.**
- **No external services are used to process your email.**
- **No data is sent outside of your local instance of Home Assistant**

##### \*Privacy / Security Note

Please note that files stored in the `www` Home Assistant folder is [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) unless you have taken security measures outside of Home Assistant to secure it. You can place the images in an `images` directory inside Home Assistants root folder and still send notifications via most notification integrations.

See the WIKI [information on how this works](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki).

## Configuration

See the WIKI [for configuring the integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings).

### Supported Shippers and Requirements:

See the WIKI [for account settings needed for certain shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings#supported-shippers-and-requirements).

### Automation and Template Examples

See the WIKI for [example automations and templates](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Example-Automations-and-Templates#delivery-summary-text-sensor-template-example).
