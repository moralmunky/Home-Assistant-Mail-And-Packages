"""Tests that each mailbox uses its own OAuth provider."""

import asyncio
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from homeassistant import config_entries
from homeassistant.components import application_credentials
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.application_credentials import (
    OAUTH_SERVERS,
)
from custom_components.mail_and_packages.const import (
    AUTH_TYPE_OAUTH_GOOGLE,
    AUTH_TYPE_OAUTH_MICROSOFT,
    CONF_AUTH_TYPE,
    DOMAIN,
)
from custom_components.mail_and_packages.coordinator.helpers import (
    async_oauth_access_token,
)

GOOGLE_CLIENT_ID = "google-client.apps.googleusercontent.com"
MICROSOFT_CLIENT_ID = "microsoft-client"
GOOGLE_AUTH_DOMAIN = "google_credential"
MICROSOFT_AUTH_DOMAIN = "microsoft_credential"
GOOGLE_TOKEN_URL = OAUTH_SERVERS[AUTH_TYPE_OAUTH_GOOGLE].token_url
MICROSOFT_TOKEN_URL = OAUTH_SERVERS[AUTH_TYPE_OAUTH_MICROSOFT].token_url


def _expired_token(name: str) -> dict:
    """Return a token that needs a refresh."""
    return {
        "access_token": f"{name}_old",
        "refresh_token": f"{name}_refresh",
        "token_type": "Bearer",
        "expires_in": 3600,
        "expires_at": 0,
    }


def _mailbox(hass, auth_type: str, auth_domain: str, name: str) -> MockConfigEntry:
    """Add an OAuth mailbox entry tied to one application credential."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            CONF_AUTH_TYPE: auth_type,
            CONF_HOST: f"imap.{name}.test",
            CONF_USERNAME: f"user@{name}.test",
            "auth_implementation": auth_domain,
            "token": _expired_token(name),
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def mailboxes(hass):
    """Set up one Google and one Microsoft mailbox, each with its credential."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(GOOGLE_CLIENT_ID, "google-secret", "Google"),
        GOOGLE_AUTH_DOMAIN,
    )
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(MICROSOFT_CLIENT_ID, "microsoft-secret", "Microsoft"),
        MICROSOFT_AUTH_DOMAIN,
    )
    return {
        AUTH_TYPE_OAUTH_GOOGLE: _mailbox(
            hass, AUTH_TYPE_OAUTH_GOOGLE, GOOGLE_AUTH_DOMAIN, "gmail"
        ),
        AUTH_TYPE_OAUTH_MICROSOFT: _mailbox(
            hass, AUTH_TYPE_OAUTH_MICROSOFT, MICROSOFT_AUTH_DOMAIN, "outlook"
        ),
    }


def _mock_token_servers(aioclient_mock) -> None:
    """Answer refreshes from each provider with a provider specific token."""
    for url, name in ((GOOGLE_TOKEN_URL, "gmail"), (MICROSOFT_TOKEN_URL, "outlook")):
        aioclient_mock.post(
            url,
            payload={
                "access_token": f"{name}_new",
                "refresh_token": f"{name}_refresh",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
            repeat=True,
        )


def _token_requests(aioclient_mock) -> dict[str, str]:
    """Map each refresh token sent to the URL it was sent to."""
    return {
        call.kwargs["data"]["refresh_token"]: str(url)
        for (_, url), calls in aioclient_mock.requests.items()
        for call in calls
    }


@pytest.mark.parametrize(
    "order",
    [
        (AUTH_TYPE_OAUTH_GOOGLE, AUTH_TYPE_OAUTH_MICROSOFT),
        (AUTH_TYPE_OAUTH_MICROSOFT, AUTH_TYPE_OAUTH_GOOGLE),
    ],
)
async def test_refresh_uses_each_mailbox_provider(
    hass, mailboxes, aioclient_mock, order
):
    """Refreshing one mailbox never sends another mailbox to the wrong server."""
    _mock_token_servers(aioclient_mock)

    for auth_type in order:
        await async_oauth_access_token(hass, mailboxes[auth_type], auth_type)

    assert _token_requests(aioclient_mock) == {
        "gmail_refresh": GOOGLE_TOKEN_URL,
        "outlook_refresh": MICROSOFT_TOKEN_URL,
    }
    assert (
        mailboxes[AUTH_TYPE_OAUTH_GOOGLE].data["token"]["access_token"] == "gmail_new"
    )
    assert (
        mailboxes[AUTH_TYPE_OAUTH_MICROSOFT].data["token"]["access_token"]
        == "outlook_new"
    )


async def test_refresh_at_the_same_time(hass, mailboxes, aioclient_mock):
    """Mailboxes refreshing together each reach their own server."""
    _mock_token_servers(aioclient_mock)
    get_platform = application_credentials._get_platform

    async def slow_get_platform(*args):
        # Right after startup the platform is still loading, so the lookup
        # yields and the mailboxes' refreshes overlap.
        await asyncio.sleep(0)
        return await get_platform(*args)

    with patch.object(application_credentials, "_get_platform", slow_get_platform):
        tokens = await asyncio.gather(
            *(
                async_oauth_access_token(hass, entry, auth_type)
                for auth_type, entry in mailboxes.items()
            )
        )

    assert tokens == ["gmail_new", "outlook_new"]
    assert _token_requests(aioclient_mock) == {
        "gmail_refresh": GOOGLE_TOKEN_URL,
        "outlook_refresh": MICROSOFT_TOKEN_URL,
    }


@pytest.mark.usefixtures("current_request_with_host")
async def test_outlook_reauth_after_google_refresh(hass, mailboxes, aioclient_mock):
    """Outlook reauth signs in at Microsoft even right after a Gmail refresh."""
    _mock_token_servers(aioclient_mock)
    await async_oauth_access_token(
        hass, mailboxes[AUTH_TYPE_OAUTH_GOOGLE], AUTH_TYPE_OAUTH_GOOGLE
    )

    outlook = mailboxes[AUTH_TYPE_OAUTH_MICROSOFT]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": outlook.entry_id,
        },
        data=outlook.data,
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "pick_implementation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"implementation": MICROSOFT_AUTH_DOMAIN}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    url = urlparse(result["url"])
    authorize_url = OAUTH_SERVERS[AUTH_TYPE_OAUTH_MICROSOFT].authorize_url
    assert f"{url.scheme}://{url.netloc}{url.path}" == authorize_url
    query = parse_qs(url.query)
    assert query["client_id"] == [MICROSOFT_CLIENT_ID]
    assert query["login_hint"] == ["user@outlook.test"]
