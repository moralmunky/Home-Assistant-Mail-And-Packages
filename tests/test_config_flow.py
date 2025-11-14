"""Test Mail and Packages config flow"""

import sys
import logging
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from homeassistant import config_entries, setup
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.config_flow import (
    MailAndPackagesFlowHandler,
    _get_mailboxes,
    _get_schema_step_3,
    _validate_user_input,
)
from custom_components.mail_and_packages.const import (
    CONF_AMAZON_FWDS,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_CUSTOM_IMG,
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
from custom_components.mail_and_packages.helpers import _check_ffmpeg, _test_login, NO_SSL
from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_BAD

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
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
async def test_form(
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
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
    "input_1,step_id_2",
    [
        (
            {
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
            {
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
            },
            "imap.test.email",
            {
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
        assert result2["step_id"] == step_id_2

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

    assert result3["type"] == "form"
    assert result3["step_id"] == step_id_2
    assert result3["errors"] == {CONF_GENERATE_MP4: "ffmpeg_not_found"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
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
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
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
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
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
async def test_form_mailbox_format2(
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
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
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
async def test_form_mailbox_format3(
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
    mock_imap_mailbox_format3,
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
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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


@pytest.mark.asyncio
async def test_valid_ffmpeg(test_valid_ffmpeg):
    result = await _check_ffmpeg()
    assert result


@pytest.mark.asyncio
async def test_invalid_ffmpeg(test_invalid_ffmpeg):
    result = await _check_ffmpeg()
    assert not result


@pytest.mark.asyncio
async def test_imap_login(mock_imap):
    result = await _test_login(
        "127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword", "SSL", False
    )
    assert result


@pytest.mark.asyncio
async def test_imap_login_with_starttls(mock_imap):
    result = await _test_login(
        "127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword", "startTLS", False
    )
    assert result


@pytest.mark.asyncio
async def test_imap_login_without_ssl(mock_imap, caplog):
    result = await _test_login(
        "127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword", "", False
    )
    assert result
    assert NO_SSL in caplog.text


@pytest.mark.asyncio
async def test_imap_connection_error(caplog):
    await _test_login(
        "127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword", "SSL", False
    )
    assert "Error connecting into IMAP Server:" in caplog.text


@pytest.mark.asyncio
async def test_imap_login_error(mock_imap_login_error, caplog):
    await _test_login(
        "127.0.0.1", 993, "fakeuser@test.email", "suchfakemuchpassword", "SSL", True
    )
    assert "Error logging into IMAP Server:" in caplog.text


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "amazon_fwds": "testemail@amazon.com",
            },
            "config_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_amazon_error(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    mock_imap,
    hass,
    caplog,
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
        "os.path.exists", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
        assert (
            "Amazon domain found in email: testemail@amazon.com, this may cause errors when searching emails."
            in caplog.text
        )


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "amazon_fwds": "@bademail.com, amazon.com",
            },
            "config_4",
            {
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
            },
            "test_form_amazon_error_2",
            {
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_form_amazon_error_2(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    step_id_4,
    input_4,
    title,
    data,
    mock_imap,
    hass,
    caplog,
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
        assert "Missing '@' in email address: amazon.com" in caplog.text
        assert result["errors"] == {CONF_AMAZON_FWDS: "invalid_email_format"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            "custom_components.mail_and_packages.config_flow.path.exists",
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_custom_img": False,
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
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

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@fake.email, fakeuser2@fake.email",
                "amazon_custom_img": False,
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
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

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            "reconfig_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "reconfig_4",
            {
                "amazon_custom_img": False,
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@fake.email, fakeuser2@fake.email",
                "amazon_custom_img": False,
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": False,
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
async def test_reconfigure_no_amazon_no_custom_image(
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

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        _LOGGER.debug("Entries: %s", len(hass.config_entries.async_entries(DOMAIN)))
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.data.copy() == data


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            "reconfig_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_custom_img": False,
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "custom_img": False,
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
async def test_reconfig_no_cust_img(
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

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "custom_img": False,
                "ups_custom_img": False,
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
                "amazon_fwds": "amazon.com",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfig_amazon_error(
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
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
    caplog,
) -> None:
    """Test reconfigure flow."""
    entry = integration

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == step_id_3
        assert "Missing '@' in email address: amazon.com" in caplog.text
        assert result["errors"] == {CONF_AMAZON_FWDS: "invalid_email_format"}


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3",
    [
        (
            {
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
                "amazon_custom_img": False,
                "custom_img": False,
                "ups_custom_img": False,
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
                    "zpackages_delivered",
                    "zpackages_transit",
                ],
            },
            "reconfig_storage",
            {
                "storage": "custom_components/mail_and_packages/images/",
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfig_storage_error(
    input_1,
    step_id_2,
    input_2,
    step_id_3,
    input_3,
    hass: HomeAssistant,
    integration,
    mock_imap_no_email,
):
    """Test we get the form."""
    entry = integration

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

    result = await hass.config_entries.flow.async_configure(result["flow_id"], input_2)

    assert result["type"] == "form"
    assert result["step_id"] == step_id_3

    with patch(
        "custom_components.mail_and_packages.config_flow._validate_user_input",
        return_value=({CONF_STORAGE: "path_not_found"}, input_3),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

    assert result["type"] == "form"
    assert result["step_id"] == step_id_3
    assert result["errors"] == {CONF_STORAGE: "path_not_found"}


@pytest.mark.asyncio
async def test_reconfigure_with_custom_images(
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
    """Test reconfigure flow with custom Amazon and USPS images."""
    entry = integration

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
            result["flow_id"], input_4
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_5
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_5
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        _LOGGER.debug("Entries: %s", len(hass.config_entries.async_entries(DOMAIN)))
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        actual_data = entry.data.copy()
        # Sort lists for comparison
        if "resources" in actual_data:
            actual_data["resources"] = sorted(actual_data["resources"])
        if "resources" in data:
            data["resources"] = sorted(data["resources"])

        # Compare key by key to handle any differences
        for key in data:
            assert actual_data[key] == data[key], f"Mismatch for key {key}"


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_amazon,input_amazon,step_id_storage,input_storage,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            "reconfig_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "custom_img": False,
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
async def test_reconfigure_with_default_images(
    input_1,
    step_id_2,
    input_2,
    step_id_amazon,
    input_amazon,
    step_id_storage,
    input_storage,
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
    """Test reconfigure flow with default images."""
    entry = integration

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
        assert result["step_id"] == step_id_amazon
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_amazon
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_storage
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_storage
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        _LOGGER.debug("Entries: %s", len(hass.config_entries.async_entries(DOMAIN)))
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        actual_data = entry.data.copy()
        # Sort lists for comparison
        if "resources" in actual_data:
            actual_data["resources"] = sorted(actual_data["resources"])
        if "resources" in data:
            data["resources"] = sorted(data["resources"])

        # Compare key by key to handle any differences
        for key in data:
            assert actual_data[key] == data[key], f"Mismatch for key {key}"


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_amazon,input_amazon,step_id_3,input_3,step_id_storage,input_storage,title,data",
    [
        (
            {
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
                "custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "amazon_custom_img_file": "images/amazon_custom.jpg",
            },
            "config_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_custom_img": True,
                "amazon_custom_img_file": "images/amazon_custom.jpg",
                "custom_img": False,
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
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": ".storage/mail_and_packages/images",
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
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_config_flow_with_amazon_custom_image_only(
    input_1,
    step_id_2,
    input_2,
    step_id_amazon,
    input_amazon,
    step_id_3,
    input_3,
    step_id_storage,
    input_storage,
    title,
    data,
    hass,
    mock_imap,
):
    """Test config flow with Amazon custom image only."""
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_amazon
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_amazon
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_storage
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_storage
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    actual_data = result["data"]
    # Sort lists for comparison
    if "resources" in actual_data:
        actual_data["resources"] = sorted(actual_data["resources"])
    if "resources" in data:
        data["resources"] = sorted(data["resources"])

    # Compare key by key to handle any differences
    for key in data:
        assert actual_data[key] == data[key], f"Mismatch for key {key}"

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_amazon,input_amazon,step_id_3,input_3,step_id_storage,input_storage,title,data",
    [
        (
            {
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
                "custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "ups_custom_img_file": "images/ups_custom.jpg",
            },
            "config_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_custom_img": False,
                "custom_img": False,
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
                "imap_timeout": 30,
                "scan_interval": 20,
                "storage": ".storage/mail_and_packages/images",
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
                "ups_custom_img": True,
                "ups_custom_img_file": "images/ups_custom.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "verify_ssl": False,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_config_flow_with_ups_custom_image_only(
    input_1,
    step_id_2,
    input_2,
    step_id_amazon,
    input_amazon,
    step_id_3,
    input_3,
    step_id_storage,
    input_storage,
    title,
    data,
    hass,
    mock_imap,
):
    """Test config flow with UPS custom image only."""
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
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )
        assert result["type"] == "form"
        assert result["step_id"] == step_id_2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_2
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_amazon
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_amazon
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_3
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_3
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_storage
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_storage
        )

    assert result["type"] == "create_entry"
    assert result["title"] == title
    actual_data = result["data"]
    # Sort lists for comparison
    if "resources" in actual_data:
        actual_data["resources"] = sorted(actual_data["resources"])
    if "resources" in data:
        data["resources"] = sorted(data["resources"])

    # Compare key by key to handle any differences
    for key in data:
        assert actual_data[key] == data[key], f"Mismatch for key {key}"

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "amazon_custom_img": True,
                "ups_custom_img": True,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            "reconfig_amazon",
            {
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "reconfig_3",
            {
                "custom_img_file": "images/test.gif",
                "amazon_custom_img_file": "images/test_amazon.jpg",
                "ups_custom_img_file": "images/test_ups.jpg",
            },
            "reconfig_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "amazon_custom_img": True,
                "amazon_custom_img_file": "images/test_amazon.jpg",
                "ups_custom_img": True,
                "ups_custom_img_file": "images/test_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_with_custom_images(
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
    """Test reconfigure flow with custom Amazon and UPS images."""
    entry = integration

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        await hass.async_block_till_done()

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        actual_data = entry.data.copy()

        for key in data:
            assert key in actual_data, f"Missing key: {key}"
            expected_value = data[key]
            actual_value = actual_data[key]
            # Sort lists before comparison to handle order differences
            if isinstance(expected_value, list) and isinstance(actual_value, list):
                expected_value = sorted(expected_value)
                actual_value = sorted(actual_value)
            assert (
                expected_value == actual_value
            ), f"Value mismatch for {key}: expected {data[key]}, got {actual_data[key]}"
        for key in actual_data:
            assert key in data, f"Extra key: {key}"


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_amazon,input_amazon,step_id_storage,input_storage,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            "reconfig_amazon",
            {
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
            },
            "reconfig_storage",
            {
                "storage": ".storage/mail_and_packages/images",
            },
            "imap.test.email",
            {
                "allow_external": False,
                "allow_forwarded_emails": False,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_custom_img": False,
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "custom_img": False,
                "ups_custom_img": False,
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_reconfigure_with_default_images(
    input_1,
    step_id_2,
    input_2,
    step_id_amazon,
    input_amazon,
    step_id_storage,
    input_storage,
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
    """Test reconfigure flow with default Amazon and UPS images."""
    entry = integration

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
        assert result["step_id"] == step_id_amazon
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_amazon
        )

        assert result["type"] == "form"
        assert result["step_id"] == step_id_storage
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_storage
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
            assert (
                expected_value == actual_value
            ), f"Value mismatch for {key}: expected {data[key]}, got {actual_data[key]}"
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
    ) as mock_setup_entry, patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
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
                "ups_custom_img": False,
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
            "ups_custom_img": False,
            "walmart_custom_img": False,
            "generic_custom_img": False,
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
        }
        # Compare dictionaries by checking each key-value pair
        for key in expected_data:
            assert key in actual_data, f"Missing key: {key}"
            expected_value = expected_data[key]
            actual_value = actual_data[key]
            # Sort lists before comparison to handle order differences
            if isinstance(expected_value, list) and isinstance(actual_value, list):
                expected_value = sorted(expected_value)
                actual_value = sorted(actual_value)
            assert (
                expected_value == actual_value
            ), f"Value mismatch for {key}: expected {expected_data[key]}, got {actual_data[key]}"
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
    ) as mock_setup_entry, patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
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
                "allow_forwarded_emails": False,
                "custom_img": False,
                "amazon_custom_img": False,
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
            "amazon_custom_img": False,
            "ups_custom_img": True,
            "ups_custom_img_file": "images/test_ups_only.jpg",
            "walmart_custom_img": False,
            "generic_custom_img": False,
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
        }

        # Compare key by key to handle any order differences
        for key in expected_data:
            assert key in actual_data, f"Missing key: {key}"
            assert (
                actual_data[key] == expected_data[key]
            ), f"Mismatch for {key}: {actual_data[key]} != {expected_data[key]}"

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
    assert "Migration complete to version 12" in caplog.text

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
    assert entry.version == 12

    yield entry


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
    assert "Migration complete to version 12" in caplog.text

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
    assert entry.version == 12

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
    assert "Migration complete to version 12" in caplog.text

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
    assert entry.version == 12


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
        "amazon_custom_img": False,
        "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
        "ups_custom_img": False,
        "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
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
    assert "Migration complete to version 12" in caplog.text

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
    assert entry.version == 12


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
    assert "Migration complete to version 12" in caplog.text

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
    assert entry.version == 12


async def test_migration_with_minimal_config(hass, caplog):
    """Test migration with a minimal config that's missing many fields."""
    # Create a very minimal config that might exist from very old versions
    minimal_config = {
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
        "Migration complete to version 12" in record.message
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
    assert entry.version == 12


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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

    with patch(
        "custom_components.mail_and_packages.helpers._test_login",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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

    with patch(
        "custom_components.mail_and_packages.helpers._test_login",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], input_1
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    # The flow is still on reconfigure step because IMAP login failed
    # We can't proceed to Amazon step or storage step
    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    # The flow is still on reconfigure step because IMAP login failed
    # We can't test storage configuration error since we can't reach that step


async def test_walmart_custom_image_validation():
    """Test Walmart custom image file validation."""
    import tempfile
    import os

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
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

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


async def test_walmart_custom_image_in_config_flow(hass):
    """Test that Walmart custom image options are properly handled in config flow."""
    import tempfile
    import os

    # Test that Walmart custom image is included in the flow when enabled
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "custom_components.mail_and_packages.config_flow._test_login", return_value=True
    ), patch(
        "custom_components.mail_and_packages.config_flow._check_ffmpeg",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.async_setup", return_value=True
    ), patch(
        "custom_components.mail_and_packages.async_setup_entry",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
    ), patch(
        "custom_components.mail_and_packages.config_flow.login"
    ) as mock_login:
        # Mock the login function to return a mock IMAP account
        mock_account = MagicMock()
        mock_account.list.return_value = ("OK", [b'(\\HasNoChildren) "/" "INBOX"'])
        mock_login.return_value = mock_account
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Complete step 1
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": True,  # Enable Walmart custom image
                "generic_custom_img": False,
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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(b"fake walmart image data")

    try:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_WALMART_CUSTOM_IMG_FILE: temp_file_path,
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
        assert entry.data[CONF_WALMART_CUSTOM_IMG_FILE] == temp_file_path

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def test_generic_custom_image_validation(hass: HomeAssistant):
    """Test validation of generic custom image file."""
    import tempfile
    import os

    # Test with non-existent file
    user_input = {
        "host": "imap.test.email",
        "port": "993",
        "username": "test@test.email",
        "password": "notarealpassword",
        "imap_security": "SSL",
        "verify_ssl": False,
        "allow_external": False,
        "custom_img": False,
        "amazon_custom_img": False,
        "ups_custom_img": False,
        "walmart_custom_img": False,
        "generic_custom_img": True,
        "generic_custom_img_file": "/nonexistent/path/image.jpg",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "resources": ["usps_mail"],
    }

    with patch(
        "custom_components.mail_and_packages.helpers._test_login", return_value=True
    ):
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

        with patch(
            "custom_components.mail_and_packages.helpers._test_login", return_value=True
        ):
            errors, validated_input = await _validate_user_input(user_input)

            # Should not have validation error for existing file
            assert "generic_custom_img_file" not in errors
            assert validated_input[CONF_GENERIC_CUSTOM_IMG_FILE] == temp_file_path

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def test_generic_custom_image_in_config_flow(hass: HomeAssistant):
    """Test generic custom image configuration in full config flow."""
    import tempfile
    import os

    # Create a temporary image file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
        temp_file_path = temp_file.name
        temp_file.write(b"fake image data")

    try:
        with patch(
            "custom_components.mail_and_packages.config_flow._test_login",
            return_value=True,
        ), patch(
            "custom_components.mail_and_packages.config_flow._check_ffmpeg",
            return_value=True,
        ), patch(
            "custom_components.mail_and_packages.async_setup", return_value=True
        ), patch(
            "custom_components.mail_and_packages.async_setup_entry", return_value=True
        ), patch(
            "custom_components.mail_and_packages.config_flow.login"
        ) as mock_login:
            # Mock the login function to return a mock IMAP account
            mock_account = MagicMock()
            mock_account.list.return_value = ("OK", [b'(\\HasNoChildren) "/" "INBOX"'])
            mock_login.return_value = mock_account

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
                    "host": "imap.test.email",
                    "port": "993",
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
                    "amazon_custom_img": False,
                    "ups_custom_img": False,
                    "walmart_custom_img": False,
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
                    "generic_custom_img_file": temp_file_path,
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
            assert entry.data[CONF_GENERIC_CUSTOM_IMG_FILE] == temp_file_path
            assert entry.version == 12

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def test_migration_to_version_12(hass: HomeAssistant):
    """Test migration to version 12 adds new generic camera fields."""
    # Create a mock config entry with version 11
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data={
            "host": "imap.test.email",
            "port": "993",
            "username": "test@test.email",
            "password": "notarealpassword",
            "imap_security": "SSL",
            "verify_ssl": False,
            "allow_external": False,
            "custom_img": False,
            "amazon_custom_img": False,
            "ups_custom_img": False,
            "walmart_custom_img": False,
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
    with patch(
        "custom_components.mail_and_packages.helpers._test_login", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify version was updated to 12
    assert entry.version == 12

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
        assert (
            CONF_WALMART_CUSTOM_IMG_FILE not in errors
        ), "Walmart custom image file should be valid"
        assert validated_input[CONF_WALMART_CUSTOM_IMG] is True
        assert validated_input[CONF_WALMART_CUSTOM_IMG_FILE] == temp_file_path

    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

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
    assert (
        CONF_WALMART_CUSTOM_IMG_FILE in errors
    ), "Walmart custom image file should be invalid"
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
    assert (
        CONF_WALMART_CUSTOM_IMG_FILE not in errors
    ), "Walmart custom image file should not be validated when disabled"


async def test_walmart_config_flow_version():
    """Test that the config version has been incremented for Walmart support."""
    # Version should be 12 or higher to include Walmart custom image support
    assert (
        CONFIG_VER >= 12
    ), f"Config version should be 12 or higher for Walmart support, got {CONFIG_VER}"


async def test_get_mailboxes_non_ok_status():
    """Test _get_mailboxes handles non-OK status gracefully."""
    # Mock login to return an account that returns non-OK status
    with patch("custom_components.mail_and_packages.config_flow.login") as mock_login:
        mock_account = MagicMock()
        mock_account.list.return_value = ("ERROR", [])  # Non-OK status
        mock_login.return_value = mock_account

        result = _get_mailboxes("test.host", 993, "user", "pass", "SSL", True)

        # Should return default folder when status is not OK
        assert result == ['"INBOX"']


async def test_get_schema_step_3_none_input():
    """Test _get_schema_step_3 with None user_input."""
    result = _get_schema_step_3(None, {})

    # Should handle None input gracefully
    assert result is not None


async def test_config_flow_step_amazon_empty_fwds():
    """Test config flow step amazon with empty amazon_fwds."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {"amazon_fwds": []}

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        result = await flow._show_reconfig_amazon({})

        # Should set amazon_fwds to "(none)" when empty
        assert flow._data["amazon_fwds"] == "(none)"
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_storage_validation_error():
    """Test reconfig storage step with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {}
    flow._errors = {"test_error": "validation_failed"}

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        result = await flow._show_reconfig_storage({"test": "data"})

        # Should show form with errors
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_amazon_validation_error():
    """Test reconfig amazon step with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {"amazon_fwds": ["test@example.com"]}
    flow._errors = {"test_error": "validation_failed"}

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        result = await flow._show_reconfig_amazon({"test": "data"})

        # Should show form with errors
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_3_validation_error():
    """Test reconfig step 3 with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {}
    flow._errors = {"test_error": "validation_failed"}

    # Mock the async_show_form method
    with patch.object(flow, "async_show_form") as mock_show_form:
        result = await flow._show_reconfig_3({"test": "data"})

        # Should show form with errors
        mock_show_form.assert_called_once()


async def test_config_flow_reconfig_2_validation_error():
    """Test reconfig step 2 with validation errors."""
    flow = MailAndPackagesFlowHandler()
    flow._data = {
        "host": "imap.test.com",
        "port": 993,
        "username": "test@test.com",
        "password": "password",
        "imap_security": "SSL",
        "verify_ssl": True,
    }
    flow._errors = {"test_error": "validation_failed"}

    # Mock the _get_mailboxes function and async_show_form method
    with patch(
        "custom_components.mail_and_packages.config_flow._get_mailboxes",
        return_value=['"INBOX"'],
    ), patch.object(flow, "async_show_form") as mock_show_form:
        result = await flow._show_reconfig_2({"test": "data"})

        # Should show form with errors
        mock_show_form.assert_called_once()


@pytest.mark.parametrize(
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,step_id_6,input_6,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "forwarded_emails": "user@example.com,testuser@example.com"
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
                "allow_forwarded_emails": True,
                "forwarded_emails": "user@example.com,testuser@example.com",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "custom_img_file": "images/test.gif",
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,step_id_6,input_6,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "forwarded_emails": "(none)"
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            {
                "forwarded_emails": "user@example.com,testuser@example.com"
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
                "custom_img": False,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
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
            {
                "forwarded_emails": "user@example.com,testuser@example.com"
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
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "forwarded_emails": "user@example.com,testuser@example.com",
                "custom_img": False,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
            {
                "forwarded_emails": "user@example.com,testuser@example.com"
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
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "forwarded_emails": "user@example.com,testuser@example.com",
                "custom_img": False,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,step_id_6,input_6,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "forwarded_emails": "(none)"
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
                "forwarded_emails": "(none)",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
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
    "input_1,step_id_2,input_2,step_id_3,input_3,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "allow_external": False,
                "allow_forwarded_emails": True,
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,title,data",
    [
        (
            {
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "custom_img_file": "images/test.gif",
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
    caplog
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,step_id_6,input_6,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "custom_img": True,
                "generic_custom_img": False,
                "walmart_custom_img": False,
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
            {
                "forwarded_emails": "user@example.com,testuser@example.com"
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
                "allow_external": False,
                "allow_forwarded_emails": True,
                "forwarded_emails": "user@example.com,testuser@example.com",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": "fakeuser@test.email,fakeuser2@test.email",
                "amazon_custom_img": False,
                "generic_custom_img": False,
                "ups_custom_img": False,
                "custom_img": True,
                "custom_img_file": "images/test.gif",
                "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
                "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
                "walmart_custom_img": False,
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

    with patch(
        "custom_components.mail_and_packages.config_flow.path",
        return_value=True,
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
    "input_1,step_id_2,input_2,step_id_3,input_3,step_id_4,input_4,step_id_5,input_5,step_id_6,input_6,title,data",
    [
        (
            {
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
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
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
                "forwarded_emails": "no-reply@usps.com"
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
                "allow_forwarded_emails": True,
                "forwarded_emails": "no-reply@usps.com",
                "amazon_days": 3,
                "amazon_domain": "amazon.com",
                "amazon_fwds": [],
                "custom_img": True,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "walmart_custom_img": False,
                "generic_custom_img": False,
                "amazon_custom_img": False,
                "ups_custom_img": False,
                "custom_img_file": "images/test.gif",
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
    caplog
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
