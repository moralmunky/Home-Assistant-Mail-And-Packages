"""Binary sensors for Mail and Packages."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import COORDINATOR, DOMAIN, VERSION
from .entity import MailandPackagesBinarySensorEntityDescription

_LOGGER = logging.getLogger(__name__)

BINARY_SENSORS = {
    "usps_update": MailandPackagesBinarySensorEntityDescription(
        name="USPS Image Updated",
        key="usps_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        selectable=False,
        entity_registry_enabled_default=False,
    ),
    "amazon_update": MailandPackagesBinarySensorEntityDescription(
        name="Amazon Image Updated",
        key="amazon_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        selectable=False,
        entity_registry_enabled_default=False,
    ),
    "usps_mail_delivered": MailandPackagesBinarySensorEntityDescription(
        name="USPS Mail Delivered",
        key="usps_mail_delivered",
        entity_registry_enabled_default=False,
        selectable=True,
    ),
}


async def async_setup_entry(hass, entry, async_add_devices):
    """Initialize binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    binary_sensors = [
        PackagesBinarySensor(value, coordinator, entry)
        for value in BINARY_SENSORS.values()
    ]
    async_add_devices(binary_sensors, False)


class PackagesBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of an Mail and Packages binary sensor."""

    def __init__(
        self,
        sensor_description: MailandPackagesBinarySensorEntityDescription,
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
