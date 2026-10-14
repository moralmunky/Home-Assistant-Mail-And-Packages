---
name: Migrations vs. Repairs Decision Guidelines
description: Best practices and architectural guidelines for deciding when to use config entry migrations versus repairs flows.
---

# Migrations vs. Repairs Decision Guidelines

This skill documents the rules and architectural lifecycle patterns for deciding whether to use **Config Entry Migrations** (`async_migrate_entry` in `migrate.py`) or **Repairs Issues** (`RepairsFlow` in `repairs.py`) in Home Assistant integrations.

---

## 1. Core Rule & Lifecycle Distinction

| Mechanism | Purpose | User Action Required | Timing / Phase |
| :--- | :--- | :--- | :--- |
| **Repairs Flow (`repairs.py`)** | Warn the user about deprecated settings, breaking changes, or degraded states and allow interactive remediation. | **Yes** (User reviews notification in Settings > System > Repairs and confirms action). | **Deprecation / Transition Phase** (while the old option is deprecated but still operational). |
| **Config Migration (`migrate.py`)** | Automatically transform internal schemas between versions without user interaction. | **No** (Automatic, silent on startup during `async_migrate_entry`). | **Schema Evolution / Removal Phase** (when backwards compatibility is formally dropped or new schema defaults are added). |

---

## 2. When to Use a Repair Flow (`repairs.py`)

Use a Repair Flow when:
1. **Deprecating a user-configurable option**:
   - The user configured a custom path, option, or behavior (e.g. `CONF_STORAGE`, `CONF_ALLOW_EXTERNAL`) that is being phased out.
   - The option still works or falls back gracefully, but the user should be alerted that it will be removed in a future release.
   - Clicking "Submit" in the repair dialog performs the remediation (e.g., removing the deprecated keys from `entry.options` and `entry.data`).
2. **Action requires user confirmation or re-authentication**:
   - The user must provide new credentials (e.g. `auth_failed` triggering `async_start_reauth`).
   - The user must explicitly consent before behavior changes or files are cleaned up.

> [!WARNING]
> **Never combine an active deprecation repair with an automatic version migration that strips the same key.**
> If `async_migrate_entry` automatically deletes the deprecated configuration key on startup, the coordinator's check (e.g. `if CONF_STORAGE in self.config:`) will never evaluate to true, and the user will never see the repair issue notification.

---

## 3. When to Use a Migration (`migrate.py`)

Use a Config Entry Migration when:
1. **Hard Removal Phase (Breaking Changes)**:
   - A previously deprecated feature has reached its scheduled removal release.
   - The repair issue is decommissioned, `CONFIG_VER` is bumped, and any leftover keys from old entries are stripped or mapped to new schemas automatically.
2. **Schema Restructuring**:
   - Moving keys from `entry.data` to `entry.options` (e.g. non-connection options separated from IMAP credentials).
   - Changing types (e.g. converting a comma-separated string `forwarded_emails` into a `list[str]`).
   - Renaming internal keys where no user decision is needed and zero functional degradation occurs.
3. **Adding New Required Defaults**:
   - Introducing a new feature or flag that needs a default value added to existing entries without requiring user intervention.

---

## 4. Repairs Flow Implementation Checklist

When implementing a repair flow in `repairs.py`:
1. **Confirm Dialog Handling**:
   - Home Assistant's `RepairsFlowManager.async_init` invokes `async_step_init(user_input)` with initial data containing `{"issue_id": ...}`.
   - Do **not** forward `user_input` directly from `async_step_init` to `async_step_confirm(user_input)`:
     ```python
     async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
         """Handle the first step of a repair flow."""
         return await self.async_step_confirm()
     ```
     Forwarding `user_input` causes `async_step_confirm` to mistake `{"issue_id": ...}` for form submission, bypassing the confirmation prompt!
2. **Translations**:
   - Every repair issue must define translations in `strings.json` and `translations/en.json` (as well as fallbacks in other translation files) under `"issues"`:
     ```json
     "issues": {
       "<issue_id>": {
         "title": "...",
         "fix_flow": {
           "step": {
             "confirm": {
               "title": "...",
               "description": "..."
             }
           }
         }
       }
     }
     ```
