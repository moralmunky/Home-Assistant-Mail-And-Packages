"""Binary sensors for Mail and Packages."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import MailAndPackagesConfigEntry
from .const import BINARY_SENSORS, DOMAIN, VERSION
from .entity import MailandPackagesBinarySensorEntityDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: MailAndPackagesConfigEntry, async_add_devices):
    """Initialize binary_sensor platform."""
    coordinator = entry.runtime_data.coordinator
    resources = entry.data.get(CONF_RESOURCES, [])

    binary_sensors = [
        PackagesBinarySensor(value, coordinator, entry)
        for value in BINARY_SENSORS.values()
        if not value.selectable or value.key in resources
    ]
    async_add_devices(binary_sensors, False)


class PackagesBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of an Mail and Packages binary sensor."""

    def __init__(
        self,
        sensor_description: MailandPackagesBinarySensorEntityDescription,
        coordinator: DataUpdateCoordinator,
        config: MailAndPackagesConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._config = config
        self.entity_description = sensor_description
        self._name = sensor_description.name
        self._type = sensor_description.key
        self._unique_id = config.entry_id
        self._host = config.data[CONF_HOST]

        self._attr_name = f"{self._name}"
        self._attr_unique_id = (
            f"binary_sensor_{self._host}_{self._type}_{self._unique_id}"
        )

    @property
    def device_info(self) -> dict:
        """Return device information about the mailbox."""
        return {
            "connections": {(DOMAIN, self._unique_id)},
            "name": self._host,
            "manufacturer": "IMAP E-Mail",
            "sw_version": VERSION,
        }

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        """Return True if the image is updated."""
        if self._type in self.coordinator.data:
            _LOGGER.debug(
                "binary_sensor: %s value: %s",
                self._type,
                self.coordinator.data[self._type],
            )
            return bool(self.coordinator.data[self._type])
        return False
