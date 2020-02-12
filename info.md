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