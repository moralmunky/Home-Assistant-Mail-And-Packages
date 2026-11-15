# Notification Examples

Automate notifications when mail or packages are scheduled for delivery today. Notifications can include text summaries from the [Mail Summary Message Wiki](Mail-Summary-Message) along with today's [USPS Informed Delivery mail scan image](USPS-Informed-Delivery-Image).

---

## Amazon Delivery Codes and Attempted Deliveries

Two Amazon recipes have their own page, [Amazon Delivery Confirmations](Amazon-Delivery-Confirmations):

- **Delivery code reminder** — announce the one-time password a driver needs, at the start of its delivery window (with a conditional dashboard card that shows the code only while it is needed).
- **Attempted delivery alert** — get notified when a delivery was attempted, with a dashboard card that clears itself once that order is delivered.

That page also covers exception tracking-number matching and the daily (midnight) reset behavior for delivery confirmations.

---

## Mobile App Notifications (iOS & Android)

This automation triggers when mail or package counts change and sends a push notification to your phone with an embedded image scan of today's mail.

```yaml
alias: "Mail and Packages - Delivery Notification"
description: "Send push notification when new mail or packages are detected"
trigger:
  - platform: state
    entity_id:
      - sensor.mail_usps_mail
      - sensor.mail_packages_in_transit
condition:
  - condition: template
    value_template: >-
      {{ states('sensor.mail_usps_mail') | int(0) > 0 or states('sensor.mail_packages_in_transit') | int(0) > 0 }}
action:
  - action: notify.mobile_app_your_phone
    data:
      title: "📬 Mail & Packages Update"
      message: >-
        {% set mail = states('sensor.mail_usps_mail') | int(0) %}
        {% set mail_delivered = is_state('binary_sensor.mail_usps_mail_delivered', 'on') %}
        {% set in_transit = states('sensor.mail_packages_in_transit') | int(0) %}
        {% set delivered = states('sensor.mail_packages_delivered') | int(0) %}
        {%- if mail == 0 -%}No mail today.
        {%- elif mail_delivered -%}{{ mail }} piece{{ 's' if mail != 1 }} of mail in the mailbox.
        {%- else -%}{{ mail }} piece{{ 's' if mail != 1 }} of mail arriving today.
        {%- endif %}
        {%- if in_transit > 0 %} {{ in_transit }} package{{ 's' if in_transit != 1 }} in transit.{% endif %}
        {%- if delivered > 0 %} {{ delivered }} package{{ 's' if delivered != 1 }} delivered.{% endif %}
      data:
        # iOS camera attachment
        entity_id: camera.mail_usps_camera
        # Android camera attachment
        image: "/api/camera_proxy/camera.mail_usps_camera"
```

---

## iOS Companion App Notification

Optimized for iOS devices with thread grouping, collapse ID, and a tap action that opens your Home Assistant mail dashboard view.

```yaml
alias: "Mail and Packages - iOS Rich Notification"
description: "Sends an iOS notification with mail scan attachment and collapse ID"
trigger:
  - platform: state
    entity_id: sensor.mail_usps_mail
condition:
  - condition: numeric_state
    entity_id: sensor.mail_usps_mail
    above: 0
action:
  - action: notify.mobile_app_your_iphone
    data:
      title: "📬 USPS Mail Arriving Today"
      message: "{{ states('sensor.mail_usps_mail') }} piece(s) of mail arriving."
      data:
        entity_id: camera.mail_usps_camera
        apns_headers:
          apns-collapse-id: "mail-and-packages-update"
        push:
          thread-id: "mail-and-packages"
        url: "/lovelace/mail"
```

---

## Android Companion App Notification

Optimized for Android devices with expandable image preview and a tap action to open the mail view.

```yaml
alias: "Mail and Packages - Android Rich Notification"
description: "Sends an Android notification with image preview"
trigger:
  - platform: state
    entity_id: sensor.mail_usps_mail
condition:
  - condition: numeric_state
    entity_id: sensor.mail_usps_mail
    above: 0
action:
  - action: notify.mobile_app_your_android_phone
    data:
      title: "📬 USPS Mail Arriving Today"
      message: "{{ states('sensor.mail_usps_mail') }} piece(s) of mail scheduled for delivery."
      data:
        image: "/api/camera_proxy/camera.mail_usps_camera"
        clickAction: "/lovelace/mail"
        group: "mail-and-packages"
```

---

## Smart Speaker Voice Announcement (TTS)

Announces today's deliveries over smart speakers (e.g. Google Home or Alexa) at a scheduled time.

```yaml
alias: "Mail and Packages - Morning TTS Announcement"
description: "Announces mail and package status at 9:00 AM"
trigger:
  - platform: time
    at: "09:00:00"
condition:
  - condition: template
    value_template: >-
      {{ states('sensor.mail_usps_mail') | int(0) > 0 or states('sensor.mail_packages_in_transit') | int(0) > 0 }}
action:
  - action: tts.speak
    target:
      entity_id: tts.google_en_com
    data:
      media_player_entity_id: media_player.living_room_speaker
      message: >-
        {% set mail = states('sensor.mail_usps_mail') | int(0) %}
        {% set packages = states('sensor.mail_packages_in_transit') | int(0) %}
        Good morning! You have
        {%- if mail > 0 %}{{ mail }} piece{{ 's' if mail != 1 }} of mail{% endif %}
        {%- if mail > 0 and packages > 0 %} and {% endif %}
        {%- if packages > 0 %}{{ packages }} package{{ 's' if packages != 1 }} in transit{% endif %}
        arriving today.
```

---

## Notes & Troubleshooting

 - **Camera Attachments (Recommended)**: Utilizing `camera.mail_usps_camera` via `entity_id` (iOS) or `/api/camera_proxy/camera.mail_usps_camera` (Android) provides instant local image attachments without needing external internet-accessible URLs.
 - **External URL / Remote Attachment**: You can attach the signed image URL using `url: "{{ state_attr('sensor.mail_image_url', 'image_url') }}"`. This URL is cryptographically signed with Home Assistant's token and valid for 24 hours (requires `External_URL` or `Internal_URL` to be configured in Home Assistant general settings).
 - Replace `notify.mobile_app_your_phone` with your actual Home Assistant notification device entity.
