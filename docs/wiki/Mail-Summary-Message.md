# Delivery Summary Sensor

The integration does not include a built-in text summary sensor — this lets you customize the message for the delivery services you have configured and the style you prefer. Create one as a template sensor through the Home Assistant UI.

1. Go to **Settings** → **Devices & services** → **Helpers**
2. Click **+ Create helper**
3. Select **Template**
4. Choose **Template a sensor**
5. Enter a **Name** for the sensor (e.g. `Deliveries Summary`)
6. Paste one of the templates below into the **State template** field
7. Click **Submit** / **Save**

The entity ID will be generated from the name you provide (e.g. `sensor.deliveries_summary`).

> [!NOTE]
> Home Assistant entity states are limited to **255 characters**. If your custom summary exceeds this limit, paste the Jinja code directly into a Dashboard **Markdown Card** or an **Automation Action** (such as a push notification or TTS alert) instead of creating a template sensor.

---

## Simple Summary (Voice & TTS)

Shows mail status and a combined package count with natural phrasing. Ideal for TTS voice announcements (Alexa, Google Assistant) and simple push notifications.

```jinja2
{% set mail = states('sensor.mail_usps_mail') | int(0) %}
{% set mail_delivered = is_state('binary_sensor.mail_usps_mail_delivered', 'on') %}
{% set in_transit = states('sensor.mail_packages_in_transit') | int(0) %}
{% set delivered = states('sensor.mail_packages_delivered') | int(0) %}

{%- if mail == 0 -%}
  No mail today.
{%- elif mail_delivered -%}
  {{ mail }} piece{{ 's' if mail != 1 }} of mail in the mailbox.
{%- else -%}
  {{ mail }} piece{{ 's' if mail != 1 }} of mail arriving today.
{%- endif %}

{%- if in_transit > 0 or delivered > 0 %} {{ '' }}
  {%- if in_transit > 0 and delivered > 0 -%}
    {{ in_transit }} package{{ 's' if in_transit != 1 }} in transit and {{ delivered }} delivered.
  {%- elif in_transit > 0 -%}
    {{ in_transit }} package{{ 's' if in_transit != 1 }} in transit.
  {%- else -%}
    {{ delivered }} package{{ 's' if delivered != 1 }} delivered.
  {%- endif -%}
{%- else -%}
  {{ '' }} No packages today.
{%- endif -%}
```

**Example output:**
> *2 pieces of mail arriving today. 3 packages in transit and 1 delivered.*

---

## Detailed Summary (Per-Carrier Breakdown)

Shows mail status, total packages in transit broken down by shipper, and delivered package counts. Easily add or remove shippers by editing the `carriers` list at the top.

```jinja2
{% set mail = states('sensor.mail_usps_mail') | int(0) %}
{% set mail_delivered = is_state('binary_sensor.mail_usps_mail_delivered', 'on') %}
{% set in_transit = states('sensor.mail_packages_in_transit') | int(0) %}
{% set delivered = states('sensor.mail_packages_delivered') | int(0) %}

{%- set carriers = [
  ('sensor.mail_usps_delivering', 'USPS'),
  ('sensor.mail_fedex_delivering', 'FedEx'),
  ('sensor.mail_ups_delivering', 'UPS'),
  ('sensor.mail_amazon_packages', 'Amazon'),
  ('sensor.mail_walmart_delivering', 'Walmart'),
  ('sensor.mail_dhl_delivering', 'DHL')
] %}

{%- set active_carriers = namespace(list=[]) %}
{%- for sensor, name in carriers %}
  {%- set count = states(sensor) | int(0) %}
  {%- if count > 0 %}
    {%- set active_carriers.list = active_carriers.list + [name ~ ': ' ~ count] %}
  {%- endif %}
{%- endfor %}

{%- if mail == 0 -%}
  No mail today.
{%- elif mail_delivered -%}
  {{ mail }} piece{{ 's' if mail != 1 }} of mail in the mailbox.
{%- else -%}
  {{ mail }} piece{{ 's' if mail != 1 }} of mail arriving today.
{%- endif %}

{{- ' ' }}
{%- if in_transit == 0 -%}
  No packages in transit.
{%- else -%}
  {{- in_transit }} package{{ 's' if in_transit != 1 }} in transit
  {%- if active_carriers.list | length > 0 %} ({{ active_carriers.list | join(', ') }}){% endif -%}.
{%- endif %}

{%- if delivered > 0 %} {{ delivered }} package{{ 's' if delivered != 1 }} delivered.{% endif %}
```

**Example output:**
> *2 pieces of mail arriving today. 3 packages in transit (USPS: 1, FedEx: 2). 1 package delivered.*

---

## Dashboard Markdown Card

A formatted version with bullet points and emojis, perfect for use in a Lovelace **Markdown Card**.

```jinja2
### 📬 Mail & Packages Summary

{% set mail = states('sensor.mail_usps_mail') | int(0) %}
{% set mail_delivered = is_state('binary_sensor.mail_usps_mail_delivered', 'on') %}
{% set in_transit = states('sensor.mail_packages_in_transit') | int(0) %}
{% set delivered = states('sensor.mail_packages_delivered') | int(0) %}

- **Mail:** {% if mail == 0 %}No mail today{% elif mail_delivered %}{{ mail }} piece{{ 's' if mail != 1 }} in mailbox 📬{% else %}{{ mail }} piece{{ 's' if mail != 1 }} arriving today ✉️{% endif %}
- **In Transit:** {{ in_transit }} package{{ 's' if in_transit != 1 }} 🚚
- **Delivered:** {{ delivered }} package{{ 's' if delivered != 1 }} 📦

{% set carriers = [
  ('sensor.mail_usps_delivering', 'USPS'),
  ('sensor.mail_fedex_delivering', 'FedEx'),
  ('sensor.mail_ups_delivering', 'UPS'),
  ('sensor.mail_amazon_packages', 'Amazon'),
  ('sensor.mail_walmart_delivering', 'Walmart'),
  ('sensor.mail_dhl_delivering', 'DHL')
] %}
{% set active_carriers = namespace(list=[]) %}
{% for sensor, name in carriers %}
  {% set count = states(sensor) | int(0) %}
  {% if count > 0 %}
    {% set active_carriers.list = active_carriers.list + [name ~ ': ' ~ count] %}
  {% endif %}
{% endfor %}
{% if active_carriers.list | length > 0 %}
*Breakdown:* {{ active_carriers.list | join(' • ') }}
{% endif %}
```

---

## Notes

- `int(0)` is used throughout so the sensor degrades gracefully when the integration is unavailable rather than showing an error.
- `is_state()` is used for the binary sensor check rather than comparing the state string directly — this is the recommended approach in Home Assistant templates.
- The `carriers` list in the detailed template makes it easy to add or remove shippers depending on your setup.
- `binary_sensor.mail_usps_mail_delivered` must be enabled for the mailbox-delivered state to work. It is disabled by default — enable it under **Settings** → **Devices & services** → **Integrations** → **Mail and Packages** → **entities**.
