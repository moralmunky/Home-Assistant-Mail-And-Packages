"""Tests for Mail and Packages helper functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.helpers import (
    copy_images,
    fetch,
    get_count,
    get_items,
    get_mails,
    get_resources,
)


@pytest.mark.asyncio
async def test_get_count_legacy(hass):
    """Test legacy get_count wrapper."""
    account = AsyncMock()
    mock_shipper = AsyncMock()
    mock_shipper.process.return_value = {"count": 1}

    mock_registry = {"ups_delivered": MagicMock(return_value=mock_shipper)}

    with patch.dict(
        "custom_components.mail_and_packages.helpers.SHIPPER_REGISTRY",
        mock_registry,
        clear=True,
    ):
        result = await get_count(account, "ups_delivered", False, "/path", hass)
        assert result["count"] == 1

        # Test no shipper found
        result = await get_count(account, "unknown", False, "/path", hass)
        assert result["count"] == 0


@pytest.mark.asyncio
async def test_get_mails_legacy(hass):
    """Test legacy get_mails wrapper."""
    account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.helpers.USPSShipper",
    ) as mock_shipper_class:
        mock_shipper = AsyncMock()
        mock_shipper.process.return_value = {"count": 5}
        mock_shipper_class.return_value = mock_shipper

        result = await get_mails(account, [], hass, {})
        assert result == 5


@pytest.mark.asyncio
async def test_fetch_legacy(hass):
    """Test legacy fetch wrapper."""
    account = AsyncMock()
    mock_shipper = AsyncMock()
    mock_shipper.process.return_value = {"count": 2}
    mock_registry = {"fedex_delivered": MagicMock(return_value=mock_shipper)}

    with patch.dict(
        "custom_components.mail_and_packages.helpers.SHIPPER_REGISTRY",
        mock_registry,
        clear=True,
    ):
        result = await fetch(hass, {}, account, "fedex_delivered")
        assert result == 2

        # Test no shipper found
        result = await fetch(hass, {}, account, "unknown")
        assert result == 0


@pytest.mark.asyncio
async def test_get_items_legacy(hass):
    """Test legacy get_items wrapper."""
    account = AsyncMock()
    mock_shipper = AsyncMock()
    mock_shipper.process.return_value = {"count": 3}
    mock_registry = {"dhl_delivered": MagicMock(return_value=mock_shipper)}

    with patch.dict(
        "custom_components.mail_and_packages.helpers.SHIPPER_REGISTRY",
        mock_registry,
        clear=True,
    ):
        result = await get_items(hass, {}, account, "dhl_delivered")
        assert result["count"] == 3

        # Test no shipper found
        result = await get_items(hass, {}, account, "unknown")
        assert result["count"] == 0


def test_get_resources():
    """Test get_resources."""
    resources = get_resources()
    assert "amazon_packages" in resources


def test_copy_images_mkdir(hass):
    """Test copy_images creating the directory."""
    config = MagicMock()
    config.get.return_value = "test_storage/"

    with (
        patch("custom_components.mail_and_packages.helpers.Path") as mock_path,
        patch("custom_components.mail_and_packages.helpers.os.walk", return_value=[]),
    ):
        mock_path_obj = MagicMock()
        # Mocking Path() calls
        mock_path.return_value = mock_path_obj
        mock_path_obj.__truediv__.return_value = mock_path_obj
        mock_path_obj.is_dir.return_value = False

        copy_images(hass, config)
        assert mock_path_obj.mkdir.called


@patch("custom_components.mail_and_packages.helpers.Path")
@patch("custom_components.mail_and_packages.helpers.copyfile")
@patch("custom_components.mail_and_packages.helpers.os.walk")
def test_copy_images_logic(mock_walk, mock_copy, mock_path, hass):
    """Test copy_images logic with directory creation and OSError."""
    config = MagicMock()
    config.get.return_value = "test_storage/"

    mock_path_obj = MagicMock()
    mock_path.return_value = mock_path_obj
    mock_path_obj.__truediv__.return_value = mock_path_obj

    # mkdir path
    mock_path_obj.is_dir.return_value = False

    # walk path
    mock_walk.return_value = [("/src", [], ["image.jpg"])]

    # copyfile path triggers OSError
    mock_copy.side_effect = OSError("Copy failed")

    copy_images(hass, config)

    assert mock_path_obj.mkdir.called
    assert mock_copy.called
