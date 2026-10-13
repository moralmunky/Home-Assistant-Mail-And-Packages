"""Support for Mail and Packages entities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.const import CONF_HOST, CONF_USERNAME


def mailbox_device_name(data: Mapping[str, Any]) -> str:
    """Return the device name for a mailbox entry.

    Uses the mailbox address so several accounts on the same server
    (e.g. multiple Gmail accounts) get distinct devices and entity IDs.
    Falls back to the server host for entries without a username.
    """
    return data.get(CONF_USERNAME) or data.get(CONF_HOST) or "Mail and Packages"


@dataclass
class MailandPackagesBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Mail and Packages binary sensor entities."""

    selectable: bool = False
