# Amazon Delivery Confirmations

Recipes and sensor reference for the Amazon delivery-confirmation
additions: one-time-password (OTP) delivery codes, attempted
(missed) deliveries, and the exception matching that lets a card or
automation clear itself once a package finally lands.

These sensors match a delivery across its whole email lifecycle by
**order number** (Amazon) or **tracking number** (other carriers).
Support is not uniform across carriers — see the
[Delivery Confirmation Support Matrix](Supported-Shipper-Requirements#delivery-confirmation-support-matrix)
before building recipes for another carrier.

> **Entity IDs:** The examples below use the default entity IDs
> (for example `sensor.mail_amazon_otp_code`). If your mailbox host
> adds a suffix to your entity IDs, adjust them to match your
> install.

---

## Enable the sensors first

None of these sensors exist until they are selected:

**Settings → Devices & Services → Mail and Packages → Configure**,
then tick the sensors you want in the **Sensor List**:

- **Mail Amazon OTP Code** — the code sensor, with attributes.
- **Mail Amazon Delivery Code** — the first code as a plain string.
- **Mail Amazon Delivery Window Start** / **Mail Amazon Delivery
  Window End** — the window bounds as `timestamp` sensors.
- **Mail Amazon Attempted** — attempted-delivery count and orders.
- **Mail Amazon Delivered** and **Mail Amazon Exception** — if you
  do not already use them; the attempted-delivery recipes below
  read the delivered sensor's `order` attribute.

---

## Amazon one-time-password (OTP) deliveries

Some Amazon deliveries need a one-time password that you give the
driver in person. When an "Out for delivery" email for such a
delivery arrives, the integration extracts the code and its
delivery window.

### Sensors

| Sensor | Entity | State | Notes |
| --- | --- | --- | --- |
| Mail Amazon OTP Code | `sensor.mail_amazon_otp_code` | Count of today's deliveries that need a code | Carries the attributes below |
| Mail Amazon Delivery Code | `sensor.mail_amazon_delivery_code` | Today's first code, as a string | `unknown` when no code is needed today |
| Mail Amazon Delivery Window Start | `sensor.mail_amazon_delivery_window_start` | Timestamp of the window start | `unknown` when there is no code today |
| Mail Amazon Delivery Window End | `sensor.mail_amazon_delivery_window_end` | Timestamp of the window end | `unknown` when there is no code today |

Attributes on **Mail Amazon OTP Code**:

| Attribute | Meaning |
| --- | --- |
| `code` | List of today's codes (several deliveries can need a code on the same day) |
| `order` | List of the order numbers those codes belong to |
| `delivery_date` | Date of the first code delivery, e.g. `2026-11-06` |
| `delivery_window` | Window as written in the email, e.g. `1 PM - 4 PM` |
| `delivery_window_start` | Window start in 24-hour form, e.g. `13:00` |
| `delivery_window_end` | Window end in 24-hour form, e.g. `16:00` |

The window and code sensors above carry a single (first) delivery
as their state, which is what makes the simple automation below
possible. The attribute-based versions further down keep working
with the OTP Code sensor alone.

### Automation: announce the code when the window starts (native sensors)

With the window-start timestamp sensor enabled, a `time` trigger
does the whole job:

```yaml
alias: Amazon delivery code reminder
triggers:
  - trigger: time
    at: sensor.mail_amazon_delivery_window_start
conditions:
  - condition: template
    value_template: >-
      {{ (state_attr('sensor.mail_amazon_otp_code', 'code') or []) | count > 0 }}
actions:
  - action: notify.notify
    data:
      title: Amazon driver may arrive now
      message: >-
        Delivery window {{ state_attr('sensor.mail_amazon_otp_code', 'delivery_window') }}.
        Give the driver code {{ state_attr('sensor.mail_amazon_otp_code', 'code') | first }}.
mode: single
```

### Automation: announce the code (OTP Code sensor only)

If you only enabled the OTP Code sensor, trigger when the window
**has started**, not when a clock string matches. A template
trigger fires when its result turns true, so this fires once at
the window start — or immediately, if the email was processed
after the window already started (scan interval, late email, or a
restart). It re-arms after the midnight reset clears the
attributes.

```yaml
alias: Amazon delivery code reminder
triggers:
  - trigger: template
    value_template: >
      {% set e = 'sensor.mail_amazon_otp_code' %}
      {% set s = state_attr(e, 'delivery_window_start') %}
      {{ s is not none
         and state_attr(e, 'delivery_date') == now().date().isoformat()
         and (state_attr(e, 'code') or []) | count > 0
         and now() >= today_at(s) }}
actions:
  - action: notify.notify
    data:
      title: Amazon driver may arrive now
      message: >
        Delivery window {{ state_attr('sensor.mail_amazon_otp_code', 'delivery_window') }}.
        Give the driver code {{ state_attr('sensor.mail_amazon_otp_code', 'code') | first }}.
mode: single
```

### Dashboard card: show the code only while it is needed

Uses a numeric condition — `unknown` and `unavailable` do not
satisfy `above: 0`, so the card stays hidden after a restart or
while the integration is down — and a markdown card, which shows
the attributes directly:

```yaml
type: conditional
conditions:
  - condition: numeric_state
    entity: sensor.mail_amazon_otp_code
    above: 0
card:
  type: markdown
  title: Amazon delivery code needed today
  content: >
    **Code:** {{ state_attr('sensor.mail_amazon_otp_code', 'code') | first }}

    **Window:** {{ state_attr('sensor.mail_amazon_otp_code', 'delivery_window') }}

    Give this code to the driver in person.
```

If an entities card is preferred, every attribute row needs
`type: attribute`, or Home Assistant shows the entity state (the
count) instead of the attribute:

```yaml
  type: entities
  entities:
    - type: attribute
      entity: sensor.mail_amazon_otp_code
      attribute: delivery_window
      name: Delivery window
```

---

## Amazon attempted (missed) deliveries

When Amazon emails "Delivery attempted", the **Mail Amazon
Attempted** sensor counts today's attempted-delivery emails and
exposes the attempted order numbers on its `order` attribute:

| Sensor | Entity | State | Attributes |
| --- | --- | --- | --- |
| Mail Amazon Attempted | `sensor.mail_amazon_attempted` | Count of today's "Delivery attempted" emails that carry an order number | `order` — the attempted order numbers |

**Mail Amazon Delivered** (`sensor.mail_amazon_delivered`) exposes
its order numbers on its own `order` attribute the same way.
Comparing the two lists is how a recipe knows an attempted order
is still outstanding — and clears itself once that order is
delivered.

### Template helper: attempted orders still outstanding

Create this template sensor (via YAML, or as a Template helper in
**Settings → Devices & Services → Helpers**) so both the card and
the automation below can use one value:

```yaml
template:
  - sensor:
      - name: "Amazon attempted orders outstanding"
        unique_id: amazon_attempted_orders_outstanding
        state: >
          {% set attempted = state_attr('sensor.mail_amazon_attempted', 'order') or [] %}
          {% set delivered = state_attr('sensor.mail_amazon_delivered', 'order') or [] %}
          {{ attempted | reject('in', delivered) | list | count }}
        attributes:
          order: >
            {% set attempted = state_attr('sensor.mail_amazon_attempted', 'order') or [] %}
            {% set delivered = state_attr('sensor.mail_amazon_delivered', 'order') or [] %}
            {{ attempted | reject('in', delivered) | list }}
```

### Dashboard card: show an attempted delivery until it lands

```yaml
type: conditional
conditions:
  - condition: numeric_state
    entity: sensor.amazon_attempted_orders_outstanding
    above: 0
card:
  type: markdown
  title: Amazon delivery attempted — still outstanding
  content: >
    Attempted order(s):
    {{ state_attr('sensor.amazon_attempted_orders_outstanding', 'order') | join(', ') }}

    Check for a safe place to leave the package, or be ready for
    the next attempt.
```

Because the condition reads the helper, the card hides itself as
soon as the attempted order appears in the delivered orders — no
manual clearing.

### Automation: alert on a missed delivery

```yaml
alias: Amazon delivery attempted
triggers:
  - trigger: numeric_state
    entity_id: sensor.amazon_attempted_orders_outstanding
    above: 0
actions:
  - action: notify.notify
    data:
      title: Amazon delivery attempted
      message: >-
        Delivery was attempted for order
        {{ state_attr('sensor.amazon_attempted_orders_outstanding', 'order') | join(', ') }}
        and it has not been delivered yet.
mode: single
```

---

## Exception tracking numbers (all carriers that have them)

Exception sensors — USPS, UPS, FedEx, Walmart, Home Depot,
PostNL, and Amazon — now expose **their own** exception tracking
numbers on the sensor's `tracking_#` attribute (order numbers for
Amazon, on its `order` attribute), instead of the in-transit
list. That makes the same match-and-clear pattern possible by
tracking number:

```jinja
{% set exception = state_attr('sensor.mail_usps_exception', 'tracking_#') or [] %}
{% set delivered = state_attr('sensor.mail_usps_delivered', 'tracking_#') or [] %}
{{ exception | reject('in', delivered) | list }}
```

Two behavior notes:

- Exception numbers **never set or override the delivering
  counts**. They exist only so templates can match an exception
  to a later delivery.
- Attempted/missed detection exists only for **Amazon and
  PostNL** so far (for PostNL, the "we missed you" notice is the
  `post_nl_exception` email). No other carrier's attempted email
  is detected yet.

---

## Daily reset and midnight behavior

Delivered counts reset at midnight local time, and delivering
sensors search a configurable look-back window (default 3 days).
Delivery confirmations soften that reset in three ways, so an
open item is not lost overnight:

- A sighting on a newer sensor keeps an already-tracked package
  active past midnight.
- A delivery stays confirmed past midnight while an attempt or
  exception for the same order/tracking number is still open,
  clearing once nothing references it or it ages past the
  tracking time-to-live.
- Amazon attempted orders likewise stay open until the delivered
  order list matches them.

---

## Other delivery-confirmation additions

These landed in the same series and are documented where they
belong, in
[Supported Shipper Requirements](Supported-Shipper-Requirements):

- **DHL eCommerce attribution** — marketplace emails that identify
  DHL eCommerce as the carrier (including `420…` DHL eCommerce
  tracking numbers) count under the DHL sensors, not only under
  the marketplace.
- **eBay** — new delivering support (`ebay_delivering` /
  `ebay_packages`); there is no eBay delivered sensor yet, as no
  genuine delivered sample is available.
- **Shopify stores** — stores that mail from their own domains
  are matched, not only the standard Shopify senders.
- **PledgeBox and 4PX** — PledgeBox in-transit notices are
  parsed, and full 4PX tracking numbers in them are attributed
  to the 4PX sensors; a package reported by both counts once
  (the carrier wins).
