"""Test Mail and Packages binary sensors."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from tests.const import FAKE_CONFIG_DATA

from unittest.mock import patch


@pytest.mark.asyncio
async def test_binary_sensor_no_updates(hass, mock_imap_no_email):
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
