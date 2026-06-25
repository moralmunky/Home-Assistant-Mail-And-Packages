---
name: Home Assistant Modernization Standards
description: Guidelines for adhering to modern Home Assistant lifecycle and component structure rules (like runtime_data).
---

# Home Assistant Modernization Standards

This skill ensures that all changes and additions to this integration align with modern Home Assistant development practices, lifecycle methods, and architecture requirements.

## Guidelines

### 1. Replaces `hass.data` with `ConfigEntry.runtime_data`
* For Home Assistant core version compatibility, always store active runtime data (like the coordinator instance) using the typed `ConfigEntry.runtime_data` pattern instead of storing objects globally in `hass.data[DOMAIN]`.

### 2. Async Lifecycle & Config Entry Setup
* During config entry setup (`async_setup_entry`), ensure any network-dependent actions (like connecting to the IMAP server) are managed cleanly.
* Do not perform blocking, synchronous updates directly during setup. Leverage `DataUpdateCoordinator` and handle first-refresh behavior carefully to avoid triggering Home Assistant's configuration entry setup timeouts (`CancelledError`).

### 3. Graceful Property Access
* All sensor and camera entities should handle situations where the coordinator has no data (`self.coordinator.data is None`) gracefully. Return appropriate defaults (e.g. `None` or `0`) rather than raising a `TypeError` or `AttributeError`.
