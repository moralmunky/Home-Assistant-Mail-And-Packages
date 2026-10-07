"""Tests for Mail and Packages HTTP image view."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from homeassistant.components.http import KEY_AUTHENTICATED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from custom_components.mail_and_packages.views import (
    ALLOWED_EXTENSIONS,
    CONTENT_TYPES,
    MailAndPackagesImageView,
)


@pytest.fixture
def mock_image_file(tmp_path):
    """Create a temporary dummy image file."""
    img_dir = tmp_path / "mail_and_packages"
    img_dir.mkdir(parents=True, exist_ok=True)
    test_file = img_dir / "test_mail.gif"
    test_file.write_bytes(b"GIF89a_fake_gif_content")
    return test_file


async def test_view_unauthenticated(hass):
    """Test image view rejects unauthenticated requests."""
    view = MailAndPackagesImageView(hass)
    req = MagicMock(spec=web.Request)
    req.get.side_effect = lambda key, default=None: (
        False if key == KEY_AUTHENTICATED else default
    )

    response = await view.get(req, "some_entry_id", "test_mail.gif")
    assert response.status == 401
    assert response.text == "Unauthorized"


async def test_view_entry_not_found(hass):
    """Test image view returns 404 when config entry is not found."""
    view = MailAndPackagesImageView(hass)
    req = MagicMock(spec=web.Request)
    req.get.side_effect = lambda key, default=None: (
        True if key == KEY_AUTHENTICATED else default
    )

    response = await view.get(req, "nonexistent_entry_id", "test_mail.gif")
    assert response.status == 404
    assert response.text == "Config entry not found"


async def test_view_invalid_extension(hass):
    """Test image view returns 400 for forbidden extensions."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="test_entry")
    entry.add_to_hass(hass)

    view = MailAndPackagesImageView(hass)
    req = MagicMock(spec=web.Request)
    req.get.side_effect = lambda key, default=None: (
        True if key == KEY_AUTHENTICATED else default
    )

    response = await view.get(req, "test_entry", "secrets.yaml")
    assert response.status == 400
    assert response.text == "Invalid file type"


async def test_view_path_traversal_blocked(hass, tmp_path):
    """Test image view blocks directory traversal attacks."""
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry",
        data={"storage": str(images_dir)},
    )
    entry.add_to_hass(hass)

    view = MailAndPackagesImageView(hass)
    req = MagicMock(spec=web.Request)
    req.get.side_effect = lambda key, default=None: (
        True if key == KEY_AUTHENTICATED else default
    )

    response = await view.get(req, "test_entry", "../secret.png")
    assert response.status == 403
    assert response.text == "Forbidden"


async def test_view_file_not_found(hass, tmp_path):
    """Test image view returns 404 when file does not exist."""
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry",
        data={"storage": str(images_dir)},
    )
    entry.add_to_hass(hass)

    view = MailAndPackagesImageView(hass)
    req = MagicMock(spec=web.Request)
    req.get.side_effect = lambda key, default=None: (
        True if key == KEY_AUTHENTICATED else default
    )

    response = await view.get(req, "test_entry", "nonexistent.gif")
    assert response.status == 404
    assert response.text == "File not found"


async def test_view_serves_file_success(hass, tmp_path):
    """Test image view successfully serves valid media files with correct Content-Type."""
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry",
        data={"storage": str(images_dir)},
    )
    entry.add_to_hass(hass)

    test_file = images_dir / "mail.png"
    test_file.write_bytes(b"\x89PNG\r\n\x1a\nfake_png")

    view = MailAndPackagesImageView(hass)
    req = MagicMock(spec=web.Request)
    req.get.side_effect = lambda key, default=None: (
        True if key == KEY_AUTHENTICATED else default
    )

    response = await view.get(req, "test_entry", "mail.png")
    assert isinstance(response, web.FileResponse)
    assert response.headers["Content-Type"] == "image/png"
    assert Path(response._path) == test_file


async def test_view_allowed_extensions_and_content_types():
    """Verify supported extensions and their MIME types."""
    assert ".gif" in ALLOWED_EXTENSIONS
    assert ".png" in ALLOWED_EXTENSIONS
    assert ".jpg" in ALLOWED_EXTENSIONS
    assert ".jpeg" in ALLOWED_EXTENSIONS
    assert ".mp4" in ALLOWED_EXTENSIONS
    assert CONTENT_TYPES[".gif"] == "image/gif"
    assert CONTENT_TYPES[".png"] == "image/png"
    assert CONTENT_TYPES[".mp4"] == "video/mp4"
