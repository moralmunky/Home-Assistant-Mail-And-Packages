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
        value._host = "imap.test.email"
        mock_update.return_value = value
        yield mock_update


@pytest.fixture()
def mock_login_test():
    """ Mock email server login check. """
    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", autospec=True
    ) as mock_login_test:
        mock_login_test.return_value = True
        yield mock_login_test
