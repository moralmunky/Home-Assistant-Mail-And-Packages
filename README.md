# HomeAssistant Mail and Packages

Card, Custom Component, and iOS Notification for getting UPS, USPS, and FedEx delivery information in Home Assistant. This component only shows a snapshot of the current days packages that are in transit for delviery on the current day or have already been deliveredon in the current day. It also generates the number of USPS mail pieces and images (if avaiable) for the current day.

The component conencts to the email account you supply where your shipment notifcations are deleivers. It looks at the subject lines of the current days emails from the shipping companies. It counts the subject line matches to the known standard subject lines from the shipping companies. For USPS informed delviery emails, it also downloads the mail images to combined them into a rotating GIF.

All procedures are done locally on your machine.

Supports only Lovelace UI. Last tested in 0.95.4.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/mail_card_screenshot.jpg" alt="Preview of the custom mail card" width="350" />  <img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/notification_screenshot.jpg" alt="Preview of the custom mail card" width="350" />

## Credits:

* Mail Card based on Bram_Kragten work at [Home Assistant Community: Custom UI weather state card, with a question](https://community.home-assistant.io/t/custom-ui-weather-state-card-with-a-question/23008)
* Mail.py script based on @skalavala work at [skalavala blog](https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html)
* Package and macros based on happyleavesaoc work at [happyleavesaoc/my-home-automation](https://github.com/happyleavesaoc/my-home-automation)

## Requirements:

[USPS Informed Delivery:](https://informeddelivery.usps.com/) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/USPS_Delivery_Notifications.jpg" alt="USPS Informed Delivery notification settings."  width="350"/>

[FedEx Delivery Manager:](https://www.fedex.com/apps/fdmenrollment/) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/FedEx_Delivery_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

[UPS MyChoice:](https://wwwapps.ups.com/mcdp?loc=en_US) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/UPS_My_Choice_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

[imagemagick](https://imagemagick.org/script/download.php) packages are installed within the Home Assistant environment

In order to utilize the (more or less) drop in configration files provided you must have [packages:](https://www.home-assistant.io/docs/configuration/packages/) defined wtihin the configuration.yaml.

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
## Lovelace GUI Setup

Add the js path relative to the /local/ path to the resources section of the lovelace yaml or at the top of the GUI lovelace RAW configuration editor.
```
resources:
  - type: js
    url: /local/mail_and_packages/mail_and_packages.js?v=.01
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

## FOR FUTURE IMPLEMENTATION ##
## mail_package.yaml
Adding your settings to the configuration file.
```
sensor:
  - platform: mail_and_packages
    host: 'mail_host'
    username: 'mail_username'
    password: 'mail_password' 
```

Optional configutation options
    
    port: 'mail_port'
    Default is 993
    
    folder: 'Inbox'
    Default is Inbox
    
    image_output_path: 'mail_image_output_path'
    Default is /home/homeassistant/.homeassistant/www/mail_and_packages/
