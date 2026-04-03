"""Based on @skalavala work.

https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html
Configuration code contribution from @firstof9 https://github.com/firstof9/
"""

import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MailAndPackagesConfigEntry
from .const import (
    AMAZON_EXCEPTION,
    AMAZON_ORDER,
    ATTR_GRID_IMAGE_NAME,
    ATTR_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_TRACKING_NUM,
    ATTR_USPS_IMAGE,
    CONF_PATH,
    DOMAIN,
    IMAGE_SENSORS,
    SENSOR_TYPES,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass,
    entry: MailAndPackagesConfigEntry,
    async_add_entities,
):
    """Set up the sensor entities."""
    coordinator = entry.runtime_data.coordinator
    resources = entry.data.get(CONF_RESOURCES, [])

    sensors = [
        PackagesSensor(entry, SENSOR_TYPES[variable], coordinator)
        for variable in resources
        if variable in SENSOR_TYPES
    ]

    sensors.extend(
        ImagePathSensors(hass, entry, value, coordinator)
        for value in IMAGE_SENSORS.values()
    )

    async_add_entities(sensors, False)


class PackagesSensor(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        config: ConfigEntry,
        sensor_description: SensorEntityDescription,
        coordinator: Any,
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
        parts = self.type.split("_")
        if len(parts) > 1:
            self._tracking_key = f"{'_'.join(parts[:-1])}_tracking"
        else:
            self._tracking_key = f"{self.type}_tracking"

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
        return f"sensor_{self._host}_{self.type}_{self._unique_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self.type)

        if self.type == "mail_updated":
            # Safely handle string vs datetime to prevent ValueError
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except ValueError:
                    value = datetime.datetime.now(datetime.UTC)
            elif value is None:
                value = datetime.datetime.now(datetime.UTC)
        return value

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> str | None:
        """Return device specific state attributes."""
        attr = {}
        data = self.coordinator.data

        if (
            any(sensor in self.type for sensor in ["_delivering", "_delivered"])
            and self._tracking_key in data
        ):
            attr[ATTR_TRACKING_NUM] = data[self._tracking_key]

        # Catch no data entries
        if self.data is None:
            return attr

        if "Amazon" in self._name:
            if self.type == AMAZON_EXCEPTION and ATTR_ORDER in data:
                attr[ATTR_ORDER] = data[ATTR_ORDER]
            elif AMAZON_ORDER in data:
                attr[ATTR_ORDER] = data[AMAZON_ORDER]
        elif self._name == "Mail USPS Mail" and ATTR_IMAGE_NAME in data:
            attr[ATTR_IMAGE] = data[ATTR_IMAGE_NAME]

        return attr


class ImagePathSensors(CoordinatorEntity, SensorEntity):
    """Representation of a sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigEntry,
        sensor_description: SensorEntityDescription,
        coordinator: Any,
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
        return f"sensor_{self._host}_{self.type}_{self._unique_id}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        image = ""
        the_path = None

        image = self.coordinator.data.get(ATTR_USPS_IMAGE)

        grid_image = self.coordinator.data.get(ATTR_GRID_IMAGE_NAME)

        path = self.coordinator.data.get(
            ATTR_IMAGE_PATH,
            self._config.data.get(CONF_PATH),
        )

        if self.type == "usps_mail_image_system_path" and image:
            _LOGGER.debug("Updating system image path to: %s", path)
            the_path = f"{self.hass.config.path()}/{path}{image}"
        elif self.type == "usps_mail_grid_image_path" and grid_image:
            _LOGGER.debug("Updating grid image path to: %s", path)
            the_path = f"{self.hass.config.path()}/{path}{grid_image}"
        elif self.type == "usps_mail_image_url" and image:
            if (
                self.hass.config.external_url is None
                and self.hass.config.internal_url is None
            ):
                the_path = None
            elif self.hass.config.external_url is None:
                _LOGGER.debug("External URL not set in configuration.")
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
        return self.coordinator.data is not None
