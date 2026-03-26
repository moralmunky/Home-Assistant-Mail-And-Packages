"""Tests for image utilities."""

import datetime
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from custom_components.mail_and_packages.utils.image import (
    _generate_mp4,
    cleanup_images,
    copy_overlays,
    default_image_path,
    generate_delivery_gif,
    generate_grid_img,
    hash_file,
    image_file_name,
    io_save_file,
    random_filename,
    resize_images,
)


@pytest.mark.asyncio
async def test_cleanup_images():
    """Test cleanup_images success path."""
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_file.is_file.return_value = True
        mock_file.suffix = ".jpg"

        mock_path_obj.exists.return_value = True
        mock_path_obj.is_dir.return_value = True
        mock_path_obj.iterdir.return_value = [mock_file]
        mock_path_obj.__truediv__.return_value = mock_path_obj

        mock_path.side_effect = lambda *args: mock_path_obj

        cleanup_images("/fake/path/")
        assert mock_path_obj.unlink.called


@pytest.mark.asyncio
async def test_cleanup_images_remove_err(caplog):
    """Test cleanup_images with removal error."""
    caplog.set_level("ERROR")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.is_dir.return_value = True
        mock_path_obj.exists.return_value = True
        # One file that matches the suffix
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_path_obj.iterdir.return_value = [mock_file]
        mock_path_obj.unlink.side_effect = OSError("Permission denied")
        mock_path.side_effect = lambda *args: mock_path_obj

        cleanup_images("/fake/path/")
        assert "Error attempting to remove found image" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_directory_missing(caplog):
    """Test cleanup_images when the directory does not exist."""
    caplog.set_level("DEBUG")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.is_dir.return_value = False
        mock_path.side_effect = lambda *args: mock_path_obj

        cleanup_images("/nonexistent/path/")
        assert "cleanup_images - Directory does not exist" in caplog.text


@pytest.mark.asyncio
async def test_resize_images_corrupt_file(caplog):
    """Test resize_images with a corrupt or non-image file."""
    caplog.set_level("ERROR")
    with patch(
        "custom_components.mail_and_packages.utils.image.Image.open"
    ) as mock_open:
        mock_open.side_effect = OSError("Corrupt image")

        result = resize_images(["corrupt.jpg"], 724, 320)
        assert result == []
        assert "Error processing image" in caplog.text


@pytest.mark.asyncio
async def test_copy_overlays_error_handling(caplog):
    """Test copy_overlays handles errors gracefully."""
    caplog.set_level("DEBUG")
    with (
        patch("custom_components.mail_and_packages.utils.image.copyfile") as mock_copy,
        patch("custom_components.mail_and_packages.utils.image.OVERLAY", ["over1.png"]),
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.return_value = []  # Ensure it tries to copy
        mock_path.side_effect = lambda *args: mock_path_obj
        mock_copy.side_effect = OSError("OS Error")
        copy_overlays("/fake/path/")
        # copy_overlays does not have try/except, but we test the code path


@pytest.mark.asyncio
async def test_generate_delivery_gif_coverage(caplog):
    """Test generate_delivery_gif success and handling."""
    caplog.set_level("ERROR")
    with (
        patch(
            "custom_components.mail_and_packages.utils.image.Image.open"
        ) as mock_open,
        patch(
            "custom_components.mail_and_packages.utils.image.ImageOps.exif_transpose"
        ) as mock_transpose,
    ):
        mock_img1 = MagicMock()
        mock_img2 = MagicMock()
        mock_open.side_effect = [mock_img1, mock_img2]
        mock_transpose.side_effect = lambda x: x

        # Test success with 2 images
        result = generate_delivery_gif(["img1.jpg", "img2.jpg"], "out.gif")
        assert result is True
        assert mock_img1.save.called

        # Test failure (OSError on save)
        mock_img3 = MagicMock()
        mock_open.side_effect = [mock_img3]
        mock_img3.save.side_effect = OSError("Save error")
        result = generate_delivery_gif(["img1.jpg"], "out.gif")
        assert result is False
        assert "Error creating animated GIF" in caplog.text


@pytest.mark.asyncio
async def test_hash_file():
    """Test hash_file success path."""
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.open.return_value.__enter__.return_value.read.side_effect = [
            b"test data",
            b"",
        ]
        mock_path.side_effect = lambda *args: mock_path_obj

        result = hash_file("test.jpg")
        assert len(result) == 40  # SHA-1 length


@pytest.mark.asyncio
async def test_default_image_path():
    """Test default_image_path with different configs."""
    mock_hass = MagicMock()
    mock_config = MagicMock()

    # Test with storage config in data
    mock_config.data = {"storage": "/config/images/"}
    # Delete get to trigger AttributeError
    del mock_config.get
    assert default_image_path(mock_hass, mock_config) == "/config/images/"

    # Test without storage config
    mock_config = MagicMock()
    mock_config.get.return_value = None
    assert "custom_components/mail_and_packages/images/" in default_image_path(
        mock_hass, mock_config
    )


@pytest.mark.asyncio
async def test_image_file_name_amazon_courier():
    """Test image_file_name for Amazon courier branch."""
    mock_hass = MagicMock()
    config = {"amazon_custom_img": False, "storage": "/config/mail_images/"}
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.hash_file",
            return_value="abc",
        ),
        patch("custom_components.mail_and_packages.utils.image.copyfile"),
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.return_value = []
        mock_path.side_effect = lambda *args: mock_path_obj

        result = image_file_name(mock_hass, config, amazon=True)
        assert result.endswith(".jpg")


def test_generate_mp4_exists():
    """Test _generate_mp4 when old mp4 exists."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.subprocess.run"
        ) as mock_run,
        patch(
            "custom_components.mail_and_packages.utils.image.cleanup_images"
        ) as mock_cleanup,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.is_file.return_value = True
        mock_path_obj.parent = MagicMock()
        mock_path.side_effect = lambda *args: mock_path_obj

        _generate_mp4("/path/", "test.gif")
        assert mock_cleanup.called
        assert mock_run.called


def test_copy_overlays_success():
    """Test copy_overlays success path (no copy needed)."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch("custom_components.mail_and_packages.utils.image.copyfile") as mock_copy,
        patch("custom_components.mail_and_packages.utils.image.OVERLAY", ["over1.png"]),
    ):
        mock_path_obj = MagicMock()
        # Mocking all overlays exist
        mock_file = MagicMock()
        mock_file.name = "over1.png"
        mock_path_obj.iterdir.return_value = [mock_file]
        mock_path.side_effect = lambda *args: mock_path_obj

        copy_overlays("/path/")
        assert not mock_copy.called


@pytest.mark.asyncio
async def test_cleanup_images_file_not_found(caplog):
    """Test cleanup_images with FileNotFoundError."""
    caplog.set_level("DEBUG")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.side_effect = FileNotFoundError()
        mock_path.side_effect = lambda *args: mock_path_obj

        cleanup_images("/fake/path/")
        assert "cleanup_images - Directory removed during cleanup" in caplog.text


@pytest.mark.asyncio
async def test_image_file_name_default():
    """Test image_file_name with default mail_none.gif."""
    mock_hass = MagicMock()
    config = {"amazon_custom_img": False}

    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.hash_file",
            return_value="abc",
        ),
        patch("custom_components.mail_and_packages.utils.image.copyfile") as mock_copy,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.return_value = []
        mock_path.side_effect = lambda *args: mock_path_obj

        result = image_file_name(mock_hass, config)
        # If no images found, it generates a new UUID.gif if image_name in mail_none
        assert result.endswith(".gif")
        assert len(result) > 20
        assert mock_copy.called


@pytest.mark.asyncio
async def test_image_file_name_amazon_custom():
    """Test image_file_name with Amazon custom image."""
    mock_hass = MagicMock()
    config = {
        "amazon_custom_img": True,
        "amazon_custom_img_file": "custom_amazon.jpg",
        "storage": "/config/mail_images/",
    }

    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch("custom_components.mail_and_packages.utils.image.copyfile"),
        patch(
            "custom_components.mail_and_packages.utils.image.get_formatted_date",
            return_value="25-Mar-2026",
        ),
    ):
        mock_path_obj = MagicMock()
        # Mocking an existing file with different hash
        mock_existing_file = MagicMock()
        mock_existing_file.name = "old_amazon.jpg"
        mock_existing_file.suffix = ".jpg"
        mock_existing_file.stat.return_value.st_ctime = datetime.datetime(
            2026, 3, 24
        ).timestamp()

        mock_path_obj.iterdir.return_value = [mock_existing_file]
        mock_path.side_effect = lambda *args: mock_path_obj

        # Mock hash_file for existing file check: first call is source, second is existing
        with patch(
            "custom_components.mail_and_packages.utils.image.hash_file",
            side_effect=["abc", "diff"],
        ):
            result = image_file_name(mock_hass, config, amazon=True)
            # Should generate new UUID because hash is different and date is different
            assert len(result) > 20
            assert result.endswith(".jpg")


@pytest.mark.asyncio
async def test_image_file_name_error_paths(caplog):
    """Test image_file_name error handling."""
    mock_hass = MagicMock()
    # Ensure it doesn't try to use specific couriers
    config = {"custom_img": True, "custom_img_file": "mail_none.gif"}
    caplog.set_level("ERROR")

    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.mkdir.side_effect = OSError("No space left")
        mock_path.side_effect = lambda *args: mock_path_obj

        # Patching constants if necessary, but here it should work if config has keys
        result = image_file_name(mock_hass, config)
        assert "Error creating directory" in caplog.text
        assert result == "mail_none.gif"


def test_random_filename():
    """Test random_filename generation."""
    res = random_filename()
    assert res.endswith(".jpg")
    assert len(res) > 30


def test_io_save_file():
    """Test io_save_file logic."""
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        io_save_file("test.jpg", b"data")
        assert mock_path_obj.open.called
        mock_path_obj.open.return_value.__enter__.return_value.write.assert_called_with(
            b"data"
        )


def test_generate_mp4_success():
    """Test _generate_mp4 success path."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.subprocess.run"
        ) as mock_run,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.is_file.return_value = False
        mock_path.return_value = mock_path_obj

        _generate_mp4("/path/", "test.gif")
        assert mock_run.called


def test_generate_mp4_fail(caplog):
    """Test _generate_mp4 failure path."""
    caplog.set_level("ERROR")
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.subprocess.run"
        ) as mock_run,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.is_file.return_value = False
        mock_path.return_value = mock_path_obj
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg")

        _generate_mp4("/path/", "test.gif")
        assert "FFmpeg failed to generate MP4" in caplog.text


def test_generate_grid_img():
    """Test generate_grid_img logic."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.subprocess.call"
        ) as mock_call,
    ):
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj

        generate_grid_img("/path/", "test.gif", 5)
        assert mock_call.called


@pytest.mark.asyncio
async def test_resize_images_success():
    """Test resize_images success path."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.Image.open"
        ) as mock_open,
        patch(
            "custom_components.mail_and_packages.utils.image.ImageOps.pad"
        ) as mock_pad,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.with_suffix.return_value = "test.gif"
        mock_path_obj.open.return_value.__enter__.return_value = MagicMock()
        mock_path.side_effect = lambda *args: mock_path_obj

        mock_img = MagicMock()
        mock_img.format = "GIF"
        mock_open.return_value = (
            mock_img  # Image.open(fd_img) returns img directly, not a CTX
        )
        mock_pad.return_value = mock_img

        result = resize_images(["test.jpg"], 100, 100)
        assert len(result) == 1
        assert result[0] == "test.gif"


@pytest.mark.asyncio
async def test_image_file_name_existing_today():
    """Test image_file_name when image created today exists."""
    mock_hass = MagicMock()
    config = {"custom_img": True, "custom_img_file": "mail_none.gif"}

    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.hash_file",
            return_value="abc",
        ),
        patch("custom_components.mail_and_packages.utils.image.copyfile"),
        patch(
            "custom_components.mail_and_packages.utils.image.get_formatted_date",
            return_value="25-Mar-2026",
        ),
    ):
        mock_path_obj = MagicMock()
        mock_existing_file = MagicMock()
        mock_existing_file.name = "today_image.gif"
        mock_existing_file.suffix = ".gif"
        # Today's date (matched by get_formatted_date mock)
        mock_existing_file.stat.return_value.st_ctime = datetime.datetime(
            2026, 3, 25
        ).timestamp()

        mock_path_obj.iterdir.return_value = [mock_existing_file]
        mock_path.side_effect = lambda *args: mock_path_obj

        # Result should be the existing file name because hash matches OR date matches
        result = image_file_name(mock_hass, config)
        assert result == "today_image.gif"
