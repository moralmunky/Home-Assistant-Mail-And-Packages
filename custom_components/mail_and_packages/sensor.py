"""
Based on @skalavala work at
https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html

Configuration code contribution from @firstof9 https://github.com/firstof9/
"""
import logging
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor entities."""
    coordinator = hass.data[const.DOMAIN][entry.entry_id][const.COORDINATOR]
    unique_id = entry.entry_id
    sensors = []
    resources = entry.data[CONF_RESOURCES]

    for variable in resources:
        sensors.append(PackagesSensor(entry, variable, coordinator, unique_id))

    for variable in const.IMAGE_SENSORS:
        sensors.append(ImagePathSensors(hass, entry, variable, coordinator, unique_id))

    async_add_entities(sensors, False)


class PackagesSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(self, config, sensor_type, coordinator, unique_id):
        """Initialize the sensor"""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._config = config
        self._name = const.SENSOR_TYPES[sensor_type][const.SENSOR_NAME]
        self._icon = const.SENSOR_TYPES[sensor_type][const.SENSOR_ICON]
        self._attr_native_unit_of_measurement = const.SENSOR_TYPES[sensor_type][
            const.SENSOR_UNIT
        ]
        self.type = sensor_type
        self._host = config.data[CONF_HOST]
        self._unique_id = unique_id
        self.data = self.coordinator.data

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._host}_{self._name}_{self._unique_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> Optional[int]:
        """Return the state of the sensor."""
        value = None

        if self.type in self.coordinator.data.keys():
            value = self.coordinator.data[self.type]
        else:
            value = None
        return value

    @property
    def icon(self) -> str:
        """Return the unit of measurement."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self) -> Optional[str]:
        """Return device specific state attributes."""
        attr = {}
        attr[const.ATTR_SERVER] = self._host
        tracking = f"{self.type.split('_')[0]}_tracking"
        data = self.coordinator.data

        # Catch no data entries
        if self.data is None:
            return attr

        if "Amazon" in self._name:
            if self._name == "amazon_exception":
                attr[const.ATTR_ORDER] = data[const.AMAZON_EXCEPTION_ORDER]
            else:
                attr[const.ATTR_ORDER] = data[const.AMAZON_ORDER]
        elif self._name == "Mail USPS Mail":
            attr[const.ATTR_IMAGE] = data[const.ATTR_IMAGE_NAME]
        elif "_delivering" in self.type and tracking in self.data.keys():
            attr[const.ATTR_TRACKING_NUM] = data[tracking]
        return attr


class ImagePathSensors(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(self, hass, config, sensor_type, coordinator, unique_id):
        """Initialize the sensor"""
        super().__init__(coordinator)
        self.hass = hass
        self.coordinator = coordinator
        self._config = config
        self._name = const.IMAGE_SENSORS[sensor_type][const.SENSOR_NAME]
        self._icon = const.IMAGE_SENSORS[sensor_type][const.SENSOR_ICON]
        self._attr_native_unit_of_measurement = const.IMAGE_SENSORS[sensor_type][
            const.SENSOR_UNIT
        ]
        self.type = sensor_type
        self._host = config.data[CONF_HOST]
        self._unique_id = unique_id

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._host}_{self._name}_{self._unique_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> Optional[str]:
        """Return the state of the sensor."""
        image = self.coordinator.data[const.ATTR_IMAGE_NAME]
        the_path = None

        if const.ATTR_IMAGE_PATH in self.coordinator.data.keys():
            path = self.coordinator.data[const.ATTR_IMAGE_PATH]
        else:
            path = self._config.data[const.CONF_PATH]

        if self.type == "usps_mail_image_system_path":
            _LOGGER.debug("Updating system image path to: %s", path)
            the_path = f"{self.hass.config.path()}/{path}{image}"
        elif self.type == "usps_mail_image_url":
            if (
                self.hass.config.external_url is None
                and self.hass.config.internal_url is None
            ):
                the_path = None
            elif self.hass.config.external_url is None:
                _LOGGER.warning("External URL not set in configuration.")
                url = self.hass.config.internal_url
                the_path = f"{url.rstrip('/')}/local/mail_and_packages/{image}"
            else:
                url = self.hass.config.external_url
                the_path = f"{url.rstrip('/')}/local/mail_and_packages/{image}"
        return the_path

    @property
    def icon(self) -> str:
        """Return the unit of measurement."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self) -> Optional[str]:
        """Return device specific state attributes."""
        attr = {}
        return attr
