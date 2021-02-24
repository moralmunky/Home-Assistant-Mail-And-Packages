![GitHub release (latest by date)](https://img.shields.io/github/v/release/moralmunky/Home-Assistant-Mail-And-Packages)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

![GitHub contributors](https://img.shields.io/github/contributors/moralmunky/Home-Assistant-Mail-And-Packages)
![Maintenance](https://img.shields.io/maintenance/yes/2020)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub last commit](https://img.shields.io/github/last-commit/moralmunky/Home-Assistant-Mail-And-Packages)

## About Mail and Packages integration

The [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) creates sensors for [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements) to show a snapshot of mail and **packages that are scheduled to be delivered the current day**. For the packages that are scheduled for delivery the current day a count of in transit and delivered packages will be provided. It also generates the number of USPS mail pieces and provides a rotating GIF of the USPS provided images of the mail, if available, for the current day.

## Credits:

- Huge contributions from [@firstof9](https://github.com/firstof9) moving the project forward and keeping it active!
<br/>
<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>


## How it works

From your instance of HASS, the [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to the email account you supply where your shipment notifications are sent. It reviews at the subject lines of the current day's emails from the [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements) and counts the subject lines that match known language from the [supported shippers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements) about their transit status. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

_**The email can not be deleted until the next day**_. You can have your email filtered into a folder and have the integration watch that folder.

The image will revert back to the no mail graphic after the first email check after midnight, local time.

##### *Privacy / Security Note
Please note that files stored in the ```www``` Home Assistant folder is [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) unless you have taken security measures outside of Home Assistant to secure it. You can place the images in an ```images``` directory inside Home Assistants root folder and still send notifications via most notification integrations.

See the WIKI [information on how this works](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki).

## Support
[Configuring the integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings)

[Supported Shippers and Requirements](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Supported-Shipper-Requirements)

[Troubleshooting](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Troubleshooting)


### Templates and Examples
[USPS Informed Delivery](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/USPS-Informed-Delivery-Image)

[Text Summary](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Mail-Summary-Message)

[Notifications](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Notifications)