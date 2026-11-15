### Uninstalling/Reinstalling

If you are attempting to troubleshoot and want to uninstall and reinstall the component please follow these steps:

1. Remove the Integration from the Integrations menu in Home Assistant (you will need to re-enter usernames and passwords)
2. Open HACS
3. Click Integrations
4. Click the 3 dots for the `Mail and Packages` integration
5. Select `Reinstall`
6. Go back to the Integrations menu and re-add the Integration

Removing the integration should clear any configuration data from inside the `core.config_entries` file making for a clean reinstall.

<hr>

### My packages are not being detected?

Make sure the folder selected is where your USPS/UPS/FedEx emails are going into. Also keep in mind only packages that are "out for delivery" will be counted.

The default folder is "INBOX" if you are not filtering your email use this option.

**Reminder: The integration is only reporting on packages that are in transit to be delivered the current day. It does not report in-transit packaged delivered on a future day.**

<hr>

### Enable Debugging

More information may need to be collected, here's how you can enable debugging from the UI:
<img alt="image" src="https://github.com/user-attachments/assets/edac93ae-fe75-41a1-9ef0-16910f7abbd2" />

<hr>

### Entities Showing as "Unavailable" / Scan Timeout Errors

If entities periodically become `unavailable`, or you see log errors similar to:

```text
Mail and Packages scan exceeded its 90s time budget (elapsed 90.8s). This budget covers the ENTIRE scan (login plus every per-carrier IMAP search), not just connecting. Increase the scan time limit in the integration options, or reduce the mailbox size searched (use a dedicated folder), the days-back window, or the number of enabled carriers.
```

This occurs when the total time taken to log in and query all enabled carriers over IMAP exceeds the configured scan timeout limit. Slow response latency from the email provider (e.g., Yahoo Mail), searching a very large mailbox, or querying many carriers sequentially can cause the scan to time out.

#### Troubleshooting & Resolution Steps:

1. **Increase the Scan Time Limit**:
   - Go to **Settings** > **Devices & Services** > **Mail and Packages** > **Configure**.
   - Increase the **Scan time limit** (e.g., increase from `90` to `180` or `240` seconds) to allow slower email providers adequate time to complete all carrier searches.

2. **Use a Dedicated Mailbox Folder**:
   - Create an automated filter/rule in your email account to move delivery notifications into a dedicated folder (e.g., `Mail_Packages`).
   - In the integration options, update **Mailbox Folder** to target this folder rather than the entire `INBOX`. Searching a smaller dedicated folder significantly reduces IMAP search latency.

3. **Disable Unused Carriers**:
   - In the integration options, uncheck any delivery carriers that you do not actively use (such as DHL, Amazon, etc.) to minimize the number of sequential IMAP searches executed during each update.

4. **Reduce the Days-Back Search Window**:
   - Lower the number of days back searched (if configured above the default) to reduce the date range scanned during queries.
