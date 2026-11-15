# Installation and Updates
### [HACS](https://hacs.xyz) (Recommended)
1. Have [HACS](https://github.com/custom-components/hacs) installed — this allows easy updates.
2. Go to **HACS** → **Integrations**, click **+** in the lower right corner, and search for `Mail and Packages`.
3. Click **Download** under "Mail and Packages" and restart Home Assistant.

### Manual Installation
1. Download this repository as a ZIP (green button, top right) and unzip the archive.
2. Copy the `mail_and_packages` folder to your Home Assistant `/<config path>/custom_components/` directory.
   * You may need to create the `custom_components` folder if it does not exist.
   * On Home Assistant OS and Home Assistant Container the final location should be `/config/custom_components/mail_and_packages`.
   * On Home Assistant Supervised and Home Assistant Core the final location should be `/home/homeassistant/.homeassistant/custom_components/mail_and_packages`.
3. Restart Home Assistant.

> **Note:** If the integration does not appear, refresh the Integrations page.

# Enabling Betas
### [HACS](https://hacs.xyz) (Recommended)
1. Go to **Settings** → **Devices & services** and select the **HACS** integration.
2. Find **Mail and Packages** in the list and click it.
3. In the **Diagnostics** card, click **+1 disabled entry**.
4. Click **Pre-releases**, then click the **Cog** icon at the top and select **Enable**.
5. HACS will reload — the **Pre-releases** toggle is now active. Turn it on.
6. HACS will show that an update is available — install it and restart Home Assistant.

# Configuration
Go to **Settings** → **Devices & services** → **Integrations**, click **+ Add integration**, and search for **Mail and Packages**. Setup is a two-step process.

#### Re-configuration
To modify settings without removing the integration, go to **Settings** → **Devices & services** → **Integrations**, find **Mail and Packages**, and click **Configure**.

## Step 1 — Connection
Notes about [specific email providers](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Configuration-and-Email-Settings/#email-provider-notes) are below.

Setting | Description
--- | ---
Host | The IMAP server address provided by your email host.
Port | The IMAP port provided by your email host (typically 993 for SSL).
Email | The email address where you receive shipping notifications.
Password | The password (or app password) for your email account.

#### Checking multiple mailboxes
To check multiple email accounts, add the integration again with the credentials for the additional account. A separate set of sensors will be created for each account.

## Step 2 — Options

Setting | Description
--- | ---
Mail Folder | The folder in your email account where notification emails are stored. Default is `INBOX`.
Sensor List | The sensors to activate, corresponding to the shipping providers you want to track.
Amazon forwarded email addresses | Email addresses you forward Amazon notifications from. Separate multiple addresses with a comma.
Forwarding Header | If you use an email forwarding service that preserves the original sender in a custom header (e.g. `X-Forwarded-To`), enter that header name here. Leave blank or set to `(none)` if not applicable. See [Email Forwarding](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/wiki/Email-Forwarding) for details.
Days to look back | Number of past days to include when searching for in-transit packages. Increasing this keeps packages visible longer across the midnight boundary. Default is 3.
Scanning Interval (minutes) | How often the integration checks for new emails.
Time before connection timeout (seconds) | Increase this if your mail provider has a slow connection.
Image Duration (seconds) | How long each USPS Informed Delivery image is shown in the rotating GIF.
Create MP4 from GIF | Generate an MP4 version of the USPS Informed Delivery image.
Allow external image use *(Deprecated)* | Legacy option to copy the image to `/config/www/mail_and_packages/`. Deprecated in favor of direct authenticated streaming via Home Assistant's secure image endpoint.

### Delivery-confirmation and Amazon code sensors

The **Sensor List** also controls the delivery-confirmation sensors. They are opt-in — tick them under **Configure** or they will not be created:

| Sensor | What it gives you |
| --- | --- |
| **Mail Amazon OTP Code** (`sensor.mail_amazon_otp_code`) | Count of today's deliveries that need a one-time password, with `code`, `order`, `delivery_date`, `delivery_window`, `delivery_window_start`, and `delivery_window_end` attributes |
| **Mail Amazon Delivery Code** (`sensor.mail_amazon_delivery_code`) | Today's first delivery code as a plain string |
| **Mail Amazon Delivery Window Start / End** (`sensor.mail_amazon_delivery_window_start` / `sensor.mail_amazon_delivery_window_end`) | The delivery window bounds as `timestamp` sensors, for use as a `time` trigger |
| **Mail Amazon Attempted** (`sensor.mail_amazon_attempted`) | Count of today's "Delivery attempted" emails, with the attempted order numbers on its `order` attribute |
| Exception sensors (USPS, UPS, FedEx, Walmart, Home Depot, PostNL, Amazon) | Their own exception tracking numbers on the `tracking_#` attribute (order numbers for Amazon), so templates can match an exception to a later delivery; exception numbers never set or override the delivering counts |

Recipes for these sensors — the delivery-code automation and card, and the attempted-delivery alert and card that clears on delivery — are on [Amazon Delivery Confirmations](Amazon-Delivery-Confirmations). Which carriers support which part is in the [Delivery Confirmation Support Matrix](Supported-Shipper-Requirements#delivery-confirmation-support-matrix).

### Image Storage & Security Architecture

#### Where Images Are Stored
Images and generated media (USPS rotating GIFs, shipper delivery photos, MP4s, and AI vision grids) are automatically stored inside an **entry-scoped directory** in your Home Assistant configuration directory:
```text
<config_dir>/mail_and_packages/<entry_id>/
```
*(e.g., `/config/mail_and_packages/01JABCD1234EFGH.../`)*

#### Why Images Are Stored Here
1. **Multi-Account & Multi-Instance Isolation**: Each configured mailbox entry receives its own private storage folder scoped by its unique `entry_id`. This prevents mail scans, package delivery pictures, and filenames from colliding or overwriting each other when multiple mailboxes or accounts are configured.
2. **Security & Privacy (Eliminating Public `/www/` Exposure)**: Previously, images copied to `/config/www/` were served via Home Assistant's `/local/` static file endpoint, making personal mail scans and delivery photos accessible to anyone without authentication. Storing them inside entry-scoped directories keeps them completely private and inaccessible via the static web root.
3. **Secure Serving via Signed URLs & Camera Proxies**: Media is served on-demand via Home Assistant's secure camera proxy (`/api/camera_proxy/...`) or authenticated API endpoint (`/api/mail_and_packages/image/<entry_id>/<filename>`) using time-limited cryptographic tokens (`async_sign_path`), preventing unauthenticated scraping.
4. **Clean Lifecycle & Automated Cleanup**: When a Mail and Packages configuration entry is removed from Home Assistant, its corresponding `<entry_id>` storage folder is automatically purged from the filesystem.

#### Deprecation Notice: Custom Storage Path & External Image Copying
* **Custom Storage Path (`storage`)**: Deprecated and will be removed in a future release. Images are automatically managed in the entry-scoped directory. A repair issue will notify users if an old custom path is configured.
* **Allow External Image Use (`allow_external`)**: Deprecated. You no longer need to copy files to `/config/www/` to use them in push notifications; use the built-in camera proxy or signed URL sensors instead.

Two sensors expose image references:
* `sensor.mail_image_system_path` — local filesystem path. Provides `image_path` in its state attributes (`state_attr('sensor.mail_image_system_path', 'image_path')`) containing the complete untruncated path for use with automations, scripts, and local file cameras.
* `sensor.mail_image_url` — provides `image_url` in its `extra_state_attributes`, containing a secure, signed URL (or legacy URL if `allow_external` is enabled). Built using your configured `External URL`, `Internal URL`, or [Nabu Casa](https://www.nabucasa.com/) remote UI URL.

## Email Provider Notes

### GMail

<details>
<summary>App Password (deprecated)</summary>

If you are using GMail you will need to set up an `App Password` in order for this to work.
Please refer to [this guide](https://support.google.com/accounts/answer/185833?hl=en) for details.

Additional information on GMail settings is available [here](https://support.google.com/a/answer/9003945#zippy=%2Cstep-set-up-gmail-with-the-older-version-of-outlook) under "_Set up Gmail with older versions of Outlook and other clients_".

</details>

### OAuth Setup
This section explains how to generate a client ID and client secret using the Google Auth Platform.

<details>
<summary>OAuth2 Setup</summary>

Mail and Packages connects to your mailbox over **IMAP**. For Gmail accounts, Google requires **OAuth2** rather than a password or app password. This guide walks through creating the Google OAuth credentials and wiring them into Home Assistant.

> **Heads up — Google changed this UI.** In 2024 Google replaced the old single "APIs & Services → OAuth consent screen" wizard (with its "Test users" tab and inline scope picker) with the **Google Auth Platform** (https://console.cloud.google.com/auth). Setup is now split across separate **Branding**, **Audience**, **Data Access**, and **Clients** pages. The steps below reflect the current UI. (See [Get started with the Google Auth Platform](https://support.google.com/cloud/answer/15544987).)

---

#### Before you start

- A Google account that can sign in to the [Google Cloud Console](https://console.cloud.google.com/).
- A Home Assistant instance reachable over **HTTPS on a public domain** (required so Google will accept the OAuth redirect). The default redirect used below (`https://my.home-assistant.io/redirect/oauth`) works for most installs via [My Home Assistant](https://my.home-assistant.io/).

The whole thing is free and takes about 10 minutes. You do **not** need to pay for Google Cloud or submit your app for Google's review for personal use.

---

#### Step 1 — Create or select a Google Cloud project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Use the project picker at the top to **create a new project** (e.g. `home-assistant-mail`) or select an existing one you'll reuse.

#### Step 2 — Enable the Gmail API

The Gmail scope you need later **won't be selectable unless the Gmail API is enabled on the project first**, so do this now.

1. Navigate to **APIs & Services → Library** (https://console.cloud.google.com/apis/library).
2. Search for **Gmail API**, open it, and click **Enable**.

#### Step 3 — Configure the Google Auth Platform ("consent screen")

Open the **Google Auth Platform** at [Google Cloud Console Auth](https://console.cloud.google.com/auth).

- **First-time projects** show a **"Get started"** flow. Fill it in:
  - **App name** — anything recognizable (e.g. `Home Assistant Mail and Packages`).
  - **User support email** — your address.
  - **Audience** — choose **External**.
  - **Contact information** — your email.
  - Agree and click **Create**.
- **Reusing a project** that already has the Auth Platform configured (for example, from another Home Assistant integration)? Then there is **no "Get started" button** — you'll land directly on the configured Auth Platform view with the Branding / Audience / Data Access / Clients pages in the left nav. **This is expected**; just proceed to the next step.

(Reference: [Get started with the Google Auth Platform](https://support.google.com/cloud/answer/15544987), [Manage OAuth App Branding](https://support.google.com/cloud/answer/15549049).)

#### Step 4 — Add the Gmail scope (Data Access page)

1. In the Google Auth Platform left nav, open **Data Access**.
2. Click **Add or remove scopes**.
3. Add the scope:

   ```
   https://mail.google.com/
   ```

   You can paste it into the "Manually add scopes" box at the bottom of the panel and click **Add to table**, then **Update**.
4. Click **Save**.

> ⚠️ **You must use the full `https://mail.google.com/` scope — nothing narrower.**
> This is the single most common mistake. The granular read-only scopes (`gmail.readonly`, `gmail.metadata`, `gmail.modify`, …) only work with the Gmail **REST API**. Mail and Packages talks to Gmail over **IMAP**, and IMAP/SMTP/POP authentication via XOAUTH2 **only accepts `https://mail.google.com/`**. If you pick a read-only scope, the integration will fail to authenticate.
> (See Google's [XOAUTH2 protocol doc](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol) and [Restricted Scopes](https://support.google.com/cloud/answer/13464325).)

Because `https://mail.google.com/` is classified by Google as a **restricted** scope, adding it pops a **"Verification required"** notice. For **personal use** this is **informational** — click through it. You do **not** need to submit your app for Google's restricted-scope verification just to read your own mailbox; you self-authorize as the app owner in Step 7.

#### Step 5 — Audience: user type and test users

1. Open the **Audience** page.
2. Confirm **User type = External**.
3. While the app is in **Testing**, add your own Google account under **Test users** (the account whose mailbox you want Mail and Packages to read). Only test users can complete consent while the app is in Testing.
   (See [Manage App Audience](https://support.google.com/cloud/answer/15549945).)

#### Step 6 — Publish the app (avoid the 7-day token expiry)

This step is **strongly recommended**.

While the app's **Publishing status** is **Testing** (with External user type), Google **expires OAuth refresh tokens after 7 days**. The practical symptom: Mail and Packages stops updating and asks you to re-authenticate roughly once a week, seemingly at random. (Confirmed by Google: *"Authorizations by a test user will expire seven days from the time of consent."* — [Manage App Audience](https://support.google.com/cloud/answer/15549945).)

**Fix:** On the **Audience** page, click **Publish app** to move the publishing status to **In production**. Tokens then persist indefinitely.

- The app will still show as **"unverified"** — that's fine. Verification is only needed if you intend to distribute the app publicly. For your own mailbox you simply click through the unverified-app warning once during consent (Step 7).
- This is the exact same guidance Home Assistant gives for its built-in Google Calendar / Google Tasks integrations.

#### Step 7 — Create the OAuth client (Clients page)

1. Open the **Clients** page in the Google Auth Platform.
2. Click **Create client**.
3. **Application type:** **Web application**.
4. Give it a name (e.g. `Home Assistant`).
5. Under **Authorized redirect URIs**, add:

   ```
   https://my.home-assistant.io/redirect/oauth
   ```

   > If you don't use My Home Assistant, use `https://<your_home_assistant_url>/auth/external/callback` instead — it must exactly match the URL you use during authentication.
6. Click **Create**.
7. Copy the **Client ID** and **Client Secret**. You'll paste these into Home Assistant next.

   (New credentials are usually active within a few minutes, though Google says it can take a few hours. See the Home Assistant [Google Nest](https://www.home-assistant.io/integrations/nest/) docs, which use the same redirect URI and client setup.)

#### Step 8 — Add the credentials in Home Assistant and authenticate

1. In Home Assistant, you'll be prompted for **Application Credentials** when you add / configure the Mail and Packages integration with the Google OAuth option. You can also pre-create them: **Settings → Devices & Services → ⋮ (top right) → Application Credentials → Add Application Credential**, choosing **Mail and Packages** (or the Gmail OAuth provider it uses).
2. Paste the **Client ID** and **Client Secret** from Step 7.
3. Continue the Mail and Packages config flow. Home Assistant hands you off to Google:
   - Pick the Google account whose mailbox you're monitoring (must be a **Test user** if the app is still in Testing).
   - You'll see **"Google hasn't verified this app."** Click **Advanced**, then **Continue** (or "Go to *app name* (unsafe)").
   - **Grant** the requested access.
4. Google redirects back to Home Assistant and the integration finishes setup.

---

#### Common gotchas

- **"My read-only scope won't authenticate."** IMAP requires the **full `https://mail.google.com/` scope**. The `gmail.readonly` / `gmail.metadata` / `gmail.modify` scopes are Gmail-REST-API-only and will **not** work over IMAP. Use `https://mail.google.com/` and nothing else.
- **"It keeps asking me to re-authenticate every week."** Your app is in **Testing**, where Google expires refresh tokens after **7 days**. Go to **Audience → Publish app** to move it to **In production**.
- **"Google says the app isn't verified."** Expected for personal use. During consent, click **Advanced → Continue**. You only need formal verification to publish the app to other users.
- **"There's no 'Get started' button."** You're reusing a Google Cloud project whose Auth Platform is already configured (common if you also use another Google-OAuth Home Assistant integration). Skip straight to the **Data Access** / **Audience** / **Clients** pages — there's nothing to "get started."
- **"Google says Error 403: access_denied."** The app is still in **Testing** and the account you are signing in with was not added as a test user. Go to **Audience → Test users** and add the email address, or publish the app to **In production**.
- **"The Gmail scope isn't in the list."** You skipped **Step 2** — enable the **Gmail API** first, then the scope becomes available on the Data Access page.
- **"Redirect URI mismatch / Error 400."** The redirect URI in your OAuth client must exactly match the one Home Assistant uses (`https://my.home-assistant.io/redirect/oauth` for My Home Assistant).
- **"You signed in, but ... refused mail (IMAP) access."** The email address entered as the username in Home Assistant must match the account you signed into during the OAuth prompt. Additionally, ensure IMAP access is enabled in your Gmail settings.

---

#### A note on least privilege (optional)

`https://mail.google.com/` grants **full** read/write/delete access to the mailbox — that's broad. If you'd rather not expose your primary inbox, a common pattern is to use a **dedicated Gmail account** that only receives **forwarded shipment notifications** (set up forwarding/filters in your main account), and point Mail and Packages at that mailbox instead. The integration only reads message subjects (and, for USPS Informed Delivery, the mail-piece images), but the OAuth scope itself is all-or-nothing for IMAP, so an isolated mailbox is the cleanest way to limit blast radius.

---

#### Sources

- [Get started with the Google Auth Platform](https://support.google.com/cloud/answer/15544987)
- [Manage OAuth App Branding](https://support.google.com/cloud/answer/15549049)
- [Manage App Audience (test users, 7-day token expiry, publishing)](https://support.google.com/cloud/answer/15549945)
- [Manage App Data Access (scopes)](https://support.google.com/cloud/answer/15549135)
- [Restricted Scopes (mail.google.com)](https://support.google.com/cloud/answer/13464325)
- [Gmail XOAUTH2 protocol — IMAP requires mail.google.com](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol)
- [Home Assistant — Google Nest (same redirect URI / client pattern)](https://www.home-assistant.io/integrations/nest/)

</details>

***
### Yahoo Mail

Nothing special is required for Yahoo Mail — just enter your username (Yahoo email address) and password.
If you have 2FA enabled you will need to [generate an app password](https://help.yahoo.com/kb/generate-manage-third-party-passwords-sln15241.html).

References:
[**Server Settings**](https://help.yahoo.com/kb/sln4075.html) | [**App Passwords**](https://help.yahoo.com/kb/generate-manage-third-party-passwords-sln15241.html)

***
### Hotmail/Outlook/Live/Office

<details>
<summary>OAuth2 Setup</summary>

Mail and Packages connects to your mailbox over **IMAP**. For Hotmail, Outlook, Live, and Office 365 accounts, Microsoft requires **OAuth2** rather than a password or app password. This guide walks through creating the Microsoft OAuth credentials and wiring them into Home Assistant.

---

#### Step 1 — App Registration

1. Go to the [Microsoft Azure Portal / Entra admin center (App Registrations)](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade).
2. Click **+ New registration**.
3. **Name**: Enter a recognizable name (e.g., `Home Assistant Mail`).
4. **Supported account types**: Select **"Accounts in any organizational directory (Any Microsoft Entra ID tenant - Multitenant) and personal Microsoft accounts (e.g. Skype, Xbox)"**.
   *   *Note: This is required because Mail and Packages authenticates via Microsoft's shared `/common` endpoint. Single tenant apps will fail with `AADSTS50194`.*
5. **Redirect URI**: Select **Web** from the dropdown and enter:
   ```
   https://my.home-assistant.io/redirect/oauth
   ```
   *   *Note: If you don't use My Home Assistant, enter `https://<your_home_assistant_url>/auth/external/callback` instead.*
6. Click **Register**.

#### Step 2 — Configure API Permissions (Scopes)

1. On the left sidebar of your app registration, go to **API permissions**.
2. Click **+ Add a permission**, then select **Microsoft Graph**.
3. Click **Delegated permissions**.
4. Search for and check:
   *   `IMAP.AccessAsUser.All`
   *   `offline_access` (required for token refresh)
5. Click **Add permissions**.
6. *Optional for work/school accounts*: If you are registering an organizational mailbox, click **Grant admin consent for [Your Organization Name]** next to the Add a permission button. Personal accounts do not need admin consent.

#### Step 3 — Create Client Secret

1. On the left sidebar, go to **Certificates & secrets**.
2. Click **+ New client secret**, enter a description, set a preferred expiry (e.g., 24 months), and click **Add**.
3. **Important**: Copy the string in the **Value** column (not the Secret ID) immediately. This value is only shown once.

#### Step 4 — Copy the Application (Client) ID

1. Go to the **Overview** tab in the left sidebar.
2. Copy the **Application (client) ID** value.
3. *Note: You do **not** need the Directory (tenant) ID. The integration automatically routes authentication requests through Microsoft's `/common` endpoint, so you will only need to input the Client ID and Client Secret in Home Assistant.*

#### Step 5 — Add the credentials in Home Assistant and authenticate

1. In Home Assistant, you'll be prompted for **Application Credentials** when configuring the Mail and Packages integration with the Microsoft OAuth option. You can also pre-create them: **Settings → Devices & Services → ⋮ (top right) → Application Credentials → Add Application Credential**, choosing **Mail and Packages** (or the Microsoft OAuth provider it uses).
2. Paste the **Client ID** (from Step 4) and **Client Secret** (from Step 3).
3. Continue the Mail and Packages config flow. Home Assistant redirects you to Microsoft to authorize the connection to your mailbox.
4. Once completed, you will be redirected back to Home Assistant to finish setup.

---

#### Common gotchas & Troubleshooting

- **Microsoft says `AADSTS50194`: "is not configured as a multi-tenant application"**
  The app registration was set to a single tenant. Mail and Packages signs in through Microsoft's shared `/common` endpoint. Go to **Authentication** in the Azure/Entra portal and set **Supported account types** to multitenant (Accounts in any organizational directory).
- **Microsoft says `AADSTS50011`: The reply URL specified in the request does not match**
  Verify that the redirect URI is added under the **Web** platform (not SPA or Mobile) and exactly matches `https://my.home-assistant.io/redirect/oauth`.
- **Microsoft says "Need admin approval"**
  For work/school organizational accounts, an IT administrator must grant admin consent for the app's requested delegated permissions (`IMAP.AccessAsUser.All`).
- **Microsoft says `AADSTS7000215`: Invalid client secret**
  The **Secret ID** was copied instead of the secret **Value**, or the secret expired. Generate a new client secret under **Certificates & secrets**, copy the **Value** immediately, and update the application credentials in Home Assistant.
- **"You signed in, but ... refused mail (IMAP) access"**
  1. The email address entered as the username in Home Assistant does not match the account you signed into during the Microsoft prompt.
  2. IMAP is disabled for the mailbox. For Microsoft 365 / Exchange mailboxes, an admin may need to turn on IMAP in the [Exchange admin center](https://admin.exchange.microsoft.com/) under **Recipients → Mailboxes → [Mailbox] → Email apps settings → IMAP**.
- **`my.home-assistant.io` asks for an address**
  Enter your Home Assistant instance URL once; the browser will remember it for future redirects.

</details>

***
### Proton Mail
1. Set up Proton Mail Bridge ([Docker container](https://github.com/shenxn/protonmail-bridge-docker/issues)). After initial setup, run the info command to get connection details.
2. Add the integration using the credentials provided by the bridge. Use **SSL** and **No verification of SSL certificate**. Username and password are provided by the bridge.
