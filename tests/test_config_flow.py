""" Test Mail and Packages config flow """

from unittest.mock import patch

import pytest
from homeassistant import config_entries, setup
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.config_flow import _validate_user_input
from custom_components.mail_and_packages.const import (
    CONF_AMAZON_COOKIES,
    CONF_AMAZON_COOKIES_ENABLED,
    CONF_AMAZON_COOKIE_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_GENERATE_MP4,
    CONF_IMAP_TIMEOUT,
    CONF_LLM_API_KEY,
    CONF_LLM_ENABLED,
    CONF_LLM_ENDPOINT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_SCAN_ALL_EMAILS,
    CONF_SCAN_INTERVAL,
    CONF_TRACKING_FORWARD_ENABLED,
    CONF_TRACKING_SERVICE,
    CONF_TRACKING_SERVICE_ENTRY_ID,
    DOMAIN,
)
from custom_components.mail_and_packages.helpers import _check_ffmpeg, _test_login
from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_BAD

# Common resource list used across tests
RESOURCE_LIST = [
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
    "auspost_delivered",
    "auspost_delivering",
    "auspost_packages",
    "poczta_polska_delivering",
    "poczta_polska_packages",
    "inpost_pl_delivered",
    "inpost_pl_delivering",
    "inpost_pl_packages",
]


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,input_custom_img,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": True,
            },
            {},
            {
                "custom_img_file": "images/test.gif",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": ["fakeuser@test.email", "fakeuser2@test.email"],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_form(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
    input_custom_img,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow.path",
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_4"

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "config_5"

        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_features
        )
        assert result6["type"] == "form"
        assert result6["step_id"] == "config_6"

        result7 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_custom_img
        )

    assert result7["type"] == "create_entry"
    assert result7["title"] == title
    assert result7["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,input_custom_img,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": True,
            },
            {},
            {
                "custom_img_file": "images/test.gif",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": ["fakeuser@test.email", "fakeuser2@test.email"],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_form_invalid_custom_img_path(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
    input_custom_img,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_4"

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "config_5"

        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_features
        )
        assert result6["type"] == "form"
        assert result6["step_id"] == "config_6"

        result7 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_custom_img
        )

    # Custom image file not found: config flow auto-disables custom_img
    # and creates the entry so the user isn't stuck (no back button).
    assert result7["type"] == "create_entry"
    assert result7["title"] == title
    assert result7["data"]["custom_img"] is False


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
    "input_1,input_sensors,input_scanning,input_images,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": True,
                "allow_external": False,
                "custom_img": False,
            },
            "imap.test.email",
            {
                "amazon_days": 3,
                "amazon_fwds": [],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_form_invalid_ffmpeg(
    input_1, input_sensors, input_scanning, input_images, title, data, hass, mock_imap
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login",
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_4"

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_images
        )

    assert result5["type"] == "form"
    assert result5["step_id"] == "config_4"
    assert result5["errors"] == {CONF_GENERATE_MP4: "ffmpeg_not_found"}


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "custom_img": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_form_index_error(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_4"

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "config_5"

        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_features
        )

    assert result6["type"] == "create_entry"
    assert result6["title"] == title
    assert result6["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": False,
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_form_index_error_2(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_4"

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "config_5"

        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_features
        )

    assert result6["type"] == "create_entry"
    assert result6["title"] == title
    assert result6["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "custom_img": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_form_mailbox_format2(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_4"

        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "config_5"

        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_features
        )

    assert result6["type"] == "create_entry"
    assert result6["title"] == title
    assert result6["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


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
    assert "Error connecting into IMAP Server:" in caplog.text


async def test_imap_login_error(mock_imap_login_error, caplog):
    await _test_login("127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword")
    assert "Error logging into IMAP Server:" in caplog.text


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,input_custom_img,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 15,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": True,
            },
            {},
            {
                "custom_img_file": "images/test.gif",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_timeout": 30,
                "scan_interval": 15,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
    input_custom_img,
    title,
    data,
    hass,
    mock_imap,
    mock_update,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow.path",
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
        await hass.async_block_till_done()

        assert result2["type"] == "form"
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        await hass.async_block_till_done()

        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        await hass.async_block_till_done()

        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )
        await hass.async_block_till_done()

        assert result5["type"] == "form"
        assert result5["step_id"] == "options_5"

        result6 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_features
        )
        await hass.async_block_till_done()

        assert result6["type"] == "form"
        assert result6["step_id"] == "options_6"

        result7 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_custom_img
        )
        await hass.async_block_till_done()
        assert result7["type"] == "create_entry"
        assert data == entry.options.copy()

        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,input_custom_img,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 15,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": True,
            },
            {},
            {
                "custom_img_file": "images/test.gif",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_timeout": 30,
                "scan_interval": 15,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow_invalid_custom_img_path(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
    input_custom_img,
    title,
    data,
    hass,
    mock_imap,
    mock_update,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA,
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        await hass.async_block_till_done()

        assert result2["type"] == "form"
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        await hass.async_block_till_done()

        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        await hass.async_block_till_done()

        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )
        await hass.async_block_till_done()

        assert result5["type"] == "form"
        assert result5["step_id"] == "options_5"

        result6 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_features
        )
        await hass.async_block_till_done()

        assert result6["type"] == "form"
        assert result6["step_id"] == "options_6"

        result7 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_custom_img
        )

        # Custom image file not found: options flow auto-disables custom_img
        # and creates the entry so the user isn't stuck (no back button).
        assert result7["type"] == "create_entry"


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
    "input_1,input_sensors,input_scanning,input_images,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": True,
                "allow_external": False,
                "custom_img": False,
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": False,
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow_invalid_ffmpeg(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )

    assert result5["type"] == "form"
    assert result5["errors"] == {CONF_GENERATE_MP4: "ffmpeg_not_found"}


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": False,
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow_index_error(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "options_5"

        result6 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_features
        )

    assert result6["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": False,
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow_index_error_2(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "options_5"

        result6 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_features
        )

    assert result6["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": [],
                "custom_img": False,
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow_mailbox_format2(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
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

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )
        assert result5["type"] == "form"
        assert result5["step_id"] == "options_5"

        result6 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_features
        )

    assert result6["type"] == "create_entry"
    assert entry.options == data
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning,input_images,input_features,title,data",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 15,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
            {},
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_fwds": ['""'],
                "custom_img": False,
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_timeout": 30,
                "scan_interval": 15,
                "resources": RESOURCE_LIST,
            },
        ),
    ],
)
async def test_options_flow_bad(
    input_1,
    input_sensors,
    input_scanning,
    input_images,
    input_features,
    title,
    data,
    hass,
    mock_imap,
    mock_update,
):
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=FAKE_CONFIG_DATA_BAD,
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        await hass.async_block_till_done()

        assert result2["type"] == "form"
        assert result2["step_id"] == "options_2"

        result3 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_sensors
        )
        await hass.async_block_till_done()

        assert result3["type"] == "form"
        assert result3["step_id"] == "options_3"

        result4 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_scanning
        )
        await hass.async_block_till_done()

        assert result4["type"] == "form"
        assert result4["step_id"] == "options_4"

        result5 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_images
        )
        await hass.async_block_till_done()

        assert result5["type"] == "form"
        assert result5["step_id"] == "options_5"

        result6 = await hass.config_entries.options.async_configure(
            result["flow_id"], input_features
        )
        await hass.async_block_till_done()

    assert result6["type"] == "create_entry"
    assert data == entry.options.copy()


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "testemail@amazon.com",
                "amazon_days": 3,
            },
        ),
    ],
)
async def test_form_amazon_error(
    input_1,
    input_sensors,
    input_scanning,
    mock_imap,
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_3"
        assert result4["errors"] == {CONF_AMAZON_FWDS: "amazon_domain"}


@pytest.mark.parametrize(
    "input_1,input_sensors,input_scanning",
    [
        (
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            {
                "folder": '"INBOX"',
                "resources": RESOURCE_LIST,
            },
            {
                "scan_interval": 1,
                "imap_timeout": 9,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
        ),
    ],
)
async def test_form_interval_low(
    input_1,
    input_sensors,
    input_scanning,
    mock_imap,
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
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
        assert result2["step_id"] == "config_2"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_sensors
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "config_3"

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_scanning
        )
        assert result4["type"] == "form"
        assert result4["step_id"] == "config_3"
        assert result4["errors"] == {
            CONF_SCAN_INTERVAL: "scan_too_low",
            CONF_IMAP_TIMEOUT: "timeout_too_low",
        }


# --- Migration tests ---


async def test_migration_v1_to_v6_cascade(hass, mock_imap, mock_update):
    """Test migration from version 1 cascades through to version 6.

    This verifies the fix for the cascade bug where the local `version`
    variable prevented 4->6 migration from running after 1->4.
    """
    # Version 1 config: missing many new fields
    v1_data = {
        "host": "imap.test.email",
        "port": 993,
        "username": "user@fake.email",
        "password": "suchfakemuchpassword",
        "folder": '"INBOX"',
        "resources": ["usps_mail"],
        "amazon_fwds": "fakeuser@fake.email",
        "custom_img": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "image_name": "mail_today.gif",
        "image_path": "/old/path/",
        "image_security": False,
        "scan_interval": 20,
        "imap_timeout": 30,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v1_data,
        version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # After migration, version should be 6 (not stuck at 4)
    assert entry.version == 6

    # Advanced tracking defaults should be present (from 4->6 migration)
    assert CONF_SCAN_ALL_EMAILS in entry.data
    assert entry.data[CONF_SCAN_ALL_EMAILS] is False
    assert CONF_TRACKING_FORWARD_ENABLED in entry.data
    assert entry.data[CONF_TRACKING_FORWARD_ENABLED] is False
    assert CONF_TRACKING_SERVICE in entry.data
    assert CONF_LLM_ENABLED in entry.data
    assert entry.data[CONF_LLM_ENABLED] is False
    assert CONF_AMAZON_COOKIES_ENABLED in entry.data
    assert entry.data[CONF_AMAZON_COOKIES_ENABLED] is False

    # Image security should have been forced on
    assert entry.data.get("image_security") is True

    # Amazon fwds should have been converted to list
    assert isinstance(entry.data.get("amazon_fwds"), list)


async def test_migration_v4_to_v6(hass, mock_imap, mock_update):
    """Test migration from version 4 adds advanced tracking defaults."""
    v4_data = dict(FAKE_CONFIG_DATA)
    v4_data["image_path"] = "custom_components/mail_and_packages/images/"
    v4_data["image_security"] = True
    v4_data["image_name"] = "mail_today.gif"

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v4_data,
        version=4,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 6
    assert CONF_SCAN_ALL_EMAILS in entry.data
    assert CONF_LLM_ENABLED in entry.data
    assert CONF_LLM_PROVIDER in entry.data
    assert entry.data[CONF_LLM_PROVIDER] == "ollama"
    assert CONF_AMAZON_COOKIES_ENABLED in entry.data


# --- Data preservation tests ---


async def test_setup_entry_backfills_missing_fields(
    hass, mock_imap, mock_update
):
    """Test that async_setup_entry backfills missing fields with defaults.

    Old config entries may not have all fields. Setup should add
    them without overwriting existing values.
    """
    minimal_data = {
        "host": "imap.test.email",
        "port": 993,
        "username": "user@fake.email",
        "password": "suchfakemuchpassword",
        "folder": '"INBOX"',
        "resources": ["usps_mail"],
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "scan_interval": 20,
        "imap_timeout": 30,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=minimal_data,
        version=6,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify backfilled fields exist and have safe defaults
    assert entry.data.get(CONF_AMAZON_FWDS) == []
    assert entry.data.get(CONF_SCAN_ALL_EMAILS) is False
    assert entry.data.get(CONF_TRACKING_FORWARD_ENABLED) is False
    assert entry.data.get(CONF_LLM_ENABLED) is False
    assert entry.data.get(CONF_LLM_PROVIDER) == "ollama"
    assert entry.data.get(CONF_LLM_ENDPOINT) == "http://localhost:11434"
    assert entry.data.get(CONF_AMAZON_COOKIES_ENABLED) is False
    assert entry.data.get(CONF_AMAZON_COOKIE_DOMAIN) == "amazon.com"

    # Verify existing values were NOT overwritten
    assert entry.data["host"] == "imap.test.email"
    assert entry.data["scan_interval"] == 20
    assert entry.data["imap_timeout"] == 30


async def test_setup_entry_preserves_existing_advanced_settings(
    hass, mock_imap, mock_update
):
    """Test that setup doesn't overwrite existing advanced settings."""
    data_with_advanced = dict(FAKE_CONFIG_DATA)
    data_with_advanced.update(
        {
            "image_name": "mail_today.gif",
            "image_path": "custom_components/mail_and_packages/images/",
            "image_security": True,
            CONF_SCAN_ALL_EMAILS: True,
            CONF_TRACKING_FORWARD_ENABLED: True,
            CONF_TRACKING_SERVICE: "aftership",
            CONF_TRACKING_SERVICE_ENTRY_ID: "abc-123",
            CONF_LLM_ENABLED: True,
            CONF_LLM_PROVIDER: "anthropic",
            CONF_LLM_ENDPOINT: "https://api.anthropic.com",
            CONF_LLM_API_KEY: "sk-test",
            CONF_LLM_MODEL: "claude-3",
            CONF_AMAZON_COOKIES_ENABLED: True,
            CONF_AMAZON_COOKIES: "session=abc",
            CONF_AMAZON_COOKIE_DOMAIN: "amazon.co.uk",
        }
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=data_with_advanced,
        version=6,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify all advanced settings were preserved (not overwritten by defaults)
    assert entry.data[CONF_SCAN_ALL_EMAILS] is True
    assert entry.data[CONF_TRACKING_FORWARD_ENABLED] is True
    assert entry.data[CONF_TRACKING_SERVICE] == "aftership"
    assert entry.data[CONF_TRACKING_SERVICE_ENTRY_ID] == "abc-123"
    assert entry.data[CONF_LLM_ENABLED] is True
    assert entry.data[CONF_LLM_PROVIDER] == "anthropic"
    assert entry.data[CONF_LLM_ENDPOINT] == "https://api.anthropic.com"
    assert entry.data[CONF_LLM_API_KEY] == "sk-test"
    assert entry.data[CONF_LLM_MODEL] == "claude-3"
    assert entry.data[CONF_AMAZON_COOKIES_ENABLED] is True
    assert entry.data[CONF_AMAZON_COOKIES] == "session=abc"
    assert entry.data[CONF_AMAZON_COOKIE_DOMAIN] == "amazon.co.uk"


async def test_ffmpeg_auto_disable_on_config(mock_imap, hass):
    """Test ffmpeg validation auto-disables MP4 and shows error.

    When ffmpeg is not found, generate_mp4 should be set to False
    in the returned user_input so the form re-shows with it unchecked.
    The user can submit again to continue without MP4.
    """
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=False,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ):
        # Step 1: IMAP
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
        )
        # Step 2: Sensors
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"folder": '"INBOX"', "resources": ["usps_mail"]},
        )
        # Step 3: Scanning
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "scan_interval": 20,
                "imap_timeout": 30,
                "amazon_fwds": "",
                "amazon_days": 3,
            },
        )
        # Step 4: Images - enable MP4 (ffmpeg missing)
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "gif_duration": 5,
                "generate_mp4": True,
                "allow_external": False,
                "custom_img": False,
            },
        )
        # Error shown but generate_mp4 auto-disabled
        assert result5["type"] == "form"
        assert result5["step_id"] == "config_4"
        assert result5["errors"] == {CONF_GENERATE_MP4: "ffmpeg_not_found"}

        # Re-submit with generate_mp4 now False - should proceed
        result6 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "gif_duration": 5,
                "generate_mp4": False,
                "allow_external": False,
                "custom_img": False,
            },
        )
        assert result6["type"] == "form"
        assert result6["step_id"] == "config_5"

        # Step 5: no advanced features
        result7 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )
        assert result7["type"] == "create_entry"
        assert result7["data"]["generate_mp4"] is False
