"""Tests for Mail and Packages re-authentication flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.config_flow import MailAndPackagesFlowHandler
from custom_components.mail_and_packages.const import (
    AUTH_TYPE_PASSWORD,
    CONF_AUTH_TYPE,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_password_reauth_flow(hass):
    """Test the password re-authentication flow."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "old_password",
            CONF_AUTH_TYPE: AUTH_TYPE_PASSWORD,
        },
        source=config_entries.SOURCE_USER,
        options={},
        entry_id="reauth_test_entry",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.mail_and_packages.config_flow._validate_login",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"


@pytest.mark.asyncio
async def test_oauth_reauth_flow(hass):
    """Test the OAuth re-authentication flow."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test OAuth",
        data={
            CONF_AUTH_TYPE: "oauth2_microsoft",
            "token": {"access_token": "old_token"},
            "host": "imap.test.com",
        },
        source=config_entries.SOURCE_USER,
        options={},
        entry_id="reauth_oauth_test_entry",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    # Trigger external authentication for non-password authentication types
    with (
        patch(
            "custom_components.mail_and_packages.config_flow.MailAndPackagesFlowHandler.async_step_pick_implementation",
            return_value={"type": "external", "url": "http://fake"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )
    assert result["type"] == "external"

    # Test the OAuth2 completion redirect handler
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_REAUTH}
    flow._entry = entry
    flow._data = entry.data.copy()

    result = await flow.async_oauth_create_entry(data={"token": "new_token"})
    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
