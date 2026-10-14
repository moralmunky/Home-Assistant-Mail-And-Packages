"""Repairs platform for Mail and Packages."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ALLOW_EXTERNAL, CONF_PATH, CONF_STORAGE
from .summary import mailbox_entries


class AuthRepairFlow(RepairsFlow):
    """Handler for repairs flow."""

    def __init__(self, entry_id: str | None) -> None:
        """Initialize."""
        self.entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle confirm step."""
        if user_input is not None:
            if self.entry_id:
                entry = self.hass.config_entries.async_get_entry(self.entry_id)
            else:
                entries = mailbox_entries(self.hass)
                entry = entries[0] if entries else None

            if entry:
                entry.async_start_reauth(self.hass)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


class DeprecatedAllowExternalRepairFlow(RepairsFlow):
    """Handler for deprecated allow_external repair flow."""

    def __init__(self, entry_id: str | None) -> None:
        """Initialize."""
        self.entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle confirm step to disable allow_external."""
        if user_input is not None:
            if self.entry_id:
                entry = self.hass.config_entries.async_get_entry(self.entry_id)
            else:
                entries = mailbox_entries(self.hass)
                entry = entries[0] if entries else None

            if entry:
                if CONF_ALLOW_EXTERNAL in entry.options:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        options={**entry.options, CONF_ALLOW_EXTERNAL: False},
                    )
                elif CONF_ALLOW_EXTERNAL in entry.data:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_ALLOW_EXTERNAL: False},
                    )

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


class DeprecatedStorageRepairFlow(RepairsFlow):
    """Handler for deprecated storage repair flow."""

    def __init__(self, entry_id: str | None) -> None:
        """Initialize."""
        self.entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle confirm step to remove deprecated storage configuration."""
        if user_input is not None:
            entry = (
                self.hass.config_entries.async_get_entry(self.entry_id)
                if self.entry_id
                else (mailbox_entries(self.hass) or [None])[0]
            )

            if entry:
                new_options = {
                    k: v
                    for k, v in entry.options.items()
                    if k not in (CONF_STORAGE, CONF_PATH)
                }
                new_data = {
                    k: v
                    for k, v in entry.data.items()
                    if k not in (CONF_STORAGE, CONF_PATH)
                }
                updates: dict[str, Any] = {}
                if new_options != entry.options:
                    updates["options"] = new_options
                if new_data != entry.data:
                    updates["data"] = new_data
                if updates:
                    self.hass.config_entries.async_update_entry(entry, **updates)

            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create a flow to fix a specific issue."""
    entry_id = data.get("entry_id") if data else None
    if issue_id == "auth_failed":
        return AuthRepairFlow(entry_id)
    if issue_id == "deprecated_allow_external":
        return DeprecatedAllowExternalRepairFlow(entry_id)
    if issue_id == "deprecated_storage":
        return DeprecatedStorageRepairFlow(entry_id)
    raise ValueError(f"Unknown issue {issue_id}")
