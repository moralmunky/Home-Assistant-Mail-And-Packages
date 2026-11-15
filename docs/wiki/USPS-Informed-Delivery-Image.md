Jump to: [Getting the image](#getting-the-image) | [Displaying the image](#displaying-the-image)

# Getting the image

## Built-in Camera Entity (Recommended)

The integration automatically creates a **USPS camera entity** (`camera.mail_usps_camera`) that serves the current Informed Delivery GIF directly. No manual setup is required — the camera is available as soon as the integration is configured and an Informed Delivery email has been processed.

You can use this camera entity directly in any Lovelace card that supports cameras (picture entity card, picture elements, etc.).

> **Note:** The camera entity is enabled by default. If you don't see it, check **Settings** → **Devices & services** → **Integrations** → **Mail and Packages** → **entities** to confirm it is enabled.

### Using Camera Proxy in Notifications (Recommended)

Instead of exposing images publicly via `www/` or configuring external image URLs, modern Home Assistant notifications can use Home Assistant's built-in authenticated camera proxy:

* **iOS Companion App**: Attach via `entity_id: camera.mail_usps_camera`.
* **Android Companion App**: Attach via `image: "/api/camera_proxy/camera.mail_usps_camera"`.

**Benefits of using the camera proxy:**
* **No `www` file copying required**: You do not need to enable "Allow external image use".
* **Secure and authenticated**: Images are authenticated and token-signed by Home Assistant, rather than placed in an unauthenticated public `/local/` directory.
* **Works seamlessly with Nabu Casa / Remote UI**: No manual external URL or base URL configuration required.

See [Notifications Wiki](Notifications) for complete automation examples.

## Option 1: Image URL Sensor (Secure Signed URL)

The `sensor.mail_image_url` entity provides access to today's Informed Delivery scan:
* **`image_url` State Attribute (Recommended)**: Holds the complete, secure signed URL (e.g., `https://<your-ha-instance>/api/mail_and_packages/image/<entry_id>/<image>?authSig=...`). URLs are cryptographically signed using Home Assistant authentication and automatically expire after 24 hours. Access it in templates using:
  ```jinja2
  {{ state_attr('sensor.mail_image_url', 'image_url') }}
  ```
* **Sensor State**: Because Home Assistant limits entity states to 255 characters, the sensor state contains the image filename (or the legacy URL if short enough). Always use the `image_url` attribute for full URL access.

> **Note on "Allow external image use" (Deprecated):**
> Previously, external access required copying images to `/config/www/mail_and_packages/` (unauthenticated). This is now deprecated and no longer required. Images are streamed securely on demand from integration storage with signature verification.

**Requirements:**
* A configured `Internal URL`, `External URL`, or [Nabu Casa](https://www.nabucasa.com/) remote UI URL in Home Assistant general settings.

**Where to use it:**
* [Mail and Packages Custom Card](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages-Custom-Card)
* [iOS and Android push notifications](https://companion.home-assistant.io/docs/notifications/notification-attachments) (or use `camera.mail_usps_camera`)

## Image Storage Location & Architecture

### Where Images Are Stored
Images and generated mail GIFs are stored in an entry-scoped directory inside your Home Assistant config folder:
```text
<config_dir>/mail_and_packages/<entry_id>/
```
*(e.g., `/config/mail_and_packages/01JABCD1234EFGH.../`)*

### Why Images Are Stored Here
1. **Multi-Account Isolation**: Scoping storage to the integration `entry_id` ensures multiple configured mailboxes have private folders and never overwrite each other's mail scans or delivery photos.
2. **Privacy by Default**: Previously, images placed in `/config/www/` were served publicly by Home Assistant without authentication. Storing them inside entry-scoped directories keeps them outside the unauthenticated static web root.
3. **Signed URLs & Authenticated Proxies**: Images are streamed securely via the camera proxy (`camera.mail_usps_camera`) or via Home Assistant's authenticated signed image endpoint (`/api/mail_and_packages/image/<entry_id>/<filename>`) using cryptographic tokens that expire after 24 hours.
4. **Automated Lifecycle Cleanup**: Removing an account integration entry automatically purges its corresponding image directory from disk.

### Deprecations
* **Custom Storage Location (`storage`)**: Deprecated. Images are automatically managed in the entry-scoped directory.
* **Allow External Image Use (`allow_external`)**: Deprecated. Files no longer need to be copied into the public `www/` folder; use camera entities or signed URL attributes instead.

---

## Option 2: File Path Sensor

`sensor.mail_image_system_path` exposes the local filesystem path to the current GIF within the managed entry directory. Use this when you need to reference the file directly on the host (e.g. for local-only integrations or automations that move/copy the file).

* **`image_path` State Attribute (Recommended)**: Holds the complete, untruncated local filesystem path. Access it in templates using:
  ```jinja2
  {{ state_attr('sensor.mail_image_system_path', 'image_path') }}
  ```
* **Sensor State**: Home Assistant limits entity states to 255 characters. If the full path exceeds 255 characters, the sensor state falls back to just the image filename. Always use the `image_path` attribute to access the full path safely in automations and scripts.

---

# Displaying the image

## Built-in Camera and Custom Card

The [Mail and Packages Custom Card](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages-Custom-Card) can be installed manually or through HACS. It works with the built-in `camera.mail_usps_camera` entity or `sensor.mail_image_url`.

<img src="https://raw.githubusercontent.com/moralmunky/Home-Assistant-Mail-And-Packages-Custom-Card/master/img/card-image.png" width="350">

## Standard Lovelace Cards

> **Note:** The camera entity refreshes every 10 seconds. If your GIF is longer than 10 seconds, use a [picture entity card](https://www.home-assistant.io/lovelace/picture-entity/) with `camera_view: live` so all mail pieces are shown.

### Example 1: Picture Entity Card

```yaml
type: picture-entity
entity: camera.mail_usps_camera
aspect_ratio: 50%
name: Mail
camera_view: live
show_name: false
show_state: false
```

### Example 2: Vertical Stack

```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: camera.mail_usps_camera
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
      - entity: sensor.mail_usps_delivering
        name: USPS Delivering
      - entity: sensor.mail_fedex_delivering
        name: FedEx Delivering
      - entity: sensor.mail_ups_delivering
        name: UPS Delivering
      - entity: sensor.mail_packages_in_transit
        name: Packages In Transit
      - entity: sensor.mail_packages_delivered
        name: Packages Delivered
      - entity: sensor.mail_updated
        name: Last Updated
```

### Example 3: Picture Elements Card (with overlays)

```yaml
type: picture-elements
image: local/mail_and_packages/white.png
entity: camera.mail_usps_camera
tap_action:
  action: more_info
hold_action:
  action: none
elements:
  - type: image
    entity: null
    camera_image: camera.mail_usps_camera
    camera_view: live
    style:
      top: 50%
      left: 50%
      width: 100%
  - type: image
    entity: null
    image: local/mail_and_packages/overlay.png
    style:
      top: 50%
      left: 50%
      width: 100%
  - type: image
    entity: camera.mail_usps_camera
    image: local/mail_and_packages/vignette.png
    style:
      top: 50%
      left: 50%
      width: 100%
```
