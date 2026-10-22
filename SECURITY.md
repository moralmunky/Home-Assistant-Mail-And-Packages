# Security Policy

## Supported Versions

Only the latest release of Mail and Packages is actively supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < Latest| :x:                |

## Reporting a Vulnerability

The Mail and Packages team takes security issues seriously. We appreciate your efforts to responsibly disclose any vulnerabilities.

If you discover a security vulnerability in this project:

1. **Do not disclose it publicly** via GitHub issues, discussions, or social media.
2. Please report security vulnerabilities privately using [GitHub Private Vulnerability Reporting](https://github.com/moralmunky/Home-Assistant-Mail-And-Packages/security/advisories/new).
3. If you cannot use GitHub Security Advisories, open an issue asking a maintainer to contact you. Do not include any details about the vulnerability in the issue.

### Security contacts

These people triage private reports:

- @moralmunky (maintainer)
- @firstof9 (maintainer)
- @jasonjhofmann (security triage)

### What to include in your report

Please include as much detail as possible to help us understand and resolve the issue quickly:
- Type of vulnerability and affected component(s).
- Step-by-step instructions or proof-of-concept to reproduce the behavior.
- Any potential impact or exploit scenarios.
- Suggested fix or mitigation, if known.

### What to expect

- **Acknowledgment**: We will review and acknowledge receipt of your report within 48 hours.
- **Assessment**: We will evaluate the report, verify the vulnerability, and keep you informed of our progress.
- **Resolution**: Once a fix is developed and tested, a new release will be published and credit will be given in the release notes / advisory (unless you request anonymity).

## Scope

Anyone can send an email that looks like it came from a carrier or retailer, so treat email content as untrusted input when you assess impact.

In scope:

- Handling of mailbox credentials, including IMAP passwords and Google and Microsoft OAuth tokens.
- Parsing of email headers, bodies, and attachments.
- Images downloaded from links in emails, and files written to the image folder.
- The image endpoint the integration adds to the Home Assistant web server (`/api/mail_and_packages/image/`).
- Data included in diagnostics downloads.

Out of scope:

- Vulnerabilities in Home Assistant itself. Report them through the [Home Assistant security policy](https://www.home-assistant.io/security/).
- Vulnerabilities in third-party libraries. Report them to that library's maintainers.
- Attacks that require control of the Home Assistant host or a Home Assistant login.
