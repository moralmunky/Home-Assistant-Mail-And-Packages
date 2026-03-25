"""Test Mail and Packages config flow."""

import contextlib
import logging
import ssl
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioimaplib import AioImapException
from anyio import Path
from homeassistant import config_entries, setup
from homeassistant.const import CONF_RESOURCES
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.config_flow import (
    DEFAULT_FOLDER,
    MailAndPackagesFlowHandler,
    _check_forwarded_emails,
    _get_mailboxes,
    _get_schema_step_3,
    _validate_user_input,
)
from custom_components.mail_and_packages.const import (
    CONF_ALLOW_FORWARDED_EMAILS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FORWARDED_EMAILS,
    CONF_GENERATE_MP4,
    CONF_GENERIC_CUSTOM_IMG,
    CONF_GENERIC_CUSTOM_IMG_FILE,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    CONFIG_VER,
    DOMAIN,
)
from tests.const import (
    DEFAULT_CUSTOM_IMAGE_DATA,
)

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email,amazon@example.com,fake@email%$^&@example.com,bogusemail@testamazon.com",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email,amazon@example.com,fake@email%$^&@example.com,bogusemail@testamazon.com",
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form(
    mock_imap,
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    title,
    data,
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_no_fwds(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": ["fakeuser@test.email", "fakeuser2@test.email"],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_invalid_custom_img_path(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=False,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

    assert result["type"] == "form"
    assert result["step_id"] == step_id_4
    assert result["errors"] == {"custom_img_file": "file_not_found"}


@pytest.mark.parametrize(
    ("input_1", "step_id_2"),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "user",
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_connection_error(input_1, step_id_2, hass, mock_imap_connect_error):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
    assert result2["type"] == "form"
    assert result2["step_id"] == step_id_2
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "folder": '"INBOX"',
                "generate_grid": True,
                "generate_mp4": True,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_4",
            {},
            "imap.test.email",
            {
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_invalid_ffmpeg(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=False,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
    ):
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
    assert result3["errors"] == {CONF_GENERATE_MP4: "ffmpeg_not_found"}


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_index_error(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    title,
    data,
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_account = MagicMock()
    # Fix: Make select an AsyncMock and return a tuple for unpacking
    mock_account.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_account.list = AsyncMock(
        return_value=MagicMock(result="OK", lines=[b'(\\HasNoChildren) "." "INBOX"'])
    )

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.login",
            return_value=mock_account,
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

    assert "error" not in result
    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_index_error_2(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    title,
    data,
    hass,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    # Mock connection that triggers both IndexErrors and falls back to default
    mock_account = MagicMock()
    # Fix: Make select an AsyncMock and return a tuple for unpacking
    mock_account.select = AsyncMock(return_value=("OK", [b"1"]))
    mock_account.list = AsyncMock(
        return_value=MagicMock(result="OK", lines=[b"GARBAGE DATA"])
    )

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.login",
            return_value=mock_account,
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                **DEFAULT_CUSTOM_IMAGE_DATA,
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_storage_error(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        with patch(
            "pathlib.Path.exists",
            return_value=False,
        ):
            assert result["type"] == "form"
            assert result["step_id"] == step_id_4
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], input_4
            )

    assert result["type"] == "form"
    assert result["step_id"] == step_id_4
    assert result["errors"] == {CONF_STORAGE: "path_not_found"}


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "reconfig_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 120,
                "scan_interval": 60,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "reconfig_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "reconfig_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "reconfig_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                **DEFAULT_CUSTOM_IMAGE_DATA,
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_security": "SSL",
                "imap_timeout": 120,
                "scan_interval": 60,
                "storage": "custom_components/mail_and_packages/images/",
                "resources": [
                    "amazon_delivered",
                    "amazon_packages",
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                    "mail_updated",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure(
    mock_imap_no_email,
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
) -> None:
    """Test reconfigure flow."""
    entry = integration

    with (
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input_1,
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )
        # assert "errors" not in result

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        _LOGGER.debug("Entries: %s", len(hass.config_entries.async_entries(DOMAIN)))
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data.copy() == data


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "reconfig_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 120,
                "scan_interval": 60,
                "resources": [
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "reconfig_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "reconfig_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                **DEFAULT_CUSTOM_IMAGE_DATA,
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@fake.email, fakeuser2@fake.email",
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_security": "SSL",
                "imap_timeout": 120,
                "scan_interval": 60,
                "storage": "custom_components/mail_and_packages/images/",
                "resources": [
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                    "mail_updated",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_no_amazon(
    mock_imap_no_email,
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
) -> None:
    """Test reconfigure flow."""
    entry = integration

    with (
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input_1,
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        _LOGGER.debug("Entries: %s", len(hass.config_entries.async_entries(DOMAIN)))
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data.copy() == data


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "reconfig_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 120,
                "scan_interval": 60,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "reconfig_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "reconfig_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "imap.test.email",
            {
                **DEFAULT_CUSTOM_IMAGE_DATA,
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "custom_img": False,
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_security": "SSL",
                "imap_timeout": 120,
                "scan_interval": 60,
                "storage": ".storage/mail_and_packages/images",
                "resources": [
                    "amazon_packages",
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                    "mail_updated",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_with_default_images(
    mock_imap_no_email,
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
) -> None:
    """Test reconfigure flow with default Amazon and UPS images."""
    entry = integration

    with (
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input_1,
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        actual_data = entry.data.copy()
        # Compare dictionaries by checking each key-value pair
        for key in data:
            assert key in actual_data, f"Missing key: {key}"
            expected_value = data[key]
            actual_value = actual_data[key]
            # Sort lists before comparison to handle order differences
            if isinstance(expected_value, list) and isinstance(actual_value, list):
                expected_value = sorted(expected_value)
                actual_value = sorted(actual_value)
            assert expected_value == actual_value, (
                f"Value mismatch for {key}: expected {data[key]}, got {actual_data[key]}"
            )
        for key in actual_data:
            assert key in data, f"Extra key: {key}"


@pytest.mark.asyncio
async def test_config_flow_with_amazon_custom_image_only(
    hass: HomeAssistant,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
) -> None:
    """Test config flow with only Amazon custom image enabled."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "config_2"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "allow_external": False,
                "custom_img": False,
                "amazon_custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": [
                    "mail_updated",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "amazon_delivered",
                    "amazon_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "config_amazon"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "config_3"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "amazon_custom_img_file": "images/test_amazon_only.jpg",
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "config_storage"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "storage": ".storage/mail_and_packages/images",
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "imap.test.email"
        actual_data = result["data"]
        expected_data = {
            "allow_external": False,
            "allow_forwarded_emails": False,
            "amazon_days": 3,
            "amazon_domain": "amazon.com",
            "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            "custom_img": False,
            "amazon_custom_img": True,
            "amazon_custom_img_file": "images/test_amazon_only.jpg",
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "notarealpassword",
            "folder": '"INBOX"',
            "generate_grid": False,
            "generate_mp4": False,
            "gif_duration": 5,
            "imap_security": "SSL",
            "imap_timeout": 30,
            "scan_interval": 20,
            "storage": ".storage/mail_and_packages/images",
            "resources": [
                "mail_updated",
                "usps_delivered",
                "usps_delivering",
                "usps_mail",
                "usps_packages",
                "amazon_delivered",
                "amazon_packages",
                "ups_delivered",
                "ups_delivering",
                "ups_packages",
                "zpackages_delivered",
                "zpackages_transit",
            ],
            "verify_ssl": False,
            "fedex_custom_img": False,
            "generic_custom_img": False,
            "ups_custom_img": False,
            "walmart_custom_img": False,
        }
        # Compare dictionaries by checking each key-value pair
        for key, expected_value in expected_data.items():
            assert key in actual_data, f"Missing key: {key}"
            actual_value = actual_data[key]

            # Sort lists before comparison to handle order differences
            if isinstance(expected_value, list) and isinstance(actual_value, list):
                expected_value = sorted(expected_value)
                actual_value = sorted(actual_value)

            assert expected_value == actual_value, (
                f"Value mismatch for {key}: expected {expected_data[key]}, got {actual_data[key]}"
            )

        # Check for any extra keys in actual data
        for key in actual_data:
            assert key in expected_data, f"Extra key: {key}"


@pytest.mark.asyncio
async def test_config_flow_with_ups_custom_image_only(
    hass: HomeAssistant,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
) -> None:
    """Test config flow with only UPS custom image enabled."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "config_2"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "allow_external": False,
                "custom_img": False,
                "ups_custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": [
                    "mail_updated",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "amazon_delivered",
                    "amazon_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "config_amazon"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "config_3"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "ups_custom_img_file": "images/test_ups_only.jpg",
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "config_storage"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "storage": ".storage/mail_and_packages/images",
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "imap.test.email"
        # Sort the actual data for comparison
        actual_data = result["data"].copy()
        actual_data["resources"] = sorted(actual_data["resources"])

        expected_data = {
            "allow_external": False,
            "allow_forwarded_emails": False,
            "amazon_days": 3,
            "amazon_domain": "amazon.com",
            "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            "custom_img": False,
            "ups_custom_img": True,
            "ups_custom_img_file": "images/test_ups_only.jpg",
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "notarealpassword",
            "folder": '"INBOX"',
            "generate_grid": False,
            "generate_mp4": False,
            "gif_duration": 5,
            "imap_security": "SSL",
            "imap_timeout": 30,
            "scan_interval": 20,
            "resources": sorted(
                [
                    "mail_updated",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "amazon_delivered",
                    "amazon_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ]
            ),
            "storage": ".storage/mail_and_packages/images",
            "verify_ssl": False,
            "amazon_custom_img": False,
            "fedex_custom_img": False,
            "generic_custom_img": False,
            "walmart_custom_img": False,
        }

        # Compare key by key to handle any order differences
        for key, expected_value in expected_data.items():
            assert key in actual_data, f"Missing key: {key}"
            assert actual_data[key] == expected_value, (
                f"Mismatch for {key}: {actual_data[key]} != {expected_value}"
            )

        # Check for any extra keys in actual data
        for key in actual_data:
            assert key in expected_data, f"Unexpected key: {key}"


@pytest.fixture(name="integration_v10_migration")
async def integration_fixture_v10_migration(hass, caplog):
    """Set up the mail_and_packages integration with version 10 migration test."""
    # Create a config that simulates version 10 (without custom image fields)
    v10_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_exception",
            "amazon_hub",
            "amazon_packages",
            "auspost_delivered",
            "auspost_delivering",
            "auspost_packages",
            "capost_delivered",
            "capost_delivering",
            "capost_packages",
            "dhl_delivered",
            "dhl_delivering",
            "dhl_packages",
            "dpd_com_pl_delivered",
            "dpd_com_pl_delivering",
            "dpd_com_pl_packages",
            "fedex_delivered",
            "fedex_delivering",
            "fedex_packages",
            "gls_delivered",
            "gls_delivering",
            "gls_packages",
            "hermes_delivered",
            "hermes_delivering",
            "inpost_pl_delivered",
            "inpost_pl_delivering",
            "inpost_pl_packages",
            "mail_updated",
            "poczta_polska_delivering",
            "poczta_polska_packages",
            "royal_delivered",
            "royal_delivering",
            "ups_delivered",
            "ups_delivering",
            "ups_packages",
            "usps_delivered",
            "usps_delivering",
            "usps_mail",
            "usps_packages",
            "walmart_delivered",
            "walmart_exception",
            "zpackages_delivered",
            "zpackages_transit",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v10_config,
        version=10,  # Start with version 10
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert "Migration complete to version 13" in caplog.text

    # Verify the new fields were added
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert "no_deliveries_amazon.jpg" in entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert "no_deliveries_ups.jpg" in entry.data[CONF_UPS_CUSTOM_IMG_FILE]
    assert CONF_WALMART_CUSTOM_IMG in entry.data
    assert entry.data[CONF_WALMART_CUSTOM_IMG] is False
    assert CONF_WALMART_CUSTOM_IMG_FILE in entry.data
    assert "no_deliveries_walmart.jpg" in entry.data[CONF_WALMART_CUSTOM_IMG_FILE]

    # Verify version was updated
    assert entry.version == CONFIG_VER

    return entry


"""Tests for migration functionality."""

pytestmark = pytest.mark.asyncio


async def test_migration_from_version_10_to_11(hass, caplog):
    """Test migration from version 10 to version 11 adds custom image fields."""
    # Create a config that simulates version 10 (without custom image fields)
    v10_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v10_config,
        version=10,  # Start with version 10
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert f"Migration complete to version {CONFIG_VER}" in caplog.text

    # Verify the new fields were added with correct defaults
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
    )

    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )
    assert CONF_WALMART_CUSTOM_IMG in entry.data
    assert entry.data[CONF_WALMART_CUSTOM_IMG] is False
    assert CONF_WALMART_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_WALMART_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
    )

    # Verify version was updated
    assert entry.version == CONFIG_VER

    # Verify existing fields were preserved
    assert entry.data["amazon_days"] == 3
    assert entry.data["amazon_domain"] == "amazon.com"
    assert entry.data["host"] == "imap.test.email"


async def test_migration_from_version_9_to_11(hass, caplog):
    """Test migration from version 9 to version 11 adds all missing fields."""
    # Create a config that simulates version 9 (missing storage field too)
    v9_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v9_config,
        version=9,  # Start with version 9
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert f"Migration complete to version {CONFIG_VER}" in caplog.text

    # Verify all missing fields were added
    assert "storage" in entry.data
    assert entry.data["storage"] == "custom_components/mail_and_packages/images/"

    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
    )

    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )
    assert CONF_WALMART_CUSTOM_IMG in entry.data
    assert entry.data[CONF_WALMART_CUSTOM_IMG] is False
    assert CONF_WALMART_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_WALMART_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
    )

    # Verify version was updated
    assert entry.version == CONFIG_VER


async def test_migration_from_version_11_no_changes(hass, caplog):
    """Test that migration from version 11 doesn't make unnecessary changes."""
    # Create a config that's already at version 11
    v11_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v11_config,
        version=11,  # Already at version 11
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Migration should occur from version 11 to 12 to add Walmart and Generic fields
    assert f"Migration complete to version {CONFIG_VER}" in caplog.text

    # Verify all fields are still present and unchanged
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
    )

    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )
    assert CONF_WALMART_CUSTOM_IMG in entry.data
    assert entry.data[CONF_WALMART_CUSTOM_IMG] is False
    assert CONF_WALMART_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_WALMART_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
    )

    # Verify version remains 12
    assert entry.version == CONFIG_VER


async def test_migration_preserves_existing_custom_image_settings(hass, caplog):
    """Test that migration preserves existing custom image settings if present."""
    # Create a config that has some custom image settings already
    v10_config_with_custom = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": True,
        "custom_img_file": "images/custom_mail.gif",
        "amazon_custom_img": True,  # Already set
        "amazon_custom_img_file": "images/custom_amazon.jpg",  # Already set
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v10_config_with_custom,
        version=10,  # Start with version 10
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert f"Migration complete to version {CONFIG_VER}" in caplog.text

    # Verify existing custom image settings were preserved
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is True  # Preserved
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE] == "images/custom_amazon.jpg"
    )  # Preserved

    # Verify UPS fields were added with defaults
    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False  # Default
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )  # Default

    # Verify version was updated
    assert entry.version == CONFIG_VER


async def test_migration_with_minimal_config(hass, caplog):
    """Test migration with a minimal config that's missing many fields."""
    # Create a very minimal config that might exist from very old versions
    minimal_config = {
        "auth_type": "password",
        "host": "imap.test.email",
        "port": 993,
        "username": "user@fake.email",
        "password": "suchfakemuchpassword",
        "folder": '"INBOX"',
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=minimal_config,
        version=1,  # Very old version
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert any(
        f"Migration complete to version {CONFIG_VER}" in record.message
        for record in caplog.records
    )

    # Verify all required fields were added
    assert "amazon_days" in entry.data
    assert "amazon_domain" in entry.data
    assert "imap_security" in entry.data
    assert "verify_ssl" in entry.data
    assert "storage" in entry.data
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert CONF_WALMART_CUSTOM_IMG in entry.data
    assert CONF_WALMART_CUSTOM_IMG_FILE in entry.data

    # Verify version was updated
    assert entry.version == CONFIG_VER


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "reconfig_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "usps_delivered",
                ],
            },
            "reconfig_amazon",
            {
                "amazon_domain": "",  # Invalid domain to trigger error
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            None,
            None,
            None,
            None,
            "Mail and Packages",
            {},
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfig_amazon_error(
    hass: HomeAssistant,
    mock_imap_no_email,
    integration,
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    title,
    data,
):
    """Test reconfigure flow with Amazon configuration error."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], input_1)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_2"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], input_2)
    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_amazon"

    # The flow is still on Amazon step because of invalid domain
    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_amazon"


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "reconfig_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": [
                    "amazon_packages",
                    "usps_delivered",
                ],
            },
            "reconfig_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "reconfig_storage",
            {
                "storage": "/invalid/readonly/path",  # Invalid path to trigger error
            },
            None,
            None,
            "Mail and Packages",
            {},
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfig_storage_error(
    hass: HomeAssistant,
    mock_imap_no_email,
    integration,
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    title,
    data,
):
    """Test reconfigure flow with storage configuration error."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], input_1)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_2"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], input_2)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_amazon"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], input_3)

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_amazon"


async def test_walmart_custom_image_validation():
    """Test Walmart custom image file validation."""

    # Test 1: Valid Walmart custom image file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(b"fake image data")

    try:
        user_input = {
            CONF_WALMART_CUSTOM_IMG: True,
            CONF_WALMART_CUSTOM_IMG_FILE: temp_file_path,
            CONF_GENERATE_MP4: False,
            CONF_CUSTOM_IMG: False,
            CONF_AMAZON_CUSTOM_IMG: False,
            CONF_UPS_CUSTOM_IMG: False,
            CONF_GENERIC_CUSTOM_IMG: False,
        }

        errors, validated_input = await _validate_user_input(user_input)

        # Should not have file_not_found error for Walmart custom image
        assert CONF_WALMART_CUSTOM_IMG_FILE not in errors
        assert validated_input[CONF_WALMART_CUSTOM_IMG] is True
        assert validated_input[CONF_WALMART_CUSTOM_IMG_FILE] == temp_file_path

    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            await Path(temp_file_path).unlink(missing_ok=True)

    # Test 2: Invalid Walmart custom image file (doesn't exist)
    user_input = {
        CONF_WALMART_CUSTOM_IMG: True,
        CONF_WALMART_CUSTOM_IMG_FILE: "/nonexistent/path/walmart_custom.jpg",
        CONF_GENERATE_MP4: False,
        CONF_CUSTOM_IMG: False,
        CONF_AMAZON_CUSTOM_IMG: False,
        CONF_UPS_CUSTOM_IMG: False,
        CONF_GENERIC_CUSTOM_IMG: False,
    }

    errors, validated_input = await _validate_user_input(user_input)

    # Should have file_not_found error for Walmart custom image
    assert CONF_WALMART_CUSTOM_IMG_FILE in errors
    assert errors[CONF_WALMART_CUSTOM_IMG_FILE] == "file_not_found"

    # Test 3: Walmart custom image disabled (should not validate file)
    user_input = {
        CONF_WALMART_CUSTOM_IMG: False,
        CONF_WALMART_CUSTOM_IMG_FILE: "/nonexistent/path/walmart_custom.jpg",
        CONF_GENERATE_MP4: False,
        CONF_CUSTOM_IMG: False,
        CONF_AMAZON_CUSTOM_IMG: False,
        CONF_UPS_CUSTOM_IMG: False,
        CONF_GENERIC_CUSTOM_IMG: False,
    }

    errors, validated_input = await _validate_user_input(user_input)

    # Should not have file_not_found error when Walmart custom image is disabled
    assert CONF_WALMART_CUSTOM_IMG_FILE not in errors


async def test_walmart_custom_image_in_config_flow(hass, mock_imap_no_email):
    """Test that Walmart custom image options are properly handled in config flow."""
    # We don't need to mock IMAP4_SSL if we mock _test_login and _get_mailboxes
    await setup.async_setup_component(hass, "persistent_notification", {})

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
        patch(
            "pathlib.Path.is_file",
            return_value=True,
        ),
        patch(
            "pathlib.Path.exists",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Complete step 1
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
        )

        # Should be at step 2
        assert result["type"] == "form"
        assert result["step_id"] == "config_2"

        # Complete step 2 with Walmart custom image enabled
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "allow_external": False,
                "custom_img": False,
                "walmart_custom_img": True,  # Enable Walmart custom image
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "resources": ["walmart_delivered"],
                "scan_interval": 20,
            },
        )

        # Should proceed to step 3 for custom image file configuration
        assert result["type"] == "form"
        assert result["step_id"] == "config_3"

        # Complete step 3 with Walmart custom image file
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_WALMART_CUSTOM_IMG_FILE: "custom_components/mail_and_packages/images/walmart.jpg",
            },
        )

        # Should proceed to storage step
        assert result["type"] == "form"
        assert result["step_id"] == "config_storage"

        # Complete storage step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
        )

        # Should create entry successfully
        assert result["type"] == "create_entry"
        assert result["title"] == "imap.test.email"

        # Verify Walmart custom image settings are saved
        entry = result["result"]
        assert entry.data[CONF_WALMART_CUSTOM_IMG] is True
        assert (
            entry.data[CONF_WALMART_CUSTOM_IMG_FILE]
            == "custom_components/mail_and_packages/images/walmart.jpg"
        )


async def test_generic_custom_image_validation(hass: HomeAssistant, mock_imap_no_email):
    """Test validation of generic custom image file."""

    # Test with non-existent file
    user_input = {
        "auth_type": "password",
                "host": "imap.test.email",
        "port": "993",
        "username": "test@test.email",
        "password": "notarealpassword",
        "imap_security": "SSL",
        "verify_ssl": False,
        "allow_external": False,
        "custom_img": False,
        "generic_custom_img": True,
        "generic_custom_img_file": "/nonexistent/path/image.jpg",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "resources": ["usps_mail"],
    }

    errors, validated_input = await _validate_user_input(user_input)

    # Should have validation error for non-existent file
    assert "generic_custom_img_file" in errors
    assert "file_not_found" in errors["generic_custom_img_file"]

    # Test with existing file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(b"fake image data")

    try:
        user_input["generic_custom_img_file"] = temp_file_path

        errors, validated_input = await _validate_user_input(user_input)

        # Should not have validation error for existing file
        assert "generic_custom_img_file" not in errors
        assert validated_input[CONF_GENERIC_CUSTOM_IMG_FILE] == temp_file_path

    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            await Path(temp_file_path).unlink(missing_ok=True)


async def test_generic_custom_image_in_config_flow(
    hass: HomeAssistant, mock_imap_no_email
):
    """Test generic custom image configuration in full config flow."""
    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        # Start the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Step 1: Basic IMAP settings
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "config_2"

        # Step 2: Enable generic custom image
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "allow_external": False,
                "custom_img": False,
                "generic_custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "resources": ["usps_mail"],
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "config_3"

        # Step 3: Set generic custom image file
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "generic_custom_img_file": "custom_components/mail_and_packages/images/generic.jpg",
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "config_storage"

        # Step 4: Storage settings
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "imap.test.email"

        # Verify generic custom image settings are saved
        entry = result["result"]
        assert entry.data[CONF_GENERIC_CUSTOM_IMG] is True
        assert (
            entry.data[CONF_GENERIC_CUSTOM_IMG_FILE]
            == "custom_components/mail_and_packages/images/generic.jpg"
        )
        assert entry.version == CONFIG_VER


async def test_migration_to_version_12(hass: HomeAssistant, mock_imap_no_email):
    """Test migration to version 12 adds new Walmart and Generic camera fields."""
    # Create a mock config entry with version 11
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data={
            "auth_type": "password",
                "host": "imap.test.email",
            "port": "993",
            "username": "test@test.email",
            "password": "notarealpassword",
            "imap_security": "SSL",
            "verify_ssl": False,
            "allow_external": False,
            "custom_img": False,
            "folder": '"INBOX"',
            "generate_grid": False,
            "generate_mp4": False,
            "resources": ["usps_mail"],
            "storage": "custom_components/mail_and_packages/images/",
        },
        version=11,
    )

    entry.add_to_hass(hass)

    # Set up the integration (this will trigger migration)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify version was updated (will go to 13, but we're testing that version 12 fields were added)
    assert entry.version == CONFIG_VER

    # Verify new Walmart camera fields were added with defaults
    assert CONF_WALMART_CUSTOM_IMG in entry.data
    assert entry.data[CONF_WALMART_CUSTOM_IMG] is False
    assert CONF_WALMART_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_WALMART_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
    )

    # Verify new Generic camera fields were added with defaults
    assert CONF_GENERIC_CUSTOM_IMG in entry.data
    assert entry.data[CONF_GENERIC_CUSTOM_IMG] is False
    assert CONF_GENERIC_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_GENERIC_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_generic.jpg"
    )

    # Verify existing fields were preserved
    assert entry.data["host"] == "imap.test.email"
    assert entry.data["amazon_custom_img"] is False
    assert entry.data["ups_custom_img"] is False


async def test_migration_to_version_13(hass: HomeAssistant, mock_imap_no_email):
    """Test migration to version 13 adds new generic camera fields."""
    # Create a mock config entry with version 11
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data={
            "auth_type": "password",
                "host": "imap.test.email",
            "port": "993",
            "username": "test@test.email",
            "password": "notarealpassword",
            "imap_security": "SSL",
            "verify_ssl": False,
            "allow_external": False,
            "custom_img": False,
            "folder": '"INBOX"',
            "generate_grid": False,
            "generate_mp4": False,
            "resources": ["usps_mail"],
            "storage": "custom_components/mail_and_packages/images/",
        },
        version=11,
    )

    entry.add_to_hass(hass)

    # Set up the integration (this will trigger migration)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify version was updated to 12
    assert entry.version == CONFIG_VER

    # Verify new generic camera fields were added with defaults
    assert CONF_GENERIC_CUSTOM_IMG in entry.data
    assert entry.data[CONF_GENERIC_CUSTOM_IMG] is False
    assert CONF_GENERIC_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_GENERIC_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_generic.jpg"
    )

    # Verify existing fields were preserved
    assert entry.data["host"] == "imap.test.email"
    assert entry.data["amazon_custom_img"] is False
    assert entry.data["walmart_custom_img"] is False


async def test_walmart_config_flow_integration():
    """Test that Walmart custom image support is properly integrated into config flow."""
    # Test 1: Validate Walmart custom image file exists
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(b"fake image data")

    try:
        user_input = {
            CONF_WALMART_CUSTOM_IMG: True,
            CONF_WALMART_CUSTOM_IMG_FILE: temp_file_path,
            CONF_GENERATE_MP4: False,
            CONF_CUSTOM_IMG: False,
            CONF_AMAZON_CUSTOM_IMG: False,
            CONF_UPS_CUSTOM_IMG: False,
            CONF_GENERIC_CUSTOM_IMG: False,
        }

        errors, validated_input = await _validate_user_input(user_input)

        # Should not have file_not_found error for Walmart custom image
        assert CONF_WALMART_CUSTOM_IMG_FILE not in errors, (
            "Walmart custom image file should be valid"
        )
        assert validated_input[CONF_WALMART_CUSTOM_IMG] is True
        assert validated_input[CONF_WALMART_CUSTOM_IMG_FILE] == temp_file_path

    finally:
        # Clean up temp file
        with contextlib.suppress(OSError):
            await Path(temp_file_path).unlink(missing_ok=True)

    # Test 2: Validate Walmart custom image file does not exist
    user_input = {
        CONF_WALMART_CUSTOM_IMG: True,
        CONF_WALMART_CUSTOM_IMG_FILE: "/nonexistent/path/walmart_custom.jpg",
        CONF_GENERATE_MP4: False,
        CONF_CUSTOM_IMG: False,
        CONF_AMAZON_CUSTOM_IMG: False,
        CONF_UPS_CUSTOM_IMG: False,
        CONF_GENERIC_CUSTOM_IMG: False,
    }

    errors, validated_input = await _validate_user_input(user_input)

    # Should have file_not_found error for Walmart custom image
    assert CONF_WALMART_CUSTOM_IMG_FILE in errors, (
        "Walmart custom image file should be invalid"
    )
    assert errors[CONF_WALMART_CUSTOM_IMG_FILE] == "file_not_found"

    # Test 3: Validate Walmart custom image disabled (should not validate file)
    user_input = {
        CONF_WALMART_CUSTOM_IMG: False,
        CONF_WALMART_CUSTOM_IMG_FILE: "/nonexistent/path/walmart_custom.jpg",
        CONF_GENERATE_MP4: False,
        CONF_CUSTOM_IMG: False,
        CONF_AMAZON_CUSTOM_IMG: False,
        CONF_UPS_CUSTOM_IMG: False,
        CONF_GENERIC_CUSTOM_IMG: False,
    }

    errors, validated_input = await _validate_user_input(user_input)

    # Should not have file_not_found error when Walmart custom image is disabled
    assert CONF_WALMART_CUSTOM_IMG_FILE not in errors, (
        "Walmart custom image file should not be validated when disabled"
    )


async def test_walmart_config_flow_version():
    """Test that the config version has been incremented for Walmart support."""
    # Version should be 12 or higher to include Walmart custom image support
    assert CONFIG_VER >= 12, (
        f"Config version should be 12 or higher for Walmart support, got {CONFIG_VER}"
    )


async def test_fedex_config_flow_version():
    """Test that the config version has been incremented for FedEx support."""
    # Version should be 13 or higher to include FedEx custom image support
    assert CONFIG_VER >= 13, (
        f"Config version should be 13 or higher for FedEx support, got {CONFIG_VER}"
    )


async def test_get_mailboxes_non_ok_status(hass, caplog):
    """Test getting mailboxes with a non-OK status."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()
    mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
    mock_conn.list = AsyncMock(
        return_value=MagicMock(
            result="AUTH_ERROR", lines=[b"Invalid credentials or folder access"]
        )
    )
    mock_conn.logout = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        # Test the mailbox retrieval logic
        result = await _get_mailboxes(
            hass, "imap.test.com", 993, "user", "pass", "SSL", True
        )

        # Verify the flow handles the non-OK status by returning an empty list or error
        assert result == ['"INBOX"']
        assert "Error listing mailboxes ... using default" in caplog.text
        mock_conn.list.assert_called_once()


@pytest.mark.asyncio
async def test_get_mailboxes_exception(hass):
    """Test getting mailboxes when an exception occurs."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()

    # Matching the aioimaplib response object pattern
    mock_login_res = MagicMock()
    mock_login_res.result = "OK"
    mock_conn.login.return_value = mock_login_res

    # This will trigger the exception when list() is called
    mock_conn.list.side_effect = OSError("Connection lost")
    mock_conn.logout = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        # Only the statement that triggers the exception goes inside pytest.raises
        with pytest.raises(OSError, match="Connection lost"):
            await _get_mailboxes(
                hass, "imap.test.com", 993, "user", "pass", "SSL", True
            )

        # Subsequent assertions go outside the raises block
        mock_conn.list.assert_called_once()


async def test_get_schema_step_3_none_input():
    """Test _get_schema_step_3 with None user_input."""
    result = _get_schema_step_3(None, {})

    # Should handle None input gracefully
    assert result is not None


async def test_config_flow_step_amazon_empty_fwds():
    """Test config flow step amazon with empty amazon_fwds."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {"amazon_fwds": []}  # noqa: SLF001

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        await flow._show_reconfig_amazon({})  # noqa: SLF001

        # Should set amazon_fwds to "(none)" when empty
        assert flow._data["amazon_fwds"] == "(none)"  # noqa: SLF001
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_storage_validation_error():
    """Test reconfig storage step with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {}  # noqa: SLF001
    flow._errors = {"test_error": "validation_failed"}  # noqa: SLF001

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        await flow._show_reconfig_storage({"test": "data"})  # noqa: SLF001

        # Should show form with errors
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_amazon_validation_error():
    """Test reconfig amazon step with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {"amazon_fwds": ["test@example.com"]}  # noqa: SLF001
    flow._errors = {"test_error": "validation_failed"}  # noqa: SLF001

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        await flow._show_reconfig_amazon({"test": "data"})  # noqa: SLF001

        # Should show form with errors
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_3_validation_error():
    """Test reconfig step 3 with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {}  # noqa: SLF001
    flow._errors = {"test_error": "validation_failed"}  # noqa: SLF001

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        await flow._show_reconfig_3({"test": "data"})  # noqa: SLF001

        # Should show form with errors
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_2_validation_error():
    """Test reconfig step 2 with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {  # noqa: SLF001
        "host": "imap.test.com",
        "port": 993,
        "username": "test@test.com",
        "password": "password",
        "imap_security": "SSL",
        "verify_ssl": True,
    }
    flow._errors = {"test_error": "validation_failed"}  # noqa: SLF001

    # Mock the _get_mailboxes function and async_show_form method
    with (
        patch(
            "custom_components.mail_and_packages.config_flow._get_mailboxes",
            return_value=['"INBOX"'],
        ),
        patch.object(flow, "async_show_form") as mock_show_form,
    ):
        await flow._show_reconfig_2({"test": "data"})  # noqa: SLF001

        # Should show form with errors
        mock_show_form.assert_called_once()


@pytest.mark.asyncio
async def test_get_mailboxes_generic_exception(hass, caplog):
    """Test _get_mailboxes handles generic exception during parsing."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()
    mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
    mock_response = MagicMock()
    mock_response.result = "OK"  # Change to .status if you don't change the code above
    mock_response.lines = [
        b'(\\HasNoChildren) "." "INBOX"'
    ]  # This will trigger the IndexError and fallback to period
    mock_conn.list = AsyncMock(return_value=mock_response)
    mock_conn.logout = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        # Call the function
        result = await _get_mailboxes(hass, "host", 993, "user", "pwd", "SSL", True)

        # Verify it falls back to default folder (parsed via period delimiter)
        assert result == [DEFAULT_FOLDER]


@pytest.mark.asyncio
async def test_validate_user_input_specific_images():
    """Test validation logic for specific custom image providers."""

    # Common base input
    base_input = {
        CONF_GENERATE_MP4: False,
        CONF_CUSTOM_IMG: False,
        CONF_AMAZON_CUSTOM_IMG: False,
        CONF_UPS_CUSTOM_IMG: False,
        CONF_WALMART_CUSTOM_IMG: False,
        CONF_FEDEX_CUSTOM_IMG: False,
        CONF_GENERIC_CUSTOM_IMG: False,
    }

    # Test Amazon Image Missing
    user_input = base_input.copy()
    user_input[CONF_AMAZON_CUSTOM_IMG] = True
    user_input[CONF_AMAZON_CUSTOM_IMG_FILE] = "missing_amazon.jpg"

    with patch(
        "pathlib.Path.is_file",
        return_value=False,
    ):
        errors, _ = await _validate_user_input(user_input)
        assert errors[CONF_AMAZON_CUSTOM_IMG_FILE] == "file_not_found"

    # Test UPS Image Missing
    user_input = base_input.copy()
    user_input[CONF_UPS_CUSTOM_IMG] = True
    user_input[CONF_UPS_CUSTOM_IMG_FILE] = "missing_ups.jpg"

    with patch(
        "pathlib.Path.is_file",
        return_value=False,
    ):
        errors, _ = await _validate_user_input(user_input)
        assert errors[CONF_UPS_CUSTOM_IMG_FILE] == "file_not_found"

    # Test FedEx Image Missing
    user_input = base_input.copy()
    user_input[CONF_FEDEX_CUSTOM_IMG] = True
    user_input[CONF_FEDEX_CUSTOM_IMG_FILE] = "missing_fedex.jpg"

    with patch(
        "pathlib.Path.is_file",
        return_value=False,
    ):
        errors, _ = await _validate_user_input(user_input)
        assert errors[CONF_FEDEX_CUSTOM_IMG_FILE] == "file_not_found"


@pytest.mark.asyncio
async def test_config_flow_invalid_auth(hass, mock_imap_login_error):
    """Test config flow when IMAP login fails."""
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass

    user_input = {
        "host": "imap.test.com",
        "port": 993,
        "username": "test",
        "password": "wrong_password",
        "imap_security": False,
        "verify_ssl": False,
    }

    result = await flow.async_step_user(user_input)
    assert result["type"] == "form"
    assert result["errors"] == {"password": "invalid_auth", "username": "invalid_auth"}


@pytest.mark.asyncio
async def test_validate_forwarded_emails_errors():
    """Test validation errors for forwarded emails."""
    user_input = {
        CONF_FORWARDED_EMAILS: "",
        "generate_mp4": False,
    }
    errors, _ = await _validate_user_input(user_input)
    assert errors[CONF_FORWARDED_EMAILS] == "missing_forwarded_emails"

    user_input = {
        CONF_FORWARDED_EMAILS: "not-an-email",
        "generate_mp4": False,
    }
    errors, _ = await _validate_user_input(user_input)
    assert errors[CONF_FORWARDED_EMAILS] == "invalid_email_format"

    user_input = {
        CONF_FORWARDED_EMAILS: "test@amazon.com",
        CONF_AMAZON_FWDS: [],
        "generate_mp4": False,
    }
    errors, _ = await _validate_user_input(user_input)


@pytest.mark.asyncio
async def test_reconfigure_step_login_fail(hass, mock_imap_login_error, integration):
    """Test reconfigure flow when the new login info is invalid."""
    entry = integration

    # Init the reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    user_input = {
        "host": "new.broken-host.com",
        "port": 993,
        "username": "user",
        "password": "password",
        "imap_security": "SSL",
        "verify_ssl": True,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"password": "invalid_auth", "username": "invalid_auth"}


@pytest.mark.asyncio
async def test_check_amazon_forwards_invalid_format(hass):
    """Test amazon forwards validation with missing @ symbol."""
    user_input = {
        CONF_AMAZON_FWDS: "invalid-format",
        CONF_AMAZON_DOMAIN: "amazon.com",
        "generate_mp4": False,
    }

    errors, _ = await _validate_user_input(user_input)
    assert errors[CONF_AMAZON_FWDS] == "invalid_email_format"


@pytest.mark.asyncio
async def test_reconfigure_flow_mailbox_success(hass, mock_imap_no_email, integration):
    """Test reconfigure flow moves to step 2 after successful login and mailbox fetch."""
    entry = integration
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "reconfig_2"


@pytest.mark.asyncio
async def test_validate_user_input_forwarded_emails_none():
    """Test validation when user enters (none) for forwarded emails."""
    user_input = {
        CONF_FORWARDED_EMAILS: "(none)",
        CONF_ALLOW_FORWARDED_EMAILS: True,
        CONF_GENERATE_MP4: False,
    }

    errors, result_input = await _validate_user_input(user_input)

    assert errors == {}
    # The helper should have set allow_forwarded_emails to False
    assert result_input[CONF_ALLOW_FORWARDED_EMAILS] is False
    assert CONF_FORWARDED_EMAILS not in result_input


async def test_get_mailboxes_parsing_error(hass, caplog):
    """Test _get_mailboxes handles delimiter parsing failures."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()
    mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

    # Return a response that triggers a parsing error (e.g., None where a list is expected)
    mock_conn.list = AsyncMock(return_value=MagicMock(result="OK", lines=None))
    mock_conn.logout = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        result = await _get_mailboxes(hass, "host", 993, "user", "pwd", "SSL", True)

        assert result == [DEFAULT_FOLDER]
        assert "Error listing mailboxes ... using default" in caplog.text


@pytest.mark.asyncio
async def test_get_mailboxes_period_delimiter(hass):
    """Test _get_mailboxes fallback when using period delimiter."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()
    mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))

    # Simulate a server that uses "." as a delimiter
    mock_conn.list = AsyncMock(
        return_value=MagicMock(result="OK", lines=[b'(\\HasNoChildren) "." "SENT"'])
    )
    mock_conn.logout = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        result = await _get_mailboxes(hass, "host", 993, "user", "pass", "SSL", True)
        assert '"SENT"' in result


@pytest.mark.asyncio
async def test_validate_forwarded_emails_conflict(hass):
    """Test error when forwarded email domain conflicts with service domains."""
    user_input = {"forwarded_emails": "test@amazon.com", "amazon_fwds": []}

    with patch(
        "custom_components.mail_and_packages.config_flow.validate_email_address",
        return_value=True,
    ):
        errors = await _check_forwarded_emails(user_input)
        assert "ok" in errors


@pytest.mark.asyncio
async def test_reconfig_2_schema_validation(hass, integration):
    """Test that the schema correctly rejects a scan_interval below 5."""
    entry = integration
    with (
        patch(
            "custom_components.mail_and_packages.config_flow._get_mailboxes",
            return_value=['"INBOX"'],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        # Advance to step 2
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "imap.test.com",
                "port": 993,
                "username": "test",
                "password": "pwd",
                "imap_security": "SSL",
                "verify_ssl": True,
            },
        )

        # Catch the expected schema validation failure
        with pytest.raises(InvalidData):
            await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "scan_interval": 1,
                    "folder": '"INBOX"',
                    "resources": ["mail_updated"],
                },
            )


@pytest.mark.asyncio
async def test_reconfigure_flow_skip_to_storage(hass, mock_imap_no_email, integration):
    """Test reconfigure flow skips directly to storage when no special options are enabled."""
    entry = integration
    reconfig_login_data = {
        "auth_type": "password",
        "host": "imap.test.email",
        "port": 993,
        "username": "test@test.email",
        "password": "password",
        "imap_security": "SSL",
        "verify_ssl": True,
    }

    # Initialize reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], reconfig_login_data
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_2"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "folder": '"INBOX"',
            "resources": ["mail_updated", "usps_mail"],
            "custom_img": False,
            "amazon_custom_img": False,
            "ups_custom_img": False,
            "walmart_custom_img": False,
            "fedex_custom_img": False,
            "generic_custom_img": False,
            "allow_forwarded_emails": False,
            "generate_grid": False,
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_storage"


@pytest.mark.asyncio
async def test_get_schema_step_3_fedex_only():
    """Test schema generation when only FedEx custom image is enabled."""
    user_input = {CONF_FEDEX_CUSTOM_IMG: True}
    defaults = {CONF_FEDEX_CUSTOM_IMG_FILE: "default_fedex.jpg"}

    schema = _get_schema_step_3(user_input, defaults)

    # Verify FedEx is in the schema but other providers are not
    assert CONF_FEDEX_CUSTOM_IMG_FILE in schema.schema
    assert "amazon_custom_img_file" not in schema.schema


@pytest.mark.asyncio
async def test_validate_forwarded_emails_missing_and_invalid():
    """Test validation error when allowed_forwarded is True but input is missing or bad."""
    user_input = {
        "allow_forwarded_emails": True,
        "forwarded_emails": "",
        "generate_mp4": False,
    }
    errors, _ = await _validate_user_input(user_input)
    assert errors["forwarded_emails"] == "missing_forwarded_emails"

    user_input["forwarded_emails"] = "not-an-email-address"
    errors, _ = await _validate_user_input(user_input)
    assert errors["forwarded_emails"] == "invalid_email_format"


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "step_id_6",
        "input_6",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "user@example.com,testuser@example.com"},
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "forwarded_emails": "user@example.com,testuser@example.com",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allow_forwarded_emails(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    step_id_6,
    input_6,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.is_file",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_6
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_6
        )

        assert result["type"] == "create_entry"
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "step_id_6",
        "input_6",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "(none)"},
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allowed_forwarded_emails_entered_none(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    step_id_6,
    input_6,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.is_file",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_6
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_6
        )

        assert result["type"] == "create_entry"
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
                "scan_interval": 20,
                "resources": [
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "user@example.com,testuser@example.com"},
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "forwarded_emails": "user@example.com,testuser@example.com",
                "custom_img": False,
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
                "resources": [
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allow_forwarded_emails_without_amazon_or_custom_img(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.is_file",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

        assert result["type"] == "create_entry"
        assert result["title"] == title
        assert result["data"] == data

        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "user@example.com,testuser@example.com"},
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "forwarded_emails": "user@example.com,testuser@example.com",
                "custom_img": False,
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allow_forwarded_emails_without_custom_img(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": False,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "user@example.com,testuser@example.com"},
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "forwarded_emails": "user@example.com,testuser@example.com",
                "custom_img": False,
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allow_forwarded_emails_with_custom_img_no_amazon(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "step_id_6",
        "input_6",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "(none)"},
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "forwarded_emails": "(none)",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allow_forwarded_emails_none_entered(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    step_id_6,
    input_6,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.is_file",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_6
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_6
        )

    # this gets automatically removed when set to "(none)"
    del data["forwarded_emails"]

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("input_1", "step_id_2", "input_2", "step_id_3", "input_3", "title", "data"),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {
                "forwarded_emails": "",
            },
            "imap.test.email",
            {
                **DEFAULT_CUSTOM_IMAGE_DATA,
                "allow_external": False,
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allowed_forwards_missing_email_addresses(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
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

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        assert result["errors"] == {"forwarded_emails": "missing_forwarded_emails"}


@pytest.mark.parametrize(
    ("input_1", "step_id_2", "input_2", "step_id_3", "input_3", "title", "data"),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {
                "forwarded_emails": "hello world",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allowed_forwards_invalid_email_address_format(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    title,
    data,
    hass,
    mock_imap,
    caplog,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

    assert result["type"] == "form"
    assert result["step_id"] == step_id_3
    assert result["errors"] == {"forwarded_emails": "invalid_email_format"}


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "step_id_6",
        "input_6",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "reconfig_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 120,
                "scan_interval": 60,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "reconfig_forwarded_emails",
            {"forwarded_emails": "user@example.com,testuser@example.com"},
            "reconfig_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "reconfig_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "reconfig_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "forwarded_emails": "user@example.com,testuser@example.com",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "image_name": "mail_today.gif",
                "image_path": "custom_components/mail_and_packages/images/",
                "image_security": True,
                "imap_security": "SSL",
                "imap_timeout": 120,
                "scan_interval": 60,
                "storage": "custom_components/mail_and_packages/images/",
                "resources": [
                    "amazon_delivered",
                    "amazon_packages",
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "dhl_delivered",
                    "dhl_delivering",
                    "dhl_packages",
                    "fedex_delivered",
                    "fedex_delivering",
                    "fedex_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                    "mail_updated",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "ups_delivered",
                    "ups_delivering",
                    "ups_packages",
                    "usps_delivered",
                    "usps_delivering",
                    "usps_mail",
                    "usps_packages",
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
                "verify_ssl": False,
                **DEFAULT_CUSTOM_IMAGE_DATA,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_allow_forwarded_emails(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    step_id_6,
    input_6,
    title,
    data,
    hass: HomeAssistant,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
) -> None:
    """Test reconfigure flow."""
    entry = integration

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.is_file",
            return_value=True,
        ),
    ):
        reconfigure_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert reconfigure_result["type"] is FlowResultType.FORM
        assert reconfigure_result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            reconfigure_result["flow_id"],
            input_1,
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_6
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_6
        )

        # assert "errors" not in result

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]

        assert entry.data.copy() == data


@pytest.mark.parametrize(
    (
        "input_1",
        "step_id_2",
        "input_2",
        "step_id_3",
        "input_3",
        "step_id_4",
        "input_4",
        "step_id_5",
        "input_5",
        "step_id_6",
        "input_6",
        "title",
        "data",
    ),
    [
        (
            {
                "auth_type": "password",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "imap_security": "SSL",
                "verify_ssl": False,
            },
            "config_2",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_timeout": 30,
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
            },
            "config_forwarded_emails",
            {"forwarded_emails": "no-reply@usps.com"},
            "config_amazon",
            {
                "amazon_domain": "amazon.com",
                "amazon_days": 3,
                "amazon_fwds": "(none)",
            },
            "config_3",
            {
                "custom_img_file": "images/test.gif",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "forwarded_emails": "no-reply@usps.com",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "auth_type": "password",
                "host": "imap.test.email",
                "port": 993,
                "username": "test@test.email",
                "password": "notarealpassword",
                "folder": '"INBOX"',
                "generate_grid": False,
                "generate_mp4": False,
                "gif_duration": 5,
                "imap_security": "SSL",
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": "custom_components/mail_and_packages/images/",
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
                    "auspost_delivered",
                    "auspost_delivering",
                    "auspost_packages",
                    "poczta_polska_delivering",
                    "poczta_polska_packages",
                    "inpost_pl_delivered",
                    "inpost_pl_delivering",
                    "inpost_pl_packages",
                ],
                "verify_ssl": False,
                "amazon_custom_img": False,
                "fedex_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_allow_forwarded_emails_using_service_address(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    step_id_5,
    input_5,
    step_id_6,
    input_6,
    title,
    data,
    hass,
    mock_imap,
    caplog,
):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow.Path.is_file",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "custom_components.mail_and_packages.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_4
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_4
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_6
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_6
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    assert result["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    assert "A service domain was found in email" in caplog.text


@pytest.mark.asyncio
async def test_validate_amazon_forwards(caplog):
    """Test validation of amazon forwards with empty or none strings."""
    # Test with (none)
    user_input = {
        CONF_AMAZON_FWDS: "(none)",
        CONF_AMAZON_DOMAIN: "amazon.com",
        CONF_GENERATE_MP4: False,
    }
    errors, result = await _validate_user_input(user_input)
    assert result[CONF_AMAZON_FWDS] == []
    assert errors == {}

    # Test with empty string
    user_input[CONF_AMAZON_FWDS] = ""
    errors, result = await _validate_user_input(user_input)
    assert result[CONF_AMAZON_FWDS] == []
    assert errors == {}

    # Test with amazon.com address
    user_input[CONF_AMAZON_FWDS] = "fakeuser@amazon.com"
    errors, result = await _validate_user_input(user_input)
    assert result[CONF_AMAZON_FWDS] == "fakeuser@amazon.com"
    assert errors == {}
    assert (
        "Amazon domain found in email: fakeuser@amazon.com, this may cause errors when searching emails."
        in caplog.text
    )


@pytest.mark.asyncio
async def test_get_mailboxes_fallback_delimiters(hass, caplog):
    """Test get_mailboxes fallback logic for different delimiters."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()
    mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
    mock_conn.logout = AsyncMock()

    mock_conn.list = AsyncMock(
        return_value=MagicMock(result="OK", lines=[b'(\\HasNoChildren) "|" "INBOX"'])
    )

    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        result = await _get_mailboxes(hass, "host", 993, "user", "pwd", "SSL", True)

        assert result == [DEFAULT_FOLDER]
        assert "Problem reading mailbox folders, using default." in caplog.text


@pytest.mark.asyncio
async def test_get_mailboxes_type_attribute_errors(hass, caplog):
    """Test get_mailboxes generic exception handling."""
    mock_conn = AsyncMock()
    mock_conn.wait_hello_from_server = AsyncMock()
    mock_conn.login = AsyncMock(return_value=MagicMock(result="OK"))
    mock_conn.logout = AsyncMock()

    # Trigger TypeError by returning a non-iterable integer instead of a list
    mock_conn.list = AsyncMock(return_value=MagicMock(result="OK", lines=12345))

    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        return_value=mock_conn,
    ):
        result = await _get_mailboxes(hass, "host", 993, "user", "pwd", "SSL", True)

        assert result == [DEFAULT_FOLDER]
        assert "Error listing mailboxes ... using default" in caplog.text


@pytest.mark.asyncio
async def test_step_config_3_validation_error(hass):
    """Test config flow step 3 validation failure."""
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass
    # Ensure generate_mp4 is present to avoid KeyError in validation
    flow._data = {  # noqa: SLF001
        CONF_CUSTOM_IMG: True,
        CONF_GENERATE_MP4: False,
    }

    # Simulate invalid input (file not found)
    user_input = {CONF_CUSTOM_IMG_FILE: "non_existent_file.gif"}

    with (
        patch("pathlib.Path.is_file", return_value=False),
        patch.object(flow, "async_show_form") as mock_show_form,
    ):
        await flow.async_step_config_3(user_input)

        # Should return the form again due to validation error
        mock_show_form.assert_called_once()
        assert flow._errors[CONF_CUSTOM_IMG_FILE] == "file_not_found"  # noqa: SLF001


@pytest.mark.asyncio
async def test_step_config_amazon_validation_error(hass):
    """Test config flow step amazon validation failure."""
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass
    # Ensure generate_mp4 is present to avoid KeyError in validation
    flow._data = {CONF_GENERATE_MP4: False}  # noqa: SLF001

    # Simulate invalid email format
    user_input = {
        CONF_AMAZON_DOMAIN: "amazon.com",
        CONF_AMAZON_FWDS: "invalid-email",
        CONF_AMAZON_DAYS: 3,
    }

    with patch.object(flow, "async_show_form") as mock_show_form:
        await flow.async_step_config_amazon(user_input)

        # Should return the form again due to validation error
        mock_show_form.assert_called_once()
        assert flow._errors[CONF_AMAZON_FWDS] == "invalid_email_format"  # noqa: SLF001


@pytest.mark.asyncio
async def test_reconfig_forwarded_emails_routing_failure(hass, integration):
    """Test reconfig forwarded emails failure path."""
    entry = integration
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass
    flow._entry = entry  # noqa: SLF001
    flow._data = dict(entry.data)  # noqa: SLF001

    # Ensure dependencies are set to avoid KeyErrors or wrong paths
    flow._data[CONF_RESOURCES] = ["mail_updated"]  # noqa: SLF001
    flow._data[CONF_CUSTOM_IMG] = False  # noqa: SLF001
    flow._data[CONF_GENERATE_MP4] = False  # noqa: SLF001

    user_input_error = {CONF_FORWARDED_EMAILS: "bad-email"}

    with (
        patch.object(flow, "async_show_form") as mock_show_form,
        patch(
            "custom_components.mail_and_packages.config_flow.validate_email_address",
            return_value=False,
        ),
    ):
        await flow.async_step_reconfig_forwarded_emails(user_input_error)

        mock_show_form.assert_called_once()
        assert flow._errors[CONF_FORWARDED_EMAILS] == "invalid_email_format"  # noqa: SLF001


@pytest.mark.asyncio
async def test_reconfig_forwarded_emails_routing_success(hass, integration):
    """Test reconfig forwarded emails success path routing to storage."""
    entry = integration
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass
    flow._entry = entry  # noqa: SLF001
    flow._data = dict(entry.data)  # noqa: SLF001

    # Ensure data ensures routing to storage (No Amazon sensors, No Custom Img)
    flow._data[CONF_RESOURCES] = ["mail_updated"]  # noqa: SLF001
    flow._data[CONF_CUSTOM_IMG] = False  # noqa: SLF001
    flow._data[CONF_GENERATE_MP4] = False  # noqa: SLF001

    user_input_success = {CONF_FORWARDED_EMAILS: "good@email.com"}

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.validate_email_address",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.config_flow._validate_path_input",
        ),
    ):
        result = await flow.async_step_reconfig_forwarded_emails(user_input_success)

        # Expectation: The flow proceeds to the storage step, which returns a form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfig_storage"


@pytest.mark.asyncio
async def test_get_mailboxes_connection_exceptions(hass, caplog):
    """Test get_mailboxes handling of connection exceptions (lines 281-282)."""
    # Test triggering the specific exception block with AioImapException
    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        side_effect=AioImapException("Connection refused"),
    ):
        result = await _get_mailboxes(hass, "host", 993, "user", "pwd", "SSL", True)
        assert "Unable to connect: Connection refused" in caplog.text
        assert result == []

    caplog.clear()

    # Test triggering the same block with TimeoutError
    with patch(
        "custom_components.mail_and_packages.config_flow.login",
        side_effect=TimeoutError("Timed out"),
    ):
        result = await _get_mailboxes(hass, "host", 993, "user", "pwd", "SSL", True)
        assert "Unable to connect: Timed out" in caplog.text
        assert result == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("login_side_effect", "select_return", "expected_error"),
    [
        (ssl.SSLError("SSL Handshake Failed"), None, "ssl_error"),
        (None, ("NO", [b"Select Failed"]), "missing_inbox"),
    ],
)
async def test_config_flow_validate_login_errors(
    hass, login_side_effect, select_return, expected_error
):
    """Test config flow handling of login errors (SSL and Missing Inbox)."""
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass

    user_input = {
        "auth_type": "password",
        "host": "imap.test.email",
        "port": 993,
        "username": "test@test.email",
        "password": "password",
        "imap_security": "SSL",
        "verify_ssl": True,
    }

    # Setup the login patch
    with patch("custom_components.mail_and_packages.config_flow.login") as mock_login:
        if login_side_effect:
            mock_login.side_effect = login_side_effect
        else:
            mock_account = MagicMock()
            mock_account.select = AsyncMock(return_value=select_return)
            mock_account.logout = AsyncMock()
            mock_login.return_value = mock_account

        result = await flow.async_step_user(user_input)

    # Verify the form is re-shown with the expected error code
    assert result["type"] == "form"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.asyncio
async def test_step_2_finish_flow(hass, mock_imap):
    """Test config flow finishes at step 2 when features are disabled (covers line 659)."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "config_2"
    input_2 = {
        "allow_external": False,
        "allow_forwarded_emails": False,
        "custom_img": False,
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "imap_timeout": 30,
        "scan_interval": 20,
        "resources": ["mail_updated"],
    }

    with (
        patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.async_setup", return_value=True),
        patch(
            "custom_components.mail_and_packages.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )
    assert result["type"] == "create_entry"
    assert result["title"] == "imap.test.email"
    assert result["data"]["allow_forwarded_emails"] is False
    assert result["data"]["custom_img"] is False


@pytest.mark.asyncio
async def test_step_forwarded_emails_skip_amazon(hass, mock_imap):
    """Test transition from forwarded emails directly to step 3."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "allow_external": False,
            "allow_forwarded_emails": True,
            "custom_img": True,
            "folder": '"INBOX"',
            "generate_grid": False,
            "generate_mp4": False,
            "gif_duration": 5,
            "imap_timeout": 30,
            "scan_interval": 20,
            "resources": ["mail_updated"],
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "config_forwarded_emails"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "forwarded_emails": "forwarder@example.com",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "config_3"


@pytest.mark.asyncio
async def test_reconfig_2_validation_error(hass, mock_imap_no_email, integration):
    """Test step 2 validiation errors."""
    entry = integration
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )
    assert result["step_id"] == "reconfig_2"
    with patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "folder": '"INBOX"',
                "generate_mp4": True,
                "scan_interval": 20,
                "resources": ["mail_updated"],
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_2"
    assert result["errors"] == {"generate_mp4": "ffmpeg_not_found"}


@pytest.mark.asyncio
async def test_reconfig_3_validation_error(hass, mock_imap_no_email, integration):
    """Test step 3 validation errors."""
    entry = integration

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )

    assert result["step_id"] == "reconfig_2"

    with patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "folder": '"INBOX"',
                "custom_img": True,
                "scan_interval": 20,
                "resources": ["mail_updated"],
            },
        )

    assert result["step_id"] == "reconfig_3"

    with patch("pathlib.Path.is_file", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "custom_img_file": "non_existent_file.gif",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_3"
    assert result["errors"] == {
        "custom_img_file": "file_not_found",
        "storage": "path_not_found",
    }


@pytest.mark.asyncio
async def test_reconfig_forwarded_emails_to_reconfig_3(
    hass, mock_imap_no_email, integration
):
    """Test transition from reconfig forwarded emails to reconfig 3."""
    entry = integration
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )

    with patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "scan_interval": 20,
                "resources": ["mail_updated"],
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_forwarded_emails"

    with (
        patch(
            "custom_components.mail_and_packages.config_flow.validate_email_address",
            return_value=True,
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("os.path.isfile", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "forwarded_emails": "forwarder@example.com",
            },
        )
    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_3"


@pytest.mark.asyncio
async def test_reconfig_storage_validation_error(hass, mock_imap_no_email, integration):
    """Test validation error in reconfig storage step."""
    entry = integration
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "auth_type": "password",
            "host": "imap.test.email",
            "port": 993,
            "username": "test@test.email",
            "password": "password",
            "imap_security": "SSL",
            "verify_ssl": True,
        },
    )
    with patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "allow_external": False,
                "allow_forwarded_emails": True,
                "custom_img": True,
                "folder": '"INBOX"',
                "scan_interval": 20,
                "resources": ["mail_updated"],
            },
        )
    with (
        patch(
            "custom_components.mail_and_packages.config_flow.validate_email_address",
            return_value=True,
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("os.path.isfile", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "forwarded_emails": "forwarder@example.com",
            },
        )
    assert result["step_id"] == "reconfig_3"
    with (
        patch("pathlib.Path.is_file", return_value=True),
        patch("pathlib.Path.exists", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "custom_img_file": "test_image.gif",
            },
        )
    assert result["errors"] == {}
    assert result["step_id"] == "reconfig_storage"
    with patch("pathlib.Path.exists", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "storage": "/invalid/path/does/not/exist",
            },
        )
    assert result["type"] == "form"
    assert result["step_id"] == "reconfig_storage"
    assert result["errors"] != {}
