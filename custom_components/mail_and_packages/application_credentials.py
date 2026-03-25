"""Application credentials for Mail and Packages."""

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

OAUTH_SERVERS = {
    "oauth2_microsoft": AuthorizationServer(
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    ),
    "oauth2_google": AuthorizationServer(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
    ),
}


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation based on provider selected in config flow."""
    # Config flow stores the selected provider before triggering OAuth
    provider = hass.data[DOMAIN]["oauth_provider"]
    server = OAUTH_SERVERS[provider]

    return AuthImplementation(
        hass,
        auth_domain,
        credential,
        server,
    )
