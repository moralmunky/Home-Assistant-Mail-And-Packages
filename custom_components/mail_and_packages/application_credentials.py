"""Application credentials for Mail and Packages."""

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import AUTH_TYPE_OAUTH_GOOGLE, AUTH_TYPE_OAUTH_MICROSOFT

OAUTH_SERVERS = {
    AUTH_TYPE_OAUTH_MICROSOFT: AuthorizationServer(
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    ),
    AUTH_TYPE_OAUTH_GOOGLE: AuthorizationServer(
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
    ),
}

# Every Google OAuth client ID ends with this. Microsoft uses a bare GUID.
GOOGLE_CLIENT_ID_SUFFIX = ".apps.googleusercontent.com"


class MailAuthImplementation(AuthImplementation):
    """Application credential that signs in through one provider's server."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        auth_type: str,
    ) -> None:
        """Initialize with the server that belongs to auth_type."""
        super().__init__(hass, auth_domain, credential, OAUTH_SERVERS[auth_type])
        self.credential = credential
        self.auth_type = auth_type


def implementation_for_auth_type(
    implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    auth_type: str,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the implementation using the server for this mailbox's auth type.

    Each mailbox stores its provider as its auth type, so the token and
    authorize requests for one mailbox never depend on another mailbox.
    Implementations from other sources are returned unchanged.
    """
    if (
        not isinstance(implementation, MailAuthImplementation)
        or implementation.auth_type == auth_type
    ):
        return implementation
    return MailAuthImplementation(
        implementation.hass,
        implementation.domain,
        implementation.credential,
        auth_type,
    )


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the auth implementation for one application credential.

    Home Assistant builds this without saying which mailbox it is for, so
    the default server comes from the client ID. Setup, reauth, reconfigure
    and token refresh then switch it to the mailbox's own auth type with
    implementation_for_auth_type.
    """
    auth_type = (
        AUTH_TYPE_OAUTH_GOOGLE
        if credential.client_id.endswith(GOOGLE_CLIENT_ID_SUFFIX)
        else AUTH_TYPE_OAUTH_MICROSOFT
    )
    return MailAuthImplementation(hass, auth_domain, credential, auth_type)
