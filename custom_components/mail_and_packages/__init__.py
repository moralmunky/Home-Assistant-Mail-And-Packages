"""Mail and Packages Integration."""
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.config_entries import ConfigEntry


async def async_setup(hass: HomeAssistantType, config: ConfigEntry) -> bool:
    """ Disallow configuration via YAML """

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Load the saved entities."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True
