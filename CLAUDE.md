# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mail and Packages is a Home Assistant custom integration (HACS-compatible) that creates sensors for mail and package tracking. It connects to an IMAP email server, parses shipping notification emails from 13 supported carriers (USPS, UPS, FedEx, Amazon, DHL, Canada Post, Hermes, Royal Mail, Australia Post, Poczta Polska, InPost, DPD, GLS), and creates sensors showing delivery counts and statuses. It also generates animated GIFs from USPS Informed Delivery mail images.

## Privacy-First Principle (CRITICAL)

All processing MUST be local by default. No data (email content, images, tracking numbers, personal information) may ever be sent to the internet, external services, or AI unless the user is fully informed and explicitly opts in. This is a non-negotiable requirement for every code change. When adding any feature that could involve external communication, it must be off by default and require clear user consent to enable.

## Build & Test Commands

```bash
# Full test suite via tox
tox

# Run tests directly
pytest --timeout=30 --cov=custom_components/mail_and_packages/ --cov-report=xml

# Single test file
pytest tests/test_helpers.py

# Single test function
pytest tests/test_helpers.py::test_function_name -v

# Lint (all at once)
tox -e lint

# Lint individually
black --check custom_components/mail_and_packages/
flake8 custom_components/mail_and_packages/
pylint custom_components/mail_and_packages/
pydocstyle custom_components/mail_and_packages/ tests/

# Type checking
tox -e mypy

# Format code
black custom_components/mail_and_packages/
isort custom_components/mail_and_packages/
```

## Architecture

### Core Files (`custom_components/mail_and_packages/`)

- **`__init__.py`** — Entry point. `MailDataUpdateCoordinator` (extends HA's `DataUpdateCoordinator`) periodically calls `process_emails` from helpers. Handles config entry setup/unload, config migration (versions 1–6), package registry service registration (`clear_package`, `clear_all_delivered`, `mark_delivered`, `add_package`), and registry reconciliation with event firing.
- **`helpers.py`** — Core business logic. `process_emails()` orchestrates IMAP email processing. `fetch()` recursively resolves sensor dependencies. `get_count()` matches emails by sender/subject. `get_mails()` extracts USPS Informed Delivery images and builds GIFs. Also contains `forward_to_tracking_service()`, `llm_scan_emails()`, `scrape_amazon_tracking()`, `scan_emails_for_registry()`, and `reconcile_registry()`.
- **`const.py`** — All constants: `SENSOR_DATA` (per-carrier email matching rules), `SENSOR_TYPES` (HA sensor entity descriptions), `UNIVERSAL_TRACKING_PATTERNS` (regex per carrier), `TRACKING_SERVICES` (17track/AfterShip/AliExpress config), Amazon-specific patterns.
- **`sensor.py`** — `PackagesSensor` (delivery counts), `ImagePathSensors` (USPS mail image paths), `RegistrySensor` (package registry aggregates). All extend `CoordinatorEntity`.
- **`camera.py`** — `MailCam` entity for USPS mail GIFs and Amazon delivery images. Has `update_image` service.
- **`config_flow.py`** — 3-step config wizard: (1) IMAP credentials, (2) sensor/folder/image settings, (3) advanced tracking (registry, universal scanning, LLM, tracking forwarding, Amazon cookies). Options flow mirrors this.
- **`registry.py`** — Persistent package tracking via HA's `Store` API. Status lifecycle: `detected` → `in_transit` → `out_for_delivery` → `delivered` → `cleared`. Forward-only transitions, auto-expiry (3 days delivered, 14 days detected), UID-based dedup.
- **`diagnostics.py`** — Automatic redaction of credentials, tracking numbers, and cookies.

### Key Design Patterns

- **Sensor dependency resolution**: `fetch()` in helpers.py recursively computes derived values. `*_packages` = `*_delivering` + `*_delivered`. `zpackages_delivered` and `zpackages_transit` aggregate across all carriers.
- **Email matching**: `SENSOR_DATA` in const.py defines per-carrier rules with `email` (sender), `subject` (pattern), and optional `body` (body text) fields. Some sensors (e.g., `dhl_delivered`) require body text matching in addition to subject.
- **Image pipeline**: USPS Informed Delivery attachments → resize to 724x320 → animated GIF (imageio). UUID filenames for security. Optional MP4 via ffmpeg subprocess.
- **Timeout resilience**: When IMAP times out and previous data exists, the coordinator returns stale data instead of raising `UpdateFailed`, keeping sensors available.
- **Advanced features (all opt-in, disabled by default)**: Universal email scanning, tracking service forwarding (17track/AfterShip/AliExpress), LLM-based extraction (Ollama/Anthropic/OpenAI), Amazon cookie-based tracking, persistent package registry.

### Adding a New Carrier

1. Add email matching rules to `SENSOR_DATA` in `const.py`
2. Add sensor entity descriptions to `SENSOR_TYPES` in `const.py`
3. Add the carrier prefix to `SHIPPERS` in `const.py`
4. Optionally add a universal tracking pattern to `UNIVERSAL_TRACKING_PATTERNS` in `const.py`
5. Add test email samples to `tests/test_emails/`
6. Add test cases to `tests/test_helpers.py`
7. Update the supported carriers table in `README.md`

### Testing

Tests use `pytest-homeassistant-custom-component` for the HA test harness. Fixtures in `tests/conftest.py` mock IMAP connections with sample `.eml` files from `tests/test_emails/`. Key test files: `test_helpers.py` (email matching), `test_config_flow.py` (config wizard), `test_registry.py` (package lifecycle), `test_timeout_resilience.py` (IMAP timeout handling).

## Code Style

- Formatter: **black** (line length 88)
- Import sorting: **isort** (black-compatible profile)
- PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `refactor:`, `docs:`)
- Branch PRs from `dev`, not `master`

## Version Bumps

When releasing a new version, **both** of these files must be updated in sync:

1. **`custom_components/mail_and_packages/manifest.json`** → `"version"` field (shown as "Version" on the HA integration page)
2. **`custom_components/mail_and_packages/const.py`** → `VERSION` constant (used as `sw_version` / "Firmware" on HA device entries)

These must always match. The release workflow updates them automatically, but manual releases or hotfixes require updating both.

## Configuration

- Config entry version: 6
- Platforms: `sensor`, `camera`
- Dependencies: `imageio`, `python-resize-image` (PIL)
- YAML configuration is disabled; setup is UI-only via config flow
