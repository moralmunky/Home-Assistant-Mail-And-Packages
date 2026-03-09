"""Provide diagnostics for Mail and Packages."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_AMAZON_FWDS, COORDINATOR, DOMAIN
from . import MailAndPackagesConfigEntry

_LOGGER = logging.getLogger(__name__)
REDACT_KEYS = {CONF_PASSWORD, CONF_USERNAME, CONF_AMAZON_FWDS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MailAndPackagesConfigEntry,  # pylint: disable=unused-argument
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}
    diag["config"] = config_entry.as_dict()
    return async_redact_data(diag, REDACT_KEYS)


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: MailAndPackagesConfigEntry,
    device: DeviceEntry,  # pylint: disable=unused-argument
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = config_entry.runtime_data.coordinator

    for variable in coordinator.data:
        if "tracking" in variable or "order" in variable:
            _LOGGER.debug("Attempting to add: %s for redaction.", variable)
            REDACT_KEYS.add(variable)

    _LOGGER.debug("Redacted keys: %s", REDACT_KEYS)

    return async_redact_data(coordinator.data, REDACT_KEYS)
