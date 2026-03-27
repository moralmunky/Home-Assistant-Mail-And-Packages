"""Tests for image utilities."""

import datetime
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from custom_components.mail_and_packages.utils.image import (
    _check_ffmpeg,
    _generate_mp4,
    _get_image_name_from_directory,
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
        mock_path_obj.__truediv__.return_value = mock_path_obj

        cleanup_images("/fake/path/")
        assert "Error attempting to remove image in cleanup_images" in caplog.text


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
        "custom_components.mail_and_packages.utils.image.Image.open",
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


@pytest.mark.asyncio
async def test_generate_delivery_gif_coverage(caplog):
    """Test generate_delivery_gif success and handling."""
    caplog.set_level("ERROR")
    with (
        patch(
            "custom_components.mail_and_packages.utils.image.Image.open",
        ) as mock_open,
        patch(
            "custom_components.mail_and_packages.utils.image.ImageOps.exif_transpose",
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
        mock_hass,
        mock_config,
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
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.return_value = []
        mock_path.side_effect = lambda *args: mock_path_obj

        result = image_file_name(mock_hass, config, amazon=True)
        assert result.endswith(".gif")


def test_generate_mp4_exists():
    """Test _generate_mp4 when old mp4 exists."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.subprocess.run",
        ) as mock_run,
        patch(
            "custom_components.mail_and_packages.utils.image.cleanup_images",
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
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.return_value = []
        mock_path.side_effect = lambda *args: mock_path_obj

        result = image_file_name(mock_hass, config)
        # If no images found, it generates a new UUID.gif if image_name in mail_none
        assert result.endswith(".gif")
        assert len(result) > 20


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
            2026,
            3,
            24,
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
            assert result.endswith(".gif")


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
            b"data",
        )


def test_generate_mp4_success():
    """Test _generate_mp4 success path."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.subprocess.run",
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
            "custom_components.mail_and_packages.utils.image.subprocess.run",
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
            "custom_components.mail_and_packages.utils.image.subprocess.call",
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
            "custom_components.mail_and_packages.utils.image.Image.open",
        ) as mock_open,
        patch(
            "custom_components.mail_and_packages.utils.image.ImageOps.pad",
        ) as mock_pad,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.stem = "test"
        mock_path_obj.suffix = ".jpg"
        mock_path_obj.parent = Path("/fake/path")
        mock_path_obj.open.return_value.__enter__.return_value = MagicMock()
        mock_path.side_effect = lambda *args: mock_path_obj

        mock_img = MagicMock()
        mock_img.format = "JPEG"
        mock_open.return_value = mock_img
        mock_pad.return_value = mock_img

        result = resize_images(["/fake/path/test.jpg"], 100, 100)
        assert len(result) == 1
        assert "_resized.gif" in result[0]


@pytest.mark.asyncio
async def test_resize_images_avoids_overwriting():
    """Test resize_images does not overwrite the original GIF file."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.Image.open",
        ) as mock_open,
        patch(
            "custom_components.mail_and_packages.utils.image.ImageOps.pad",
        ) as mock_pad,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.stem = "original"
        mock_path_obj.suffix = ".gif"
        mock_path_obj.parent = Path("/fake/path")
        mock_path_obj.open.return_value.__enter__.return_value = MagicMock()
        mock_path.side_effect = lambda *args: mock_path_obj

        mock_img = MagicMock()
        mock_img.format = "GIF"
        mock_open.return_value = mock_img
        mock_pad.return_value = mock_img

        result = resize_images(["/fake/path/original.gif"], 100, 100)
        assert len(result) == 1
        assert "original_resized.gif" in result[0]
        # Verify the original path was NOT used as the output path
        assert result[0] != "/fake/path/original.gif"


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
            2026,
            3,
            25,
        ).timestamp()

        mock_path_obj.iterdir.return_value = [mock_existing_file]
        mock_path.side_effect = lambda *args: mock_path_obj

        result = image_file_name(mock_hass, config)
        assert result == "today_image.gif"


@pytest.mark.asyncio
async def test_cleanup_images_recursive_tuple():
    """Test cleanup_images with tuple input."""
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = True
        mock_path.side_effect = lambda *args: mock_path_obj

        mock_path_obj.__truediv__.return_value = mock_path_obj
        cleanup_images(("/path/", "image.jpg"))
        assert mock_path_obj.unlink.called


@pytest.mark.asyncio
async def test_cleanup_images_file_not_exists(caplog):
    """Test cleanup_images when specific file doesn't exist."""
    caplog.set_level("DEBUG")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = False
        mock_path.side_effect = lambda *args: mock_path_obj

        mock_path_obj.__truediv__.return_value = mock_path_obj
        cleanup_images("/path/", "missing.jpg")
        assert "cleanup_images - File does not exist" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_os_error(caplog):
    """Test cleanup_images with OSError."""
    caplog.set_level("ERROR")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.exists.return_value = True
        mock_path_obj.unlink.side_effect = OSError("Disk error")
        mock_path.side_effect = lambda *args: mock_path_obj

        mock_path_obj.__truediv__.return_value = mock_path_obj
        cleanup_images("/path/", "file.jpg")
        assert "Error attempting to remove image in cleanup_images" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_images_iterdir_os_error(caplog):
    """Test cleanup_images with iterdir OSError."""
    caplog.set_level("ERROR")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.is_dir.return_value = True
        mock_path_obj.iterdir.side_effect = OSError("IO Error")
        mock_path.side_effect = lambda *args: mock_path_obj

        cleanup_images("/path/")
        assert "Error listing directory for cleanup" in caplog.text


def test_generate_grid_img_existing(caplog):
    """Test generate_grid_img when old grid exists."""
    caplog.set_level("DEBUG")
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch("custom_components.mail_and_packages.utils.image.subprocess.call"),
        patch(
            "custom_components.mail_and_packages.utils.image.cleanup_images",
        ) as mock_cleanup,
    ):
        mock_path_obj = MagicMock()
        mock_path_obj.is_file.return_value = True
        mock_path_obj.parent = MagicMock()
        mock_path.return_value = mock_path_obj

        generate_grid_img("/path/", "test.gif", 5)
        assert mock_cleanup.called
        assert "Removing old png grid" in caplog.text


@pytest.mark.asyncio
async def test_check_ffmpeg():
    """Test _check_ffmpeg helper."""
    with patch(
        "custom_components.mail_and_packages.utils.image.which",
        return_value="/usr/bin/ffmpeg",
    ):
        assert await _check_ffmpeg() == "/usr/bin/ffmpeg"


@pytest.mark.asyncio
async def test_cleanup_images_file_not_exist_debug(caplog):
    """Test cleanup_images debug log for non-existent file."""
    caplog.set_level("DEBUG")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.is_dir.return_value = True
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_path_obj.iterdir.return_value = [mock_file]
        mock_path_obj.__truediv__.return_value = mock_path_obj
        mock_path_obj.exists.return_value = False
        mock_path.return_value = mock_path_obj

        cleanup_images("/path/")
        assert "cleanup_images - File does not exist" in caplog.text


@pytest.mark.asyncio
async def test_hash_file_os_error():
    """Test hash_file with OSError."""
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.open.side_effect = OSError("Access denied")
        mock_path.return_value = mock_path_obj

        with pytest.raises(OSError):
            hash_file("test.jpg")


@pytest.mark.asyncio
async def test_image_file_name_stat_os_error(caplog):
    """Test image_file_name with stat OSError."""
    mock_hass = MagicMock()
    config = {"custom_img": True, "custom_img_file": "mail_none.gif"}
    caplog.set_level("ERROR")

    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.hash_file",
            return_value="abc",
        ),
    ):
        mock_path_obj = MagicMock()
        mock_file = MagicMock()
        mock_file.name = "today.gif"
        mock_file.stat.side_effect = OSError("Stat error")
        mock_path_obj.iterdir.return_value = [mock_file]
        # mkdir call, iterdir call, etc.
        mock_path.side_effect = lambda *args: mock_path_obj

        result = image_file_name(mock_hass, config)
        assert "Problem accessing file" in caplog.text
        assert result.endswith(".gif")
        assert len(result) > 20


def test_generate_grid_img_even_count():
    """Test generate_grid_img with an even count."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch("custom_components.mail_and_packages.utils.image.subprocess.call"),
    ):
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        generate_grid_img("/path/", "test.gif", 2)


@pytest.mark.asyncio
async def test_get_image_name_from_directory_non_file():
    """Test _get_image_name_from_directory with non-file items."""
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_dir = MagicMock()
        mock_dir.is_file.return_value = False
        mock_path_obj.iterdir.return_value = [mock_dir]
        mock_path.return_value = mock_path_obj

        result = _get_image_name_from_directory(
            "/path/", "mail_none.gif", "sha1", ".gif"
        )
        assert result.endswith(".gif")


@pytest.mark.asyncio
async def test_get_image_name_from_directory_os_error(caplog):
    """Test _get_image_name_from_directory with OSError."""
    caplog.set_level("ERROR")
    with patch("custom_components.mail_and_packages.utils.image.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.iterdir.side_effect = OSError("Access denied")
        mock_path.return_value = mock_path_obj

        result = _get_image_name_from_directory(
            "/path/", "mail_none.gif", "sha1", ".gif"
        )
        assert "Error accessing directory" in caplog.text
        assert result.endswith(".gif")


@pytest.mark.asyncio
async def test_image_file_name_hash_os_error(caplog):
    """Test image_file_name with hash_file OSError."""
    mock_hass = MagicMock()
    config = {"custom_img": True, "custom_img_file": "mail_none.gif"}
    caplog.set_level("ERROR")

    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch(
            "custom_components.mail_and_packages.utils.image.hash_file",
            side_effect=OSError("Hash fail"),
        ),
    ):
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.mkdir.return_value = None

        result = image_file_name(mock_hass, config)
        assert "Problem accessing file" in caplog.text
        assert result == "mail_none.gif"


def test_copy_overlays_force_copy():
    """Test copy_overlays when it needs to copy files."""
    with (
        patch("custom_components.mail_and_packages.utils.image.Path") as mock_path,
        patch("custom_components.mail_and_packages.utils.image.copyfile") as mock_copy,
    ):
        mock_path_obj = MagicMock()
        mock_file = MagicMock()
        mock_file.name = "not_an_overlay.png"
        mock_path_obj.iterdir.return_value = [mock_file]
        mock_path.return_value = mock_path_obj

        copy_overlays("/path/")
        assert mock_copy.called
