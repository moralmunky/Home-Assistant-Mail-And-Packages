# HomeAssistant Mail and Packages

Card, Custom Component, and iOS Notification for getting UPS, USPS, and FedEx delivery information in Home Assistant.

Supports only Lovelace UI. Last tested in 0.93.1.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/mail_card_screenshot.jpg" alt="Preview of the custom mail card" width="350" />  <img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/notification_screenshot.jpg" alt="Preview of the custom mail card" width="350" />

## Credits:

* Mail Card based on Bram_Kragten work at [Home Assistant Community: Custom UI weather state card, with a question](https://community.home-assistant.io/t/custom-ui-weather-state-card-with-a-question/23008)
* Mail.py script based on @skalavala work at [skalavala blog](https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html)
* Package and macros based on happyleavesaoc work at [happyleavesaoc/my-home-automation](https://github.com/happyleavesaoc/my-home-automation)

## To Do:

*Gather the configuration options from the yaml configuration instead of hard coding it in the component
*Add UPS and FedEx reaady for pickup package count for packages that are being delivered to a package pick up location?
#Home Assistant Configuration

## Requirements:

[USPS Informed Delivery:](https://informeddelivery.usps.com/) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/USPS_Delivery_Notifications.jpg" alt="USPS Informed Delivery notification settings."  width="350"/>

[FedEx Delivery Manager:](https://www.fedex.com/apps/fdmenrollment/) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/FedEx_Delivery_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

[UPS MyChoice:](https://wwwapps.ups.com/mcdp?loc=en_US) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/UPS_My_Choice_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

imagemagick PIP packages are installed within the Home Assistant environment
```
sudo apt-get install imagemagick
```
In order to utilize the (more or less) drop in configration files provided you must have The Home Assistant must have [packages:](https://www.home-assistant.io/docs/configuration/packages/) defined wtihin the configuration.yaml.

Example:
```
homeassistant:
  packages: !include_dir_named includes/packages
```

## Upload Files

Upload the files into inside the Home Assistant .homeassistant/ folder as structured in the repository
```
.homeassistant/includes/packages/mail_package.yaml
.homeassistant/www/mail_and_packages/
.homeassistant/custom_compontents/mail_and_packages/
```

## mail_package.yaml
Adding your settings to the configuration file will be implimented in a later version. For now they need to be hard coded in the component files, see below. I save all of this information in the Secrets.yaml so the example configuration has the references to these variables.
```
Line 100 Add the mail host
Line 101 Add the port used to connect
Line 102 Email account username
Line 103 Email account passowrd
Line 104 The name of the folder the email notification are delivered to
Line 105 The full path to the www/mail_and_packages/ folder
```
## Lovelace GUI Setup

Add the js path relative to the /local/ path to the resources section of the lovelace yaml or at the top of the GUI lovelace RAW configuration editor.
```
resources:
  - type: js
    url: /local/mail_card/mail_and_packages.js?v=.01
```
Add the card configuration to the cards: section of the view you want to display the card in.
```
  - type: 'custom:mail-and-packages'
    deliver_today: sensor.mail_deliveries_today
    fedex: sensor.mail_fedex_packages
    in_transit: sensor.mail_packages_in_transit
    last_update: sensor.mail_updated
    mail: sensor.mail_usps_mail
    summary: sensor.mail_deliveries_message
    ups: sensor.mail_ups_packages
    usps: sensor.mail_usps_packages
```

## Setup custom_components/mail_and_Packages/sensor.py file

Note: These configurations will eventually be moved into the components configruation file.
Enter the details for the following variables used in the file

Configuration Details
```
Line 19 The frequency in minutes the account is checked for new emails
Line 22 Add the mail host
Line 23 Add the port used to connect
Line 24 Email account username
Line 25 Email account passowrd
Line 26 The name of the folder the email notification are delivered to
Line 27 The full path to the www/mail_and_packages/ folder

```
