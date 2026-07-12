"""Repairs platform for Mail and Packages."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class AuthRepairFlow(RepairsFlow):
    """Handler for repairs flow."""

    def __init__(self, entry_id: str | None) -> None:
        """Initialize."""
        self.entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a repair flow."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle confirm step."""
        if user_input is not None:
            if self.entry_id:
                entry = self.hass.config_entries.async_get_entry(self.entry_id)
            else:
                entries = self.hass.config_entries.async_entries(DOMAIN)
                entry = entries[0] if entries else None

            if entry:
                entry.async_start_reauth(self.hass)
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
    if issue_id == "auth_failed":
        entry_id = data.get("entry_id") if data else None
        return AuthRepairFlow(entry_id)
    raise ValueError(f"Unknown issue {issue_id}")
