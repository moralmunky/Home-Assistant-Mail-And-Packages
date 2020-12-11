"""
Based on @skalavala work at
https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html

Configuration code contribution from @firstof9 https://github.com/firstof9/
"""
import logging

from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import const

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[const.DOMAIN][entry.entry_id][const.COORDINATOR]
    unique_id = entry.entry_id
    sensors = []
    resources = entry.data[CONF_RESOURCES]

    for variable in resources:
        sensors.append(PackagesSensor(entry, variable, coordinator, unique_id))

    async_add_entities(sensors, False)


class PackagesSensor(Entity):
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
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._host}_{self._name}_{self._unique_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        value = self.coordinator.data[self.type]
        self.data = self.coordinator.data
        return value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the unit of measurement."""
        return self._icon

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}
        attr[const.ATTR_SERVER] = self._host
        tracking = f"{self.type.split('_')[0]}_tracking"

        if "Amazon" in self._name:
            attr[const.ATTR_ORDER] = self.data[const.AMAZON_ORDER]
        elif "Mail USPS Mail" == self._name:
            attr[const.ATTR_IMAGE] = self.data[const.ATTR_IMAGE_NAME]
        elif "_delivering" in self.type and tracking in self.data.keys():
            attr[const.ATTR_TRACKING_NUM] = self.data[tracking]
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
