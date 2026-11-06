"""Tests for application_credentials.py."""

from unittest.mock import MagicMock

import pytest
from homeassistant.components.application_credentials import ClientCredential

from custom_components.mail_and_packages.application_credentials import (
    OAUTH_SERVERS,
    MailAuthImplementation,
    async_get_auth_implementation,
    implementation_for_auth_type,
)
from custom_components.mail_and_packages.const import (
    AUTH_TYPE_OAUTH_GOOGLE,
    AUTH_TYPE_OAUTH_MICROSOFT,
    DOMAIN,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client_id", "auth_type"),
    [
        ("id.apps.googleusercontent.com", AUTH_TYPE_OAUTH_GOOGLE),
        ("id", AUTH_TYPE_OAUTH_MICROSOFT),
    ],
)
async def test_async_get_auth_implementation(hass, client_id, auth_type):
    """Without a mailbox the client ID picks the default server."""
    cred = ClientCredential(client_id, "secret")
    impl = await async_get_auth_implementation(hass, DOMAIN, cred)

    assert impl.domain == DOMAIN
    assert impl.auth_type == auth_type
    assert impl.authorize_url == OAUTH_SERVERS[auth_type].authorize_url
    assert impl.token_url == OAUTH_SERVERS[auth_type].token_url


@pytest.mark.asyncio
async def test_mailbox_auth_type_wins(hass):
    """The mailbox's own auth type decides the server, not the client ID."""
    cred = ClientCredential("id", "secret", "Mail")
    impl = await async_get_auth_implementation(hass, DOMAIN, cred)

    google = implementation_for_auth_type(impl, AUTH_TYPE_OAUTH_GOOGLE)

    assert isinstance(google, MailAuthImplementation)
    assert google is not impl
    assert google.domain == DOMAIN
    assert google.name == "Mail"
    assert google.client_id == "id"
    assert google.client_secret == "secret"
    assert google.authorize_url == OAUTH_SERVERS[AUTH_TYPE_OAUTH_GOOGLE].authorize_url
    assert google.token_url == OAUTH_SERVERS[AUTH_TYPE_OAUTH_GOOGLE].token_url
    # The original is left alone for anyone else holding it.
    assert impl.token_url == OAUTH_SERVERS[AUTH_TYPE_OAUTH_MICROSOFT].token_url
    assert implementation_for_auth_type(google, AUTH_TYPE_OAUTH_GOOGLE) is google


def test_other_implementations_unchanged():
    """Implementations that are not ours are passed through."""
    other = MagicMock()
    assert implementation_for_auth_type(other, AUTH_TYPE_OAUTH_GOOGLE) is other
