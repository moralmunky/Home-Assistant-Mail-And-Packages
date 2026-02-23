# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mail and Packages is a Home Assistant custom integration (HACS-compatible) that creates sensors for mail and package tracking. It connects to an IMAP email server, parses shipping notification emails from supported carriers (USPS, UPS, FedEx, Amazon, DHL, Canada Post, Hermes, Royal Mail, Australia Post, and several Polish carriers), and creates sensors showing delivery counts and statuses. It also generates animated GIFs from USPS Informed Delivery mail images.

## Build & Test Commands

**Run all tests via tox:**
```bash
tox
```

**Run tests directly with pytest:**
```bash
pytest --timeout=30 --cov=custom_components/mail_and_packages/ --cov-report=xml
```

**Run a single test file:**
```bash
pytest tests/test_helpers.py
```

**Run a single test:**
```bash
pytest tests/test_helpers.py::test_function_name -v
```

**Lint (via tox):**
```bash
tox -e lint
```

**Lint individually:**
```bash
black --check custom_components/mail_and_packages/
flake8 custom_components/mail_and_packages/
pylint custom_components/mail_and_packages/
pydocstyle custom_components/mail_and_packages/ tests/
```

**Type checking:**
```bash
tox -e mypy
```

**Format code:**
```bash
black custom_components/mail_and_packages/
isort custom_components/mail_and_packages/
```

## Architecture

### Integration Structure (`custom_components/mail_and_packages/`)

- **`__init__.py`** - Entry point. Sets up `MailDataUpdateCoordinator` (extends Home Assistant's `DataUpdateCoordinator`) which periodically calls `process_emails` from helpers. Handles config entry setup/unload and config migration (versions 1-4).
- **`helpers.py`** - Core business logic. Contains all IMAP email processing: `process_emails()` is the main entry, `fetch()` recursively resolves sensor dependencies (e.g., `_packages` depends on `_delivering` + `_delivered`), `get_count()` searches emails by sender/subject, and `get_mails()` handles USPS Informed Delivery image extraction and GIF generation.
- **`sensor.py`** - Defines `PackagesSensor` (delivery counts) and `ImagePathSensors` (USPS mail image paths). Both extend `CoordinatorEntity`.
- **`camera.py`** - `MailCam` entity displaying USPS mail and Amazon delivery images. Supports a `update_image` service call.
- **`config_flow.py`** - Multi-step config flow (3 steps: IMAP credentials, sensor/folder selection, optional custom image). Also implements options flow for reconfiguration.
- **`const.py`** - All constants including `SENSOR_DATA` (email matching rules per carrier: sender addresses, subject line patterns, body text patterns) and `SENSOR_TYPES` (Home Assistant sensor entity descriptions).
- **`diagnostics.py`** - Diagnostics support with automatic redaction of credentials and tracking numbers.

### Key Design Patterns

- **Sensor dependency resolution**: The `fetch()` function in helpers.py recursively resolves sensor values. `*_packages` sensors sum `*_delivering` + `*_delivered`. `*_delivering` subtracts `*_delivered` from raw email count. `zpackages_delivered` and `zpackages_transit` aggregate across all carriers.
- **Email matching**: `SENSOR_DATA` in const.py defines per-carrier rules with `email` (sender), `subject` (subject line match), and optional `body` (body text match) fields. Some sensors like `dhl_delivered` require body text matching in addition to subject matching.
- **Image pipeline**: USPS Informed Delivery emails have image attachments extracted, resized to 724x320, and combined into an animated GIF. Filenames use UUIDs for security. Optional MP4 generation via ffmpeg subprocess.

### Testing

Tests use `pytest-homeassistant-custom-component` which provides the Home Assistant test harness. Test fixtures in `tests/conftest.py` mock IMAP connections with sample `.eml` files from `tests/test_emails/`. Each fixture configures `imaplib.IMAP4_SSL` mock with specific email responses for different carrier scenarios.

### Configuration

- Config flow version: 4
- Platforms: `sensor`, `camera`
- Dependencies: `imageio`, `python-resize-image` (PIL)
- YAML configuration is disabled; setup is UI-only via config flow

## Code Style

- Formatter: **black** (line length 88)
- Import sorting: **isort** (profile compatible with black)
- PR titles must follow [conventional commits](https://www.conventionalcommits.org/) (enforced by `semantic-pull-request` action)
- Branch PRs from `dev`, not `master`
