"""Provide diagnostics for Mail and Packages."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_AMAZON_COOKIES,
    CONF_LLM_API_KEY,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
# Base set of keys to always redact (immutable frozenset)
_BASE_REDACT_KEYS = frozenset(
    {CONF_PASSWORD, CONF_USERNAME, CONF_LLM_API_KEY, CONF_AMAZON_COOKIES}
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry  # pylint: disable=unused-argument
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}
    diag["config"] = config_entry.as_dict()
    return async_redact_data(diag, _BASE_REDACT_KEYS)


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device: DeviceEntry,  # pylint: disable=unused-argument
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Build a per-call redaction set (don't mutate module-level state)
    redact_keys = set(_BASE_REDACT_KEYS)
    for variable in coordinator.data:
        if "tracking" in variable or "order" in variable:
            _LOGGER.debug("Attempting to add: %s for redaction.", variable)
            redact_keys.add(variable)

    _LOGGER.debug("Redacted keys: %s", redact_keys)

    return async_redact_data(coordinator.data, redact_keys)
