"""Binary sensors for Mail and Packages."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import BINARY_SENSORS, COORDINATOR, DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Initialize binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    binary_sensors = []
    # pylint: disable=unused-variable
    for variable, value in BINARY_SENSORS.items():
        binary_sensors.append(PackagesBinarySensor(value, coordinator, entry))
    async_add_devices(binary_sensors, False)


class PackagesBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of an Mail and Packages binary sensor."""

    def __init__(
        self,
        sensor_description: BinarySensorEntityDescription,
        coordinator: DataUpdateCoordinator,
        config: ConfigEntry,
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
        self._attr_unique_id = f"{self._host}_{self._name}_{self._unique_id}"

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
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        """Return True if the image is updated."""
        if self._type in self.coordinator.data.keys():
            _LOGGER.debug(
                "binary_sensor: %s value: %s",
                self._type,
                self.coordinator.data[self._type],
            )
            return bool(self.coordinator.data[self._type])
        return False
