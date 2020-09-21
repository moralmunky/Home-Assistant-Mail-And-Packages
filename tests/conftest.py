""" Fixtures for Mail and Packages tests. """

from tests.const import FAKE_UPDATE_DATA
import pytest
from pytest_homeassistant_custom_component.async_mock import AsyncMock, patch

from unittest.mock import Mock

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture()
def mock_update():
    """ Mock email data update class values. """
    with patch(
        "custom_components.mail_and_packages.EmailData", autospec=True
    ) as mock_update:
        value = Mock()
        value._data = FAKE_UPDATE_DATA
        mock_update.return_value = value
        yield mock_update
