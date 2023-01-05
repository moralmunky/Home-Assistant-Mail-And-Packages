"""Based on @skalavala work.

https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html
Configuration code contribution from @firstof9 https://github.com/firstof9/
"""
import datetime
import logging
from datetime import timezone
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AMAZON_EXCEPTION_ORDER,
    AMAZON_ORDER,
    ATTR_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_TRACKING_NUM,
    CONF_PATH,
    COORDINATOR,
    DOMAIN,
    IMAGE_SENSORS,
    SENSOR_TYPES,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    sensors = []
    resources = entry.data[CONF_RESOURCES]

    for variable in resources:
        sensors.append(PackagesSensor(entry, SENSOR_TYPES[variable], coordinator))

    for variable, value in IMAGE_SENSORS.items():
        sensors.append(ImagePathSensors(hass, entry, value, coordinator))

    async_add_entities(sensors, False)


class PackagesSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        config: ConfigEntry,
        sensor_description: SensorEntityDescription,
        coordinator: str,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description
        self.coordinator = coordinator
        self._config = config
        self._name = sensor_description.name
        self.type = sensor_description.key
        self._host = config.data[CONF_HOST]
        self._unique_id = self._config.entry_id
        self.data = self.coordinator.data

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
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._host}_{self._name}_{self._unique_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        value = None

        if self.type in self.coordinator.data.keys():
            value = self.coordinator.data[self.type]
            if self.type == "mail_updated":
                value = datetime.datetime.now(timezone.utc)
        else:
            value = None
        return value

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> Optional[str]:
        """Return device specific state attributes."""
        attr = {}
        tracking = f"{'_'.join(self.type.split('_')[:-1])}_tracking"
        data = self.coordinator.data

        # Catch no data entries
        if self.data is None:
            return attr

        if "Amazon" in self._name:
            if (
                self._name == "amazon_exception"
                and AMAZON_EXCEPTION_ORDER in data.keys()
            ):
                attr[ATTR_ORDER] = data[AMAZON_EXCEPTION_ORDER]
            elif AMAZON_ORDER in data.keys():
                attr[ATTR_ORDER] = data[AMAZON_ORDER]
        elif self._name == "Mail USPS Mail" and ATTR_IMAGE_NAME in data.keys():
            attr[ATTR_IMAGE] = data[ATTR_IMAGE_NAME]
        elif "_delivering" in self.type and tracking in data.keys():
            attr[ATTR_TRACKING_NUM] = data[tracking]
            # TODO: Add Tracking URL when applicable
        return attr


class ImagePathSensors(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        sensor_description: SensorEntityDescription,
        coordinator: str,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description
        self.hass = hass
        self.coordinator = coordinator
        self._config = config
        self._name = sensor_description.name
        self.type = sensor_description.key
        self._host = config.data[CONF_HOST]
        self._unique_id = self._config.entry_id

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
        image = self.coordinator.data[ATTR_IMAGE_NAME]
        the_path = None

        if ATTR_IMAGE_PATH in self.coordinator.data.keys():
            path = self.coordinator.data[ATTR_IMAGE_PATH]
        else:
            path = self._config.data[CONF_PATH]

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
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success
