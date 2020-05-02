## Requirements:

[USPS Informed Delivery:](https://informeddelivery.usps.com/) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/USPS_Delivery_Notifications.jpg" alt="USPS Informed Delivery notification settings."  width="350"/>

[FedEx Delivery Manager:](https://www.fedex.com/apps/fdmenrollment/) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/FedEx_Delivery_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

[UPS MyChoice:](https://wwwapps.ups.com/mcdp?loc=en_US) account and all nortifications turned on for email with the email address you will have the component check.

<img src="https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/blob/master/UPS_My_Choice_Notifications.jpg" alt="FedEx notification settings."  width="350"/>

### [Docs (installation, config, and issues)](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages)

## Message Sensor Template (example)
Use the following to create a deliveries summary sensor:
```
- platform: template
  sensors:
    mail_deliveries_message:
      friendly_name: "Deliveries Summary"
      entity_id: 
        - sensor.mail_usps_mail
        - sensor.packages_in_transit
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
                  mail
                {%- else -%}
                  pieces of mail
                {%- endif -%}
              {{' '}}will be delivered.{{' '}} 
                {%- if states("sensor.packages_in_transit")|int == 0 -%}
                  No
                {%- else -%}
                  {{states("sensor.packages_in_transit")|int}}
                {%- endif -%}
              {{' '}} 
                {%- if states("sensor.packages_in_transit")|int == 1 -%}
                  package is
                {%- else -%}
                  packages are
                {%- endif -%}
              {{' '}}in transit.{{' '}}
          {%- endmacro %}
        {{deliveries_sentence()}}
```
## Lovelace Custom Card Setup

A few options here as provided by the community:
Note: The local file camera reloads the file after 10 seconds. If the gif is langer than 10 seconds not all mail with be shown. Please use a [picture entity card](https://www.home-assistant.io/lovelace/picture-entity/) with the camera view set to live.

### Option 1 (requires [vertical stack in card custom card](https://github.com/ofekashery/vertical-stack-in-card))
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
### Option 2 (also requires vertical stack in card)
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
### Option 3 (no custom card required)
```
 - cards:
    - aspect_ratio: 50%
      camera_view: live
      entity: camera.mail_usps
      name: Mail
      type: picture-entity
    - entities:
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
          state_filter:
            - operator: regex
              value: 20
      state_filter:
        - operator: '>'
          value: '0'
      type: entity-filter
  title: Mail Today
  type: vertical-stack
```
