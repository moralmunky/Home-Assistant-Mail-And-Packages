![GitHub release (latest by date)](https://img.shields.io/github/v/release/moralmunky/Home-Assistant-Mail-And-Packages)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

![GitHub contributors](https://img.shields.io/github/contributors/moralmunky/Home-Assistant-Mail-And-Packages)
![Maintenance](https://img.shields.io/maintenance/yes/2020)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub last commit](https://img.shields.io/github/last-commit/moralmunky/Home-Assistant-Mail-And-Packages)

# HomeAssistant Mail and Packages

This provides a Card, Custom Component, and Notifications for getting UPS, USPS, and FedEx delivery information in Home Assistant. This component shows a snapshot of the current days packages that are in transit for delivery on the current day or have already been delivered on the current day. It also generates the number of USPS mail pieces and images, if available, for the current day.

The component connects to the email account you supply where your shipment notifications are sent. It looks at the subject lines of the current day's emails from the shipping companies and counts the subject line matches to the known standard subject lines from the shipping companies. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

All procedures are done locally on your machine.

Supports only Lovelace UI. Last tested in 0.110.x.

## Credits:

* Huge contributions from [@firstof9](https://github.com/firstof9) moving the project forward and keeping it active!

<br/>
<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## How it works

From your instance of HASS, the [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to the email account you supply where your shipment notifications are sent. It reviews at the subject lines of the current day's emails from the shipping companies and counts the subject lines that match known language from the shipping companies about their transit status. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

* **All procedures are done locally on your machine.**
* **No external services are used to process your email.**
* **No data is sent outside of your local instance of Home Assistant**

#### Search Terms

Shipper | Email | Subject | Body Text
--- | --- | --- | ---
USPS | USPSInformedDelivery@usps.gov|Informed Delivery Daily Digest|none
USPS | auto-reply@usps.com|Expected Delivery on|out for delivery
USPS | auto-reply@usps.com|Item Delivered|none
UPS | mcinfo@ups.com|UPS Update: Package Scheduled for Delivery Today|none
UPS | mcinfo@ups.com|UPS Update: Follow Your Delivery on a Live Map|none
UPS | mcinfo@ups.com|Your UPS Package was delivered|none
FEDEX | TrackingUpdates@fedex.com |Delivery scheduled for today|none
FEDEX | TrackingUpdates@fedex.com |Your package is scheduled for delivery today|none
FEDEX | TrackingUpdates@fedex.com |Your package has been delivered|none
Amazon |shipment-tracking@amazon.com|none|regex order numbers
Amazon |shipment-tracking@amazon.ca|none |regex order numbers

## Installation
### [HACS](https://hacs.xyz) (Recommended)
1. Have [HACS](https://github.com/custom-components/hacs) installed, this will allow you to easily update
2. Add `https://github.com/moralmunky/Home-Assistant-Mail-And-Packages` as a [custom repository](https://hacs.xyz/docs/faq/custom_repositories) and Type: Integration
3. Click install under "Mail and Packages", restart your instance.

### Manual Installation
1. Download this repository as a ZIP (green button, top right) and unzip the archive
2. Copy the `mail_and_packages` folder inside the `custom_components` folder to the Home Assistant `/<config path>/custom_components/` directory
   * You may need to create the `custom_components` in your Home Assistant installation folder if it does not exist
   * On Home Assistant (formerly Hass.io) and Home Assistant Container the final location should be `/config/custom_components/mail_and_packages`
   * On Home Assistant Supervised, Home Assistant Core, and Hassbian the final location should be `/home/homeassistant/.homeassistant/custom_components/mail_and_packages`
3. Restart your instance.

## Configuration
[Go to the Configuration, Templates, and Automations section](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/info.md#configuration)
