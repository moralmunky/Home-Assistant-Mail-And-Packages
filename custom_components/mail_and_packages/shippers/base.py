"""Base Shipper class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from aioimaplib import IMAP4_SSL
from homeassistant.core import HomeAssistant

from custom_components.mail_and_packages.utils.cache import EmailCache


class Shipper(ABC):
    """Base class for shipper-specific parsing logic."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the shipper."""
        self.hass = hass
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the internal name of the shipper."""

    @classmethod
    @abstractmethod
    def handles_sensor(cls, sensor_type: str) -> bool:
        """Return True if this shipper handles the given sensor type."""

    @abstractmethod
    async def process(
        self,
        account: IMAP4_SSL,
        date: str,
        sensor_type: str,
    ) -> dict[str, Any]:
        """Process emails for this shipper on the given date for a specific sensor."""

    @abstractmethod
    async def process_batch(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> dict[str, Any]:
        """Process multiple sensors for this shipper using batched fetching/searching.

        since_date: earliest IMAP SINCE date for _delivering/_exception/_delivered
        sensors. Defaults to date (today) if not provided.
        """
