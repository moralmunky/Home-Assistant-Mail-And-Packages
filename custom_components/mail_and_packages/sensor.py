"""Based on @skalavala work.

https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html
Configuration code contribution from @firstof9 https://github.com/firstof9/
"""

import datetime
from datetime import timezone
import logging
from typing import Any, Optional

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AMAZON_EXCEPTION_ORDER,
    AMAZON_ORDER,
    ATTR_17TRACK_FORWARDED,
    ATTR_AMAZON_COOKIE_TRACKING,
    ATTR_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_TRACKING_NUM,
    ATTR_UNIVERSAL_TRACKING,
    CONF_ALLOW_EXTERNAL,
    CONF_PATH,
    CONF_REGISTRY_ENABLED,
    DOMAIN,
    IMAGE_SENSORS,
    SENSOR_TYPES,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


REGISTRY_SENSORS = ("registry_tracked", "registry_in_transit", "registry_delivered")


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor entities."""
    coordinator = entry.runtime_data.coordinator
    sensors = []
    resources = entry.data[CONF_RESOURCES]

    for variable in resources:
        sensors.append(PackagesSensor(entry, SENSOR_TYPES[variable], coordinator))

    for variable, value in IMAGE_SENSORS.items():
        sensors.append(ImagePathSensors(hass, entry, value, coordinator))

    # Add registry sensors if package registry is enabled
    if entry.data.get(CONF_REGISTRY_ENABLED, False):
        for key in REGISTRY_SENSORS:
            sensors.append(RegistrySensor(entry, SENSOR_TYPES[key], coordinator))

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
            if self._name == "amazon_exception":
                attr[ATTR_ORDER] = data[AMAZON_EXCEPTION_ORDER]
            else:
                attr[ATTR_ORDER] = data[AMAZON_ORDER]
        elif self._name == "Mail USPS Mail":
            attr[ATTR_IMAGE] = data[ATTR_IMAGE_NAME]
        elif "_delivering" in self.type and tracking in self.data.keys():
            attr[ATTR_TRACKING_NUM] = data[tracking]
        elif self.type == "email_tracking_numbers":
            if ATTR_UNIVERSAL_TRACKING in data:
                attr[ATTR_TRACKING_NUM] = data[ATTR_UNIVERSAL_TRACKING]
            if "universal_carrier_map" in data:
                attr["carrier_map"] = data["universal_carrier_map"]
        elif self.type == "tracking_service_forwarded":
            if ATTR_17TRACK_FORWARDED in data:
                attr[ATTR_TRACKING_NUM] = data[ATTR_17TRACK_FORWARDED]
        elif self.type == "amazon_cookie_packages":
            if ATTR_AMAZON_COOKIE_TRACKING in data:
                attr[ATTR_TRACKING_NUM] = data[ATTR_AMAZON_COOKIE_TRACKING]
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
            # Use authenticated camera proxy URL by default (private).
            # Only use /local/ (unauthenticated) if allow_external is enabled,
            # since that copies images to www/ for public access.
            if self._config.data.get(CONF_ALLOW_EXTERNAL):
                url = self.hass.config.external_url or self.hass.config.internal_url
                if url:
                    the_path = f"{url.rstrip('/')}/local/mail_and_packages/{image}"
            else:
                url = self.hass.config.external_url or self.hass.config.internal_url
                if url:
                    the_path = (
                        f"{url.rstrip('/')}"
                        f"/api/camera_proxy/camera.mail_usps_camera"
                    )
        return the_path

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success


class RegistrySensor(CoordinatorEntity, SensorEntity):
    """Sensor backed by the persistent package registry."""

    def __init__(
        self,
        config: ConfigEntry,
        sensor_description: SensorEntityDescription,
        coordinator: str,
    ):
        """Initialize the registry sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description
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
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data and self.type in self.coordinator.data:
            return self.coordinator.data[self.type]
        return 0

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> Optional[dict]:
        """Return detailed package list as attributes."""
        data = self.coordinator.data
        if data is None:
            return {}

        attr_key_map = {
            "registry_tracked": "registry_packages_list",
            "registry_in_transit": "registry_in_transit_list",
            "registry_delivered": "registry_delivered_list",
        }

        attr_key = attr_key_map.get(self.type)
        if attr_key and attr_key in data:
            return {"packages": data[attr_key]}
        return {}
