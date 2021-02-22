"""
Based on @skalavala work at
https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html

Configuration code contribution from @firstof9 https://github.com/firstof9/
"""
import logging
from typing import Any, Optional

from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[const.DOMAIN][entry.entry_id][const.COORDINATOR]
    unique_id = entry.entry_id
    sensors = []
    resources = entry.data[CONF_RESOURCES]

    for variable in resources:
        sensors.append(PackagesSensor(entry, variable, coordinator, unique_id))

    for variable in const.IMAGE_SENSORS:
        sensors.append(ImagePathSensors(hass, entry, variable, coordinator, unique_id))

    async_add_entities(sensors, False)


class PackagesSensor(CoordinatorEntity):
    """ Represntation of a sensor """

    def __init__(self, config, sensor_type, coordinator, unique_id):
        """ Initialize the sensor """
        self.coordinator = coordinator
        self._config = config
        self._name = const.SENSOR_TYPES[sensor_type][const.SENSOR_NAME]
        self._icon = const.SENSOR_TYPES[sensor_type][const.SENSOR_ICON]
        self._unit_of_measurement = const.SENSOR_TYPES[sensor_type][const.SENSOR_UNIT]
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
    def state(self) -> Optional[int]:
        """Return the state of the sensor."""
        if self.type in self.coordinator.data.keys():
            return self.coordinator.data[self.type]
        else:
            return None

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

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

        if "Amazon" in self._name:
            attr[const.ATTR_ORDER] = data[const.AMAZON_ORDER]
        elif "Mail USPS Mail" == self._name:
            attr[const.ATTR_IMAGE] = data[const.ATTR_IMAGE_NAME]
        elif "_delivering" in self.type and tracking in self.data.keys():
            attr[const.ATTR_TRACKING_NUM] = data[tracking]
        return attr

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

class ImagePathSensors(CoordinatorEntity):
    """ Represntation of a sensor """

    def __init__(self, hass, config, sensor_type, coordinator, unique_id):
        """ Initialize the sensor """
        self.hass = hass
        self.coordinator = coordinator
        self._config = config
        self._name = const.IMAGE_SENSORS[sensor_type][const.SENSOR_NAME]
        self._icon = const.IMAGE_SENSORS[sensor_type][const.SENSOR_ICON]
        self._unit_of_measurement = const.IMAGE_SENSORS[sensor_type][const.SENSOR_UNIT]
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
    def state(self) -> Optional[str]:
        """Return the state of the sensor."""
        image = self.coordinator.data[const.ATTR_IMAGE_NAME]

        if const.ATTR_IMAGE_PATH in self.coordinator.data.keys():
            path = self.coordinator.data[const.ATTR_IMAGE_PATH]
        else:
            path = self._config.data[const.CONF_PATH]

        if self.type == "usps_mail_image_system_path":
            _LOGGER.debug("Updating system image path to: %s", path)
            return f"{self.hass.config.path()}/{path}{image}"
        elif self.type == "usps_mail_image_url":
            if (
                self.hass.config.external_url is None
                and self.hass.config.internal_url is None
            ):
                return None
            elif self.hass.config.external_url is None:
                _LOGGER.warn("External URL not set in configuration.")
                url = self.hass.config.internal_url
                return f"{url.lstrip('/')}/local/mail_and_packages/{image}"
            url = self.hass.config.external_url
            return f"{url.lstrip('/')}/local/mail_and_packages/{image}"
        else:
            return None

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

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

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
