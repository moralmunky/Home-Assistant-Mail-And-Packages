{% if prerelease %}
### This is a pre-release version
It may contain bugs or break functionality in addition to adding new features and fixes. Please review open issues and submit new issues to the [GitHub issue tracker](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/issues).

{% endif %}

![GitHub release (latest by date)](https://img.shields.io/github/v/release/moralmunky/Home-Assistant-Mail-And-Packages)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
![GitHub contributors](https://img.shields.io/github/contributors/moralmunky/Home-Assistant-Mail-And-Packages)
![Maintenance](https://img.shields.io/maintenance/yes/2020)
![GitHub commit activity](https://img.shields.io/github/commit-activity/m/moralmunky/Home-Assistant-Mail-And-Packages)
![GitHub last commit](https://img.shields.io/github/last-commit/moralmunky/Home-Assistant-Mail-And-Packages)

## About Mail and Packages integration

The [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) creates sensors for supported shippers to show a snapshot of mail and packages that are scheduled to be delivered the current day. It provides a count of in transit and delivered packages that are scheduled to be delivered the current day. It also generates the number of USPS mail pieces and provides a rotating GIF of the USPS provided images of the mail, if available, for the current day.
<br />
<br />
<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/docs/coffee.png?raw=true" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## How it works

From your instance of HASS, the [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to the email account you supply where your shipment notifications are sent. It reviews at the subject lines of the current day's emails from the shipping companies and counts the subject lines that match known language from the shipping companies about their transit status. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

* **All procedures are done locally on your machine.**
* **No external services are used to process your email.**
* **No data is sent outside of your local instance of Home Assistant**

#### Search Terms

Sensors | Shipper | Email | Subject | Body Text
--- | --- | --- | --- | ---
sensor.mail_usps_mail, mail_today.gif |USPS | USPSInformedDelivery@usps.gov|Informed Delivery Daily Digest|none
sensor.mail_usps_delivering |USPS | auto-reply@usps.com|Expected Delivery on|out for delivery
sensor.mail_usps_delivered |USPS | auto-reply@usps.com|Item Delivered|none
sensor.mail_ups_delivering |UPS | mcinfo@ups.com|UPS Update: Package Scheduled for Delivery Today|none
sensor.mail_ups_delivering |UPS | mcinfo@ups.com|UPS Update: Follow Your Delivery on a Live Map|none
sensor.mail_ups_delivered |UPS | mcinfo@ups.com|Your UPS Package was delivered|none
sensor.mail_fedex_delivering |FEDEX | TrackingUpdates@fedex.com |Delivery scheduled for today|none
sensor.mail_fedex_delivering |FEDEX | TrackingUpdates@fedex.com |Your package is scheduled for delivery today|none
sensor.mail_fedex_delivered |FEDEX | TrackingUpdates@fedex.com |Your package has been delivered|none
sensor.mail_amazon_packages |Amazon |shipment-tracking@amazon.com|none|regex order numbers
sensor.mail_amazon_packages |Amazon |shipment-tracking@amazon.ca|none |regex order numbers

## Configuration
Once you have finished installing through [HACS or manually](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages#installation) go into ```Configuration -> Integration``` select the ```+```and add the ```Mail And Packages``` integration. You first be prompted to input your mail server settings and then additonal settings.

Setting | Description
--- | ---
Mail Folder| The folder in your email account that the notification messages are stored. The default is Inbox.
<nobr>Scanning Interval (minutes)</nobr>| The amount of time that will pass between checking for new email notifications
Image Path* | This is the absolute path to the folder where [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) will save the compiled USPS informed delivery gif.
<nobr>Image Duration (seconds)</nobr> | The amount of time each USPS Informed Delivery image is shown in the generated rotating GIF.
<nobr>Random Image Filename*</nobr> | Change the file name of the generated gif from mail_today.gif to a random string for increased secuirty in situations where it is required to store the  image in the ```www``` directory

##### *Privacy / Security Note
Please note that files stored in the ```www``` Home Assistant folder is [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) unless you have taken security measures outside of Home Assistant to secure it. You can place the images in an ```images``` directory inside Home Assistants root folder and still send notifications via most notification integrations.

### Supported Shippers and Requirements:
Shipper | Notification Settings
------------ | -------------
[USPS Informed Delivery:](https://informeddelivery.usps.com/) account and all notifications turned on for email with the email address you will have the component check.|<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/raw/master/docs/USPS_Delivery_Notifications.jpg" alt="USPS Informed Delivery notification settings."  width="350"/>
[FedEx Delivery Manager:](https://www.fedex.com/apps/fdmenrollment/) account and all notifications turned on for email with the email address you will have the component check.|<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/raw/master/docs/FedEx_Delivery_Notifications.jpg" alt="FedEx notification settings."  width="350"/>
[UPS MyChoice:](https://www.ups.com/us/en/services/tracking/mychoice.page) account and all notifications turned on for email with the email address you will have the component check.|<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/raw/master/docs/UPS_My_Choice_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

## Automation and Template Examples
[Go to the Example Automations and Templates wiki section](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Example-Automations-and-Templates#delivery-summary-text-sensor-template-example)
