"""Models for Mail and Packages coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from custom_components.mail_and_packages.coordinator import (
        MailDataUpdateCoordinator,
    )


@dataclass
class MailAndPackagesData:
    """Data for Mail and Packages integration."""

    coordinator: MailDataUpdateCoordinator
    cameras: list
    last_options: dict | None = None
    last_data: dict | None = None


type MailAndPackagesConfigEntry = ConfigEntry[MailAndPackagesData]
