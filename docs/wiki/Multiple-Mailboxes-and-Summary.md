# Multiple Mailboxes and Summary Sensors

Mail and Packages supports monitoring multiple email accounts simultaneously (e.g. personal, work, spouse, or accounts forwarding delivery notifications).

---

## Setting Up Multiple Mailboxes

Each mailbox is added as its own independent integration entry in Home Assistant:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Select **Mail and Packages** and choose your authentication method (Password, Google OAuth2, or Microsoft OAuth2).
3. Complete setup for each email account you want to monitor.

### Mailbox Naming and Image Storage
- **Device & Entity Naming**: Each mailbox entry is titled and named after its email address (e.g., `sensor.someone_example_com_mail_usps_packages`), making it easy to distinguish accounts on the same mail provider (such as multiple Gmail or Outlook accounts).
- **Isolated Image Storage**: Each mailbox automatically uses its own dedicated image subfolder. Image cleanups run independently per mailbox so one account never deletes another account's delivery images.

---

## "All Mailboxes" Summary Sensors

Once two or more mailboxes are configured, an **"All mailboxes"** summary entry is automatically discovered in Home Assistant:

1. Go to **Settings → Devices & Services**.
2. Look for the **Discovered** card for **Mail and Packages: All mailboxes**.
3. Click **Configure** and submit to create the combined summary device.

*(Note: If you click **Ignore** on the discovered card, it can be un-ignored and added at any time from your Ignored integrations list. Removing the summary entry does not affect your individual mailboxes.)*

---

## How Combined Sensors Work

The "All mailboxes" device creates aggregate sensors matching the sensor types enabled across your monitored mailboxes (e.g., `sensor.all_mailboxes_mail_usps_packages`, `sensor.all_mailboxes_mail_packages_in_transit`, `sensor.all_mailboxes_mail_packages_delivered`).

### 1. Intelligent Package Deduplication
If shipping notification emails for the same package arrive in multiple inboxes (for instance, when family members forward tracking emails to each other, or multiple accounts receive updates for the same order):
- The package is counted **only once**.
- Packages are matched and deduplicated by carrier **tracking number**, or by **Amazon order number**.

### 2. Additive Counts for Non-Tracked Mail
Counts that do not have tracking numbers—such as the USPS Informed Delivery daily mail count—are summed across all mailboxes.

### 3. Detailed Attributes
Each combined sensor provides detailed diagnostic attributes:
- **`mailboxes`**: A dictionary breakdown showing the count contributed by each individual mailbox.
- **`tracking_#`**: The complete list of unique tracking numbers found across all mailboxes.

---

## Performance & System Impact

- **Zero IMAP Overhead**: The summary entry makes **no IMAP connections** and reads no email directly.
- **Reactive Updates**: Whenever an individual mailbox coordinator completes an update cycle, it signals the summary device to recalculate its totals in memory.
- **Dynamic Sensor Management**: If you enable or disable carriers on any individual mailbox, the summary entry automatically reloads to adjust the combined sensor set.
