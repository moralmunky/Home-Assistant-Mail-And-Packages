""" Test Mail and Packages config flow """
from homeassistant import config_entries, setup
from custom_components.mail_and_packages.const import DOMAIN
from pytest_homeassistant_custom_component.async_mock import patch
import pytest


@pytest.mark.parametrize(
    "title_1,input_1,step_id_2,input_2,title_2,data",
    [
        (
            "Mail and Packages (Step 1 of 2)",
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
            },
            "config_2",
            {
                "amazon_fwds": '""',
                "folder": '"INBOX"',
                "generate_mp4": "false",
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": "true",
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
            "Mail and Packages (Step 2 of 2)",
            {
                "host": "imap.test.email",
                "port": "993",
                "username": "test@test.email",
                "password": "notarealpassword",
                "amazon_fwds": '""',
                "folder": '"INBOX"',
                "generate_mp4": "false",
                "gif_duration": 5,
                "image_path": "/config/www/mail_and_packages/",
                "image_security": "true",
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
    title_1, input_1, step_id_2, input_2, title_2, data, hass, mock_login_test
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
        "custom_components.mail_and_packages.async_setup", return_value=True
    ) as mock_setup, patch(
        "custom_components.mail_and_packages.async_setup_entry", return_value=True,
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
    assert result3["title"] == title_2
    assert result3["data"] == data

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
