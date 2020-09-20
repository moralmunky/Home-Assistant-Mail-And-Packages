""" Fixtures for Mail and Packages tests. """

from tests.const import FAKE_UPDATE_DATA
import pytest
from pytest_homeassistant_custom_component.async_mock import patch

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture()
def mock_generic_data():
    """ Mock email data update class values. """
    with patch("custom_components.mail_and_packages.EmailData.update") as mock_update:
        yield mock_update
