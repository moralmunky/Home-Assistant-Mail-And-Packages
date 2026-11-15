# Email Forwarding

Some users receive shipping notifications at a different email address than the one they monitor with this integration — for example, a shared family inbox, a business address, or a catch-all alias. The integration supports two approaches.

## When do you need this?

You need forwarding configuration if:

- Amazon notifications go to a different email address (e.g. a spouse's account) and you forward them to your monitored inbox.
- You use a forwarding service (e.g. SimpleLogin, AnonAddy, iCloud Hide My Email) that delivers mail from multiple original senders into a single inbox.
- You want to monitor a shared inbox for packages across multiple email accounts.

---

## Option 1: Forwarding Header Mode

Some email forwarding services preserve the **original sender address** in a custom email header rather than in the `From:` field. When this header is available, the integration matches emails by their original sender, which is more reliable.

**Common header names:**
- `X-Forwarded-To`
- `X-Original-To`
- `Delivered-To`
- `X-SimpleLogin-Original-From`

Check your forwarding service's documentation or inspect a forwarded email's raw headers to find the correct header name.

**Configuration:**

In the integration's Step 2 options, set **Forwarding Header** to the header name your forwarding service uses (e.g. `X-Forwarded-To`). Leave the **Amazon forwarded email addresses** field blank — in header mode, the integration searches for the shipper's original address inside the header value automatically.

---

## Option 2: Address List Mode

If your forwarding service does not preserve the original sender in a header, the integration can expand the search to also match emails that arrived at any of your specified forwarding addresses.

**Configuration:**

Leave the **Forwarding Header** field blank (or set to `(none)`). Enter the original email addresses in the **Amazon forwarded email addresses** field, separated by commas.

---

## Which option to use?

| Situation | Recommended option |
|---|---|
| Forwarding service adds a custom header with the original sender address | Header Mode |
| Simple manual forwarding (e.g. Gmail "forward to") | Address List Mode |
| Unsure | Inspect a forwarded email's raw headers first |
