"""Tests for application_credentials.py."""

import pytest
from homeassistant.components.application_credentials import ClientCredential

from custom_components.mail_and_packages.application_credentials import (
    async_get_auth_implementation,
)
from custom_components.mail_and_packages.const import DOMAIN


@pytest.mark.asyncio
async def test_async_get_auth_implementation(hass):
    """Test getting application credentials auth implementation."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["oauth_provider"] = "oauth2_microsoft"

    cred = ClientCredential("id", "secret")
    impl = await async_get_auth_implementation(hass, DOMAIN, cred)

    # Verify we can successfully get an AuthImplementation for the integration
    assert impl.domain == DOMAIN
