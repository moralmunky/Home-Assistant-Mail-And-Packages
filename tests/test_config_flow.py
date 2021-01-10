""" Test Mail and Packages config flow """
import os

import pytest
from homeassistant import config_entries, setup
from unittest.mock import patch
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from custom_components.mail_and_packages.helpers import (
    _check_ffmpeg,
    _test_login,
    _validate_path,
)
from tests.const import FAKE_CONFIG_DATA


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": ["fakeuser@test.email", "fakeuser2@test.email"],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_form(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert result3["title"] == title
    assert result3["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,step_id_2",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "user",
        ),
    ],
)
async def test_form_connection_error(input_1, step_id_2, hass, mock_imap):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2
        assert result2["errors"] == {"base": "communication"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": True,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": "",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_form_invalid_ffmpeg(
    input_1, step_id_2, input_2, title, data, hass, mock_imap
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "form"
    assert result3["step_id"] == step_id_2
    assert result3["errors"] == {"base": "ffmpeg_not_found"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": True,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": "",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_form_invalid_path(
    input_1, step_id_2, input_2, title, data, hass, mock_imap
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "form"
    assert result3["step_id"] == step_id_2
    assert result3["errors"] == {"base": "invalid_path"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_form_index_error(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap_index_error,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert result3["title"] == title
    assert result3["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_form_index_error_2(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap_index_error_2,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert result3["title"] == title
    assert result3["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_form_mailbox_format2(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap_mailbox_format2,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert result3["title"] == title
    assert result3["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_valid_path():
    result = await _validate_path(os.path.dirname(__file__))
    assert result


async def test_invalid_path():
    result = await _validate_path("/should/fail")
    assert not result


async def test_valid_ffmpeg(test_valid_ffmpeg):
    result = await _check_ffmpeg()
    assert result


async def test_invalid_ffmpeg(test_invalid_ffmpeg):
    result = await _check_ffmpeg()
    assert not result


async def test_imap_login(mock_imap):
    result = await _test_login(
        "127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword"
    )
    assert result


async def test_imap_connection_error(caplog):
    await _test_login("127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword")
    assert (
        "Error connecting into IMAP Server: [Errno 111] Connection refused"
        in caplog.text
    )


async def test_imap_login_error(mock_imap_login_error, caplog):
    await _test_login("127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword")
    assert "Error logging into IMAP Server:" in caplog.text


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "options_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_options_flow(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,step_id_2",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "init",
        ),
    ],
)
async def test_options_flow_connection_error(
    input_1,
    step_id_2,
    hass,
    mock_imap,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2
        assert result2["errors"] == {"base": "communication"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "options_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": True,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_options_flow_invalid_ffmpeg(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "ffmpeg_not_found"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "options_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": True,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_options_flow_invalid_path(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "invalid_path"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "options_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_options_flow_index_error(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap_index_error,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "options_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_options_flow_index_error_2(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap_index_error_2,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "options_2",
            {
                "amazon_fwds": "",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
            "imap.test.email",
            {
                "amazon_fwds": [""],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": True,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "mail_updated",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "amazon_delivered",
                ],
            },
        ),
    ],
)
async def test_options_flow_mailbox_format2(
    input_1,
    step_id_2,
    input_2,
    title,
    data,
    hass,
    mock_imap_mailbox_format2,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}
    # assert result["title"] == title_1

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._validate_path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_1
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()
