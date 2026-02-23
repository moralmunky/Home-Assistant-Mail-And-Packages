---
name: Bug report
about: Create a report to help us improve
title: 'ISSUE: '
labels: 'pending'
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**Environment (please complete the following information):**
 - Home Assistant installation type: [e.g. OS/Container/Core/Supervised]
 - Home Assistant version: [e.g. 2024.12.0]
 - Mail and Packages version: [e.g. 0.4.0]
 - Email provider: [e.g. Gmail/Outlook/Yahoo/Self-hosted]

**Which features are you using?**
- [ ] Core carrier email parsing (USPS, UPS, FedEx, etc.)
- [ ] USPS Informed Delivery images
- [ ] Universal email scanning (scan all emails)
- [ ] Tracking service forwarding (17track/AfterShip/AliExpress)
- [ ] AI/LLM email analysis (Ollama/Anthropic/OpenAI)
- [ ] Amazon cookie tracking

**Logs**
Enable debug logging and paste relevant output:
```yaml
logger:
  logs:
    custom_components.mail_and_packages: debug
```

```
Paste your error logs here.
```

**Diagnostics**
If possible, download and attach diagnostics from:
Settings > Devices & Services > Mail and Packages > 3-dot menu > Download Diagnostics

(Sensitive data like credentials and tracking numbers are automatically redacted.)

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Additional context**
Add any other context about the problem here.
Please add emails in plain/text format if possible and applicable.
