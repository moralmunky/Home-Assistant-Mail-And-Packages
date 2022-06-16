"""Binary sensors for Mail and Packages."""
import logging
import os

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

from .helpers import hash_file

from .const import (
    ATTR_AMAZON_IMAGE,
    ATTR_IMAGE_NAME,
    BINARY_SENSORS,
    COORDINATOR,
    DOMAIN,
    VERSION,
)

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
    def is_on(self) -> bool:
        """Return True if the image is updated."""
        if self._type == "usps_update":
            if ATTR_IMAGE_NAME in self.coordinator.data.keys():
                usps_image = self.coordinator.data[ATTR_IMAGE_NAME]
                usps_none = f"{os.path.dirname(__file__)}/mail_none.gif"
                usps_check = os.path.exists(usps_image)
                if usps_check:
                    image_hash = hash_file(usps_image)
                    none_hash = hash_file(usps_none)

                    _LOGGER.debug("USPS Image hash: %s", image_hash)
                    _LOGGER.debug("USPS None hash: %s", none_hash)

                    if image_hash != none_hash:
                        return True
                return False

        if self._type == "amazon_update":
            if ATTR_AMAZON_IMAGE in self.coordinator.data.keys():
                amazon_image = self.coordinator.data[ATTR_AMAZON_IMAGE]
                amazon_none = f"{os.path.dirname(__file__)}/no_deliveries.jpg"
                amazon_check = os.path.exists(amazon_image)
                if amazon_check:
                    image_hash = hash_file(amazon_image)
                    none_hash = hash_file(amazon_none)

                    _LOGGER.debug("Amazon Image hash: %s", image_hash)
                    _LOGGER.debug("Amazon None hash: %s", none_hash)

                    if image_hash != none_hash:
                        return True
                return False
        return False
