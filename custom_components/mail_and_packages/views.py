"""HTTP Views for Mail and Packages image serving."""

from __future__ import annotations

import logging
from pathlib import Path

import anyio
from aiohttp import web
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .utils.image import default_image_path

_LOGGER = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".gif", ".jpg", ".jpeg", ".png", ".mp4"}
CONTENT_TYPES = {
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp4": "video/mp4",
}


class MailAndPackagesImageView(HomeAssistantView):
    """View to serve mail and package media securely."""

    url = "/api/mail_and_packages/image/{entry_id}/{filename}"
    name = "api:mail_and_packages:image"
    requires_auth = False  # Protected via signed paths (async_sign_path)

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, filename: str
    ) -> web.Response | web.FileResponse:
        """Handle image requests."""
        if not request.get(KEY_AUTHENTICATED, False):
            return web.Response(status=401, text="Unauthorized")

        config_entry = self.hass.config_entries.async_get_entry(entry_id)
        if not config_entry or config_entry.domain != DOMAIN:
            _LOGGER.debug(
                "Image view request rejected: unknown config entry %s", entry_id
            )
            return web.Response(status=404, text="Config entry not found")

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            _LOGGER.warning(
                "Image view request rejected: invalid extension for %s", filename
            )
            return web.Response(status=400, text="Invalid file type")

        storage_path_str = default_image_path(self.hass, config_entry)
        base_dir = await anyio.Path(self.hass.config.path(storage_path_str)).resolve()

        # Sanitize against path traversal: support filename or subfolder/filename (e.g. usps/file.gif)
        requested_file = await (base_dir / filename).resolve()
        if not requested_file.is_relative_to(base_dir):
            _LOGGER.warning(
                "Image view path traversal attempt blocked for entry %s: %s",
                entry_id,
                filename,
            )
            return web.Response(status=403, text="Forbidden")

        if not await requested_file.is_file():
            _LOGGER.debug(
                "Image view file not found for entry %s: %s",
                entry_id,
                requested_file,
            )
            return web.Response(status=404, text="File not found")

        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
        return web.FileResponse(requested_file, headers={"Content-Type": content_type})
