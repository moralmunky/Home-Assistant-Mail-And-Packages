"""Based on @skalavala work.

https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html
Configuration code contribution from @firstof9 https://github.com/firstof9/
"""

import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MailAndPackagesConfigEntry
from .const import (
    AMAZON_DELIVERING,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_ORDER,
    AMAZON_HUB,
    AMAZON_HUB_CODE,
    AMAZON_ORDER,
    AMAZON_OTP,
    AMAZON_OTP_CODE,
    ATTR_CODE,
    ATTR_EMAIL,
    ATTR_GRID_IMAGE_NAME,
    ATTR_IMAGE,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_SUBJECT,
    ATTR_TRACKING_NUM,
    ATTR_USPS_IMAGE,
    CONF_PATH,
    DOMAIN,
    IMAGE_SENSORS,
    SENSOR_DATA,
    SENSOR_TYPES,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

DELIVERED_SUFFIXES = {"delivered"}


async def async_setup_entry(
    hass,
    entry: MailAndPackagesConfigEntry,
    async_add_entities,
):
    """Set up the sensor entities."""
    coordinator = entry.runtime_data.coordinator
    resources = coordinator.config.get(CONF_RESOURCES, [])

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


class PackagesSensor(CoordinatorEntity, RestoreSensor):
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
            prefix = "_".join(parts[:-1])
            if parts[-1] in DELIVERED_SUFFIXES:
                self._tracking_key = f"{prefix}_delivered_tracking"
            elif parts[-1] == "packages":
                packages_cfg = SENSOR_DATA.get(self.type, {})
                # IMAP-backed packages (e.g. DHL "ist unterwegs") keep their
                # own tracking list; empty-config packages still mirror OFD.
                if packages_cfg.get(ATTR_EMAIL) or packages_cfg.get(ATTR_SUBJECT):
                    self._tracking_key = f"{self.type}_tracking"
                else:
                    self._tracking_key = f"{prefix}_tracking"
            else:
                self._tracking_key = f"{prefix}_tracking"
        else:
            self._tracking_key = f"{self.type}_tracking"

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        await super().async_added_to_hass()
        if (sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = sensor_data.native_value

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
        if self.coordinator.data is None:
            return getattr(self, "_attr_native_value", None)
        value = self.coordinator.data.get(self.type)

        if self.type == "mail_updated":
            # Safely handle string vs datetime to prevent ValueError
            if isinstance(value, str):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except ValueError:
                    value = datetime.datetime.now(datetime.UTC)
            elif value is None and getattr(self, "_attr_native_value", None) is None:
                value = datetime.datetime.now(datetime.UTC)

        if value is not None:
            self._attr_native_value = value
        return getattr(self, "_attr_native_value", None)

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def extra_state_attributes(self) -> str | None:
        """Return device specific state attributes."""
        attr = {}
        data = self.coordinator.data
        if data is None:
            return attr

        if any(
            sensor in self.type
            for sensor in ["_delivering", "_delivered", "_packages", "_exception"]
        ):
            if tracking := data.get(self._tracking_key):
                attr[ATTR_TRACKING_NUM] = tracking

        if "Amazon" in self._name:
            self._add_amazon_attributes(attr, data)
        elif self._name == "Mail USPS Mail":
            if image_name := data.get(ATTR_IMAGE_NAME):
                attr[ATTR_IMAGE] = image_name

        return attr

    def _add_amazon_attributes(self, attr: dict, data: dict) -> None:
        """Add Amazon specific attributes to the sensor."""
        if self.type == AMAZON_EXCEPTION:
            if order := data.get(AMAZON_EXCEPTION_ORDER, data.get(ATTR_ORDER)):
                attr[ATTR_ORDER] = order
        elif self.type == AMAZON_DELIVERING:
            if order := data.get("amazon_delivering_order"):
                attr[ATTR_ORDER] = order
        elif order := data.get(AMAZON_ORDER):
            attr[ATTR_ORDER] = order
        elif self.type == AMAZON_HUB:
            if code := data.get(AMAZON_HUB_CODE, data.get(ATTR_CODE)):
                attr[ATTR_CODE] = code
        elif self.type == AMAZON_OTP:
            if code := data.get(AMAZON_OTP_CODE, data.get(ATTR_CODE)):
                attr[ATTR_CODE] = code


class ImagePathSensors(CoordinatorEntity, RestoreSensor):
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

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        await super().async_added_to_hass()
        if (sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = sensor_data.native_value

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
        if self.coordinator.data is None:
            return getattr(self, "_attr_native_value", None)

        image = self.coordinator.data.get(ATTR_USPS_IMAGE)

        grid_image = self.coordinator.data.get(ATTR_GRID_IMAGE_NAME)

        path = self.coordinator.data.get(
            ATTR_IMAGE_PATH,
            self.coordinator.config.get(CONF_PATH),
        )

        the_path = None

        if self.type == "usps_mail_image_system_path" and image:
            _LOGGER.debug("Updating system image path to: %s", path)
            the_path = self.hass.config.path(path, image)
        elif self.type == "usps_mail_grid_image_path" and grid_image:
            _LOGGER.debug("Updating grid image path to: %s", path)
            the_path = self.hass.config.path(path, grid_image)
        elif self.type == "usps_mail_image_url" and image:
            url = self._get_base_url()
            if url:
                the_path = f"{url.rstrip('/')}/local/mail_and_packages/{image}"

        if the_path is not None:
            self._attr_native_value = the_path

        return getattr(self, "_attr_native_value", None)

    def _get_base_url(self) -> str | None:
        """Return the best available base URL for building image links."""
        try:
            return get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            _LOGGER.debug("No URL available for image link.")
            return None

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False
