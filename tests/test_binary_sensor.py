"""Test Mail and Packages binary sensors."""

from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_USPS_DELIVERED


@pytest.mark.asyncio
async def test_binary_sensor_no_updates(
    hass, mock_imap_no_email, entity_registry: er.EntityRegistry
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "mail_and_packages" in hass.config.components

    state = hass.states.get("binary_sensor.usps_image_updated")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.amazon_image_updated")
    assert state
    assert state.state == "off"

    entity_entry = entity_registry.async_get("binary_sensor.usps_mail_delivered")

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["binary_sensor"])
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.usps_mail_delivered")
    assert state
    assert state.state == "off"


@pytest.mark.asyncio
async def test_binary_sensor_mail_delivered(
    hass, mock_imap_usps_mail_delivered, entity_registry: er.EntityRegistry, caplog
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_USPS_DELIVERED,
        version=9,
    )

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "mail_and_packages" in hass.config.components

    state = hass.states.get("binary_sensor.usps_image_updated")
    assert state
    assert state.state == "off"

    state = hass.states.get("binary_sensor.amazon_image_updated")
    assert state
    assert state.state == "off"

    entity_entry = entity_registry.async_get("binary_sensor.usps_mail_delivered")

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    updated_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload the integration
    await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    await hass.config_entries.async_forward_entry_setups(entry, ["binary_sensor"])
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.usps_mail_delivered")
    assert state
    assert state.state == "on"
    assert "binary_sensor: usps_mail_delivered value: 1" in caplog.text


# @pytest.mark.asyncio
# async def test_binary_sensor_updated(hass, mock_update_amazon_image):
#     entry = MockConfigEntry(
#         domain=DOMAIN,
#         title="imap.test.email",
#         data=FAKE_CONFIG_DATA,
#     )

#     entry.add_to_hass(hass)
#     with patch("os.path.exists", return_value=True), patch(
#         "custom_components.mail_and_packages.binary_sensor.hash_file"
#     ) as mock_hash_file:
#         mock_hash_file.side_effect = hash_side_effect
#         assert await hass.config_entries.async_setup(entry.entry_id)
#         await hass.async_block_till_done()
#         assert "mail_and_packages" in hass.config.components

#         state = hass.states.get("binary_sensor.usps_image_updated")
#         assert state
#         assert state.state == "on"

#         state = hass.states.get("binary_sensor.amazon_image_updated")
#         assert state
#         assert state.state == "on"


@pytest.mark.asyncio
def hash_side_effect(value):
    """Side effect value."""
    if "mail_none.gif" in value:
        return "633d7356947eec543c50b76a1852f92427f4dca9"
    elif "no_deliveries.jpg" in value:
        return "633d7356947ffc643c50b76a1852f92427f4dca9"
    else:
        return "133d7356947fec542c50b76b1856f92427f5dca9"
