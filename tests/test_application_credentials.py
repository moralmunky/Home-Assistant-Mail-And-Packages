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

    # AuthImplementation stores the Server as an attribute or property, it is accessible
    # However just ensuring we can instantiate it and it runs the code covers lines 3-35
    assert impl.domain == DOMAIN
