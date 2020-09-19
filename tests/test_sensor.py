""" Test Mail and Packages Sensor """
from pytest_homeassistant_custom_component.common import MockConfigEntry
from tests.common import setup_mnp


async def test_sensor(hass, generic_data):
    await setup_mnp(hass, fixture=generic_data)

    state = hass.states.get("sensor.mail_updated")

    assert state
    assert state.state == "Sep-18-2020 06:29 PM"
