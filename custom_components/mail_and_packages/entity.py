"""Support for Mail and Packages entities."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntityDescription


@dataclass
class MailandPackagesBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Mail and Packages binary sensor entities."""

    selectable: bool = False
