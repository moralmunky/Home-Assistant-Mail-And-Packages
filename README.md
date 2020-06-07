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

Supports only Lovelace UI. Last tested in 0.105.x.

### How it works

From your instance of HASS, the [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to the email account you supply where your shipment notifications are sent. It reviews at the subject lines of the current day's emails from the shipping companies and counts the subject lines that match known language from the shipping companies about their trasnit status. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

* **All procedures are done locally on your machine.**
* **No external services are used to process your email.**
* **No data is sent outside of your local instance of Home Assistant**


<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-green.png" alt="Buy Us A Coffee" style="height: 51px !important;width: 217px !important;" ></a>

## Credits:

* Huge contirbutions from @firstof9 moving the project forward and keeping it active!
* Mail.py script based on @skalavala work at [skalavala blog](https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html)
* Package and macros based on happyleavesaoc work at [happyleavesaoc/my-home-automation](https://github.com/happyleavesaoc/my-home-automation)

## Installation
### [HACS](https://hacs.xyz) (Recommended)
0. Have [HACS](https://github.com/custom-components/hacs) installed, this will allow you to easily update
1. Add `https://github.com/moralmunky/Home-Assistant-Mail-And-Packages` as a [custom repository](https://custom-components.github.io/hacs/usage/settings/#add-custom-repositories) and Type: Integration
2. Click install under "Mail and Packages", restart your instance.

### Manual Installation
1. Download this repository as a ZIP (green button, top right) and unzip the archive
2. Copy the `mail_and_packages` folder inside the `custom_components` folder to the Home Assistant `<config_dir>/custom_components/` directory
   * You may need to create the `custom_components` in your Home Assistant installation folder if it does not exist
   * On HomeAssistant (formerly hass.io) the final location will be `/config/custom_components/mail_and_packages`
   * On Hassbian the final location will be `/home/homeassistant/.homeassistant/custom_components/mail_and_packages`
3. Restart your instance.

## Configuration
[Go to the Configuration, Templates, and Automations section](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/info.md#configuration)
