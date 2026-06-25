---
name: Shipper Integration Guidelines
description: Rules and patterns for extending carrier email parsers, registering constants, and writing tests for shippers.
---

# Shipper Integration Guidelines

This skill defines the requirements for adding or updating carrier-specific shippers (email parsers) within this integration.

## Guidelines

### 1. Extending the Base Shipper Class
* All shipper implementations should reside in the `custom_components/mail_and_packages/shippers/` directory.
* Shippers must inherit from the base `GenericShipper` class found in `generic.py`.
* Override the `process` method to define specific parsing logic, or inherit the base email search logic by defining standard configuration keys.

### 2. Configuration & Constant Registration
* All shipper names, attributes, sensor names, and defaults must be registered in the central constants file: [const.py](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/custom_components/mail_and_packages/const.py).
* Do not hardcode shipper-specific identifiers directly in the coordinator or generic files.

### 3. Testing New Shippers
* Create a corresponding test file under `tests/shippers/` (e.g. `test_new_shipper.py`).
* Use the shared mock fixtures and mock IMAP client overrides defined in [conftest.py](file:///home/firstof9/github/Home-Assistant-Mail-And-Packages/tests/conftest.py).
* Verify that email content parsing, sensor values, and edge cases (such as subject mismatches or empty bodies) are fully covered.
