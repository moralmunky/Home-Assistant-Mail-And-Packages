{% if prerelease %}
### This is a pre-release version
It may contain bugs or break functionality in addition to adding new features and fixes. Please review open issues and submit new issues to the [GitHub issue tracker](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/issues).
{% endif %}

## About Mail and Packages integration

The [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) creates sensors for supported shippers to show a snapshot of mail and packages that are scheduled to be delivered the current day. It provides a count of in transit and delivered packages that are scheduled to be delivered the current day. It also generates the number of USPS mail pieces and provides a rotating GIF of the USPS provided images of the mail, if available, for the current day.

#### How it works

From your instance of HASS, the [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) connects to the email account you supply where your shipment notifications are sent. It reviews at the subject lines of the current day's emails from the shipping companies and counts the subject lines that match known language from the shipping companies about their trasnit status. For USPS Informed delivery emails, it also downloads the mail images to combine them into a rotating GIF.

* **All procedures are done locally on your machine.**
* **No external services are used to process your email.**
* **No data is sent outside of your local instance of Home Assistant**


<a href="https://www.buymeacoffee.com/Moralmunky" target="_blank"><img src="/docs/coffee.png" alt="Buy Us A Coffee" height="51px" width="217px" /></a>

## Configuration
Once you have finished installing through [HACS or manually](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages#installation) go into ```Configuration -> Integration``` select the ```+```and add the ```Mail And Packages``` integration. You first be prompted to input your mail server settings and then additonal settings.

Setting | Description
--- | ---
Mail Folder| The folder in your email account that the notification messages are stored. The default is Inbox.
<nobr>Scanning Interval (minutes)</nobr>| The amount of time that will pass between checking for new email nortifications
Image Path* | This is the absolute path to the folder where [Mail and Packages integration](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages) will save the compiled USPS informed delivery gif.
<nobr>Image Duration (seconds)</nobr> | The amount of time each USPS Informed Delivery image is shown in the generated rotating GIF.
<nobr>Random Image Filename*</nobr> | Change the file name of the generated gif from mail_today.gif to a random string for increased secuirty in situations where it is required to store the  image in the ```www``` directory

##### *Privacy / Security Note
Please note that files stored in the ```www``` Home Assistant folder is [publicly accessible](https://www.home-assistant.io/integrations/http/#hosting-files) unless you have taken security measures outside of Home Assistant to secure it. You can place the images in an ```images``` directory inside Home Assistants root folder and still send notifications via most notification integrations.

### Supported Shippers and Requirements:
Shipper | Notification Settings
------------ | -------------
[USPS Informed Delivery:](https://informeddelivery.usps.com/) account and all nortifications turned on for email with the email address you will have the component check.|<img src="/docs/USPS_Delivery_Notifications.jpg" alt="USPS Informed Delivery notification settings."  width="350"/>
[FedEx Delivery Manager:](https://www.fedex.com/apps/fdmenrollment/) account and all nortifications turned on for email with the email address you will have the component check.|<img src="/docs/FedEx_Delivery_Notifications.jpg" alt="FedEx notification settings."  width="350"/>
[UPS MyChoice:](https://www.ups.com/us/en/services/tracking/mychoice.page) account and all nortifications turned on for email with the email address you will have the component check.|<img src="/docs/UPS_My_Choice_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

## Delivery Summary Text Sensor Template (example)
Use the following to create a sensor with summary text describing the state of your deliveries that can be used in your Lovelace cards or in notifications. Add to the ```sensor:``` portion of the configuartion.yaml.
```
- platform: template
  sensors:
    mail_deliveries_message:
      friendly_name: "Deliveries Summary"
      entity_id: 
        - sensor.mail_usps_mail
        - sensor.mail_usps_delivering
        - sensor.mail_fedex_delivering
        - sensor.mail_ups_delivering
      value_template: > 
        {# Deliveries Sentence #}
          {% macro deliveries_sentence() -%}
                {%- if states("sensor.mail_usps_mail")|int == 0 -%}
                  No
                {%- else -%}
                  {{states("sensor.mail_usps_mail")|int}}
                {%- endif -%}
              {{' '}} 
                {%- if states("sensor.mail_usps_mail")|int <= 1 -%}
                  pieces of mail
                {%- else -%}
                  pieces of mail
                {%- endif -%}
              {{' '}}will be delivered.{{' '}} 
                {%- if states("sensor.mail_usps_delivering")|int == 0 -%}
                  No
                {%- else -%}
                  {{states("sensor.mail_usps_delivering")|int}}
                {%- endif -%}
              {{' '}} 
                {%- if states("sensor.mail_usps_delivering")|int == 1 -%}
                  USPS package is
                {%- else -%}
                  USPS packages are
                {%- endif -%}
              {{' '}}in transit.{{' '}}
                {%- if states("sensor.mail_fedex_delivering")|int == 0 -%}
                  No
                {%- else -%}
                  {{states("sensor.mail_fedex_delivering")|int}}
                {%- endif -%}
              {{' '}} 
                {%- if states("sensor.mail_fedex_delivering")|int == 1 -%}
                  FedEx package is
                {%- else -%}
                  Fedex packages are
                {%- endif -%}
              {{' '}}in transit.{{' '}}
              {%- if states("sensor.mail_ups_delivering")|int == 0 -%}
                  No
                {%- else -%}
                  {{states("sensor.mail_ups_delivering")|int}}
                {%- endif -%}
              {{' '}} 
                {%- if states("sensor.mail_ups_delivering")|int == 1 -%}
                  UPS package is
                {%- else -%}
                  UPS packages are
                {%- endif -%}
              {{' '}}in transit.{{' '}}
              {%- if states("sensor.mail_amazon_packages")|int == 0 -%}
                  No
                {%- else -%}
                  {{states("sensor.mail_amazon_packages")|int}}
                {%- endif -%}
              {{' '}} 
                {%- if states("sensor.mail_amazon_packages")|int == 1 -%}
                  Amazon package is
                {%- else -%}
                  Amazon packages are
                {%- endif -%}
              {{' '}}in transit.{{' '}}
          {%- endmacro %}
        {{deliveries_sentence()}}
```
### Camera
You may also want to add a camera to display the image.  Add to the ```camera:``` portion of configuration.yaml.
```
  - platform: local_file
    file_path: /<config path>/images/mail_and_packages/mail_today.gif
    name: mail_usps
```
### Notification Automation
```
- alias: "Mail Notif - Mail Delieveries"
  initial_state: 'on'
  trigger:
  #Trigger if mail or packages get updated
    - platform: state
      entity_id: sensor.mail_usps_mail
    - platform: state
      entity_id: sensor.mail_usps_delivering
  #send only if mail or packages are more than 0
  condition:
    - condition: or
      conditions:
        - condition: template
          value_template: "{{ states('sensor.mail_usps_mail') | int > 0 }}"
        - condition: template
          value_template: "{{ states('sensor.mail_usps_delivering') | int > 0 }}"
  action:
    - service: notify.YOUR_NOTIFY_METHOD
      data_template:
        title: "*Today's Mail and Packages*"
        message: "{{ states('sensor.mail_deliveries_message')}}"
    - service: notify.YOUR_NOTIFY_METHOD
      data:
        message: "Here is the mail"
        data:
          document:
            file: "/<config path>/images/mail_and_packages/mail_today.gif"
```
## Lovelace Custom Card Setup

You can create your own card using the entities generated by the integration and the front end Lovelace editor provided by Home Assistant. A few options provided by the community are provided below.

**Note:** The local file camera reloads the file after 10 seconds. If the gif is langer than 10 seconds not all mail with be shown. Please use a [picture entity card](https://www.home-assistant.io/lovelace/picture-entity/) with the camera view set to live.

### Option 1: Lovelace Manual Card
```
type: vertical-stack
cards:
  - type: picture-entity
    entity: camera.mail_usps
    aspect_ratio: 50%
    name: Mail
    camera_view: live
    show_name: false
    show_state: false
  - type: entity-filter
    state_filter:
      - operator: '>'
        value: '0'
    entities:
      - entity: sensor.mail_usps_mail
        name: USPS Mail
      - entity: sensor.mail_usps_packages
        name: USPS Packages
      - entity: sensor.fedex_packages
        name: FedEx Packages
      - sensor.mail_ups_packages
      - sensor.mail_packages_in_transit
      - sensor.mail_packages_delivered
      - entity: sensor.mail_updated


```
### Option 2: [Vertical Stack Custom Card](https://github.com/ofekashery/vertical-stack-in-card)
```
- type: custom:vertical-stack-in-card
      title: Mail & Package Tracking
      cards:
        - aspect_ratio: 50%
          camera_view: live
          entity: camera.mail_usps
          name: Mail
          type: picture-entity
        - type: entity-filter
          state_filter:
            - operator: ">"
              value: '0'
          entities:
           - entity: sensor.mail_usps_mail
             name: "Today's Mail"
           - entity: sensor.mail_packages_in_transit
             name: "Today's Package Delivery"
           - entity: sensor.mail_usps_delivering
             icon: 'mdi:package-variant-closed'
             name: USPS
           - entity: sensor.mail_fedex_delivering
             icon: 'mdi:package-variant-closed'
             name: FedEx
           - entity: sensor.mail_ups_delivering
             icon: 'mdi:package-variant-closed'
             name: UPS
           - entity: sensor.mail_updated
             state_filter:
               - operator: "regex"
                 value: 20
```
### Option 3: [Vertical Stack Custom Card](https://github.com/ofekashery/vertical-stack-in-card)
```
cards:
  - cards: null
    entities:
      - entity: sensor.mail_usps_mail
        name: Todays USPS Mail
      - entity: sensor.mail_packages_in_transit
        name: Todays Package Delivery
    type: entities
  - cards: null
    entities:
      - entity: sensor.mail_usps_delivering
        icon: 'mdi:package-variant-closed'
        name: USPS
      - entity: sensor.mail_fedex_delivering
        icon: 'mdi:package-variant-closed'
        name: FedEx
      - entity: sensor.mail_ups_delivering
        icon: 'mdi:package-variant-closed'
        name: UPS
    show_header_toggle: false
    type: glance
  - aspect_ratio: 50%
    camera_view: live
    entity: camera.mail_usps
    name: Mail
    type: picture-entity
  - cards: null
    entities:
      - entity: sensor.mail_updated
    type: entities
title: Mail & Package Tracking
type: 'custom:vertical-stack-in-card'
```
 ### Option 4: [Mail and Packages Custom Card](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages-Custom-Card)
 ![Card screenshot](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages-Custom-Card/raw/master/card-image.png "Card screenshot")
 