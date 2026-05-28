# Guidelines for AI Coding Assistants (AGENTS.md)

Welcome! This file provides a repository overview, architecture guidelines, developer environment setup, and styling/workflow standards for AI assistants contributing to this repository.

---

## 1. Project Overview & Architecture

This repository is a **Home Assistant Custom Integration** that connects to an IMAP email server, parses email notifications from various shipping carriers (USPS, FedEx, UPS, DHL, Amazon, Evri/Hermes, etc.), and exposes sensors and cameras to track mail and package deliveries in real-time.

### Core Directory Structure
- `custom_components/mail_and_packages/`: Contains the integration code.
  - `__init__.py`: Component setup, setup entries, unloading, and coordinator.
  - `const.py`: Shared constants, domains, config keys, and sensor descriptions.
  - `config_flow.py`: Setup flows and options flow handlers.
  - `sensor.py`: Home Assistant sensor entities representing delivery counts/status.
  - `camera.py`: Home Assistant camera entities that show mail scans or shipper status images.
  - `shippers/`: Specific parsers matching individual carrier email formats.
  - `utils/`: IMAP connection and query utilities.
  - `manifest.json`: Home Assistant custom component metadata.
- `tests/`: Pytest suite.
  - `conftest.py`: Shared testing fixtures and mock IMAP client overrides.
  - `test_init.py`, `test_config_flow.py`, etc.: Integration and unit tests.

---

## 2. Python Environment & Dependency Management

- **Target Python Version**: **3.13 / 3.14**
- **Environment Tooling**: **`uv`** is the standard tool for environment creation and dependency management.

### Setup and Testing
- Virtual environments are handled using `uv`.
- To install test dependencies:
  ```bash
  uv pip install -r requirements_test.txt
  ```

---

## 3. Code Style, Linting & Type Checking

This codebase uses modern, fast Rust-based tooling for formatting and static analysis:
- **Linter & Formatter**: **Ruff** replaces `black`, `flake8`, `isort`, `pydocstyle`, and `pylint`.
- **Type Checker**: **mypy**.

### Configuration Locations
- Ruff configuration: Configured in `pyproject.toml`.
- Mypy configuration: Configured in `setup.cfg`.

### Local Execution Commands
- To run lint checks:
  ```bash
  ruff check .
  ```
- To run formatting checks:
  ```bash
  ruff format --check .
  ```
- To auto-format and fix autofixable lint errors:
  ```bash
  ruff check --fix . && ruff format .
  ```
- To run type checks:
  ```bash
  mypy custom_components/mail_and_packages/
  ```

---

## 4. Git Hooks (`pre-commit`)

This project uses **`pre-commit`** to run git hooks automatically on commit.
- Hook definitions: [`.pre-commit-config.yaml`](file:///.pre-commit-config.yaml).
- Run all checks manually:
  ```bash
  pre-commit run --all-files
  ```

---

## 5. Test Suite

Unit and integration tests are written with `pytest` and can be orchestrated using `tox` or run directly with `uv`.
- Running tests locally:
  ```bash
  uv run pytest
  ```
- Running tests in isolated environments via tox:
  ```bash
  tox
  ```

---

## 6. CI/CD & Security Hardening Guidelines

When modifying or introducing new GitHub Actions workflows, adhere to the following rules:

### A. Pin Actions to Commit SHAs
Do **NOT** use version tags (e.g., `@v4`, `@master`, `@main`) for Actions. Pin them to full-length 40-character commit SHAs. Use comment tags to document human-readable versions:
```yaml
uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v4.4.4
```

### B. Use Step-Security Harden-Runner
Add `step-security/harden-runner` as the **first step** in every job running on hosted runners to monitor outbound traffic:
```yaml
- name: Harden Runner
  uses: step-security/harden-runner@5c7944e73c4c2a096b17a9cb74d65b6c2bbafbde # v2.9.1
  with:
    egress-policy: audit
```

### C. Restrict GITHUB_TOKEN Permissions
Specify minimal default permissions at the top level of each workflow:
```yaml
permissions:
  contents: read
```

### D. Conventional Commit PR Titles
All pull request titles must follow the Conventional Commits specification (e.g., `feat: ...`, `fix: ...`, `ci: ...`).
- Workflow checks: Managed via the `Semantic PR Check` action in `.github/workflows/semantic-pr.yaml`.
- Auto-labeling: Handled automatically by the built-in autolabeler in `.github/release-drafter.yml`.
