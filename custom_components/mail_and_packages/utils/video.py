"""Video and animated image generation utilities for Mail and Packages."""

import logging
import subprocess  # nosec
from pathlib import Path
from shutil import which

from PIL import Image, ImageOps

_LOGGER = logging.getLogger(__name__)


async def _check_ffmpeg() -> bool:
    """Check if ffmpeg is installed.

    Returns boolean
    """
    return which("ffmpeg")


def _generate_mp4(path: str, image_file: str) -> None:
    """Generate mp4 from gif.

    use a subprocess so we don't lock up the thread
    command: ffmpeg -f gif -i infile.gif outfile.mp4
    """
    base_path = Path(path)
    gif_image = base_path / image_file
    mp4_file = base_path / image_file.replace(".gif", ".mp4")

    filecheck = mp4_file.is_file()

    _LOGGER.debug("Generating mp4: %s", mp4_file)
    if filecheck:
        try:
            mp4_file.unlink()
            _LOGGER.debug("Removing old mp4: %s", mp4_file)
        except OSError as err:
            _LOGGER.error("Error removing old mp4 %s: %s", mp4_file, err)

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(gif_image),
            "-pix_fmt",
            "yuv420p",
            str(mp4_file),
        ]
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        _LOGGER.error("FFmpeg failed to generate MP4: %s", err)


def generate_grid_img(path: str, image_file: str, count: int) -> None:
    """Generate png grid from gif.

    use a subprocess so we don't lock up the thread
    command: ffmpeg -f gif -i infile.gif outfile.mp4
    """
    count = max(count, 1)
    if count % 2 == 0:
        length = int(count / 2)
    else:
        length = int(count / 2) + count % 2

    gif_image = Path(path) / image_file
    png_file = image_file.replace(".gif", "_grid.png")
    png_image = Path(path) / png_file

    filecheck = png_image.is_file()

    _LOGGER.debug("Generating png image grid %s from %s", png_image, gif_image)
    if filecheck:
        try:
            png_image.unlink()
            _LOGGER.debug("Removing old png grid: %s", png_image)
        except OSError as err:
            _LOGGER.error("Error removing old png grid %s: %s", png_image, err)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(gif_image),
                "-r",
                "0.20",
                "-filter_complex",
                f"tile=2x{length}:padding=10:color=black",
                str(png_image),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        _LOGGER.error("FFmpeg failed to generate grid image: %s", err)


def generate_delivery_gif(
    delivery_images: list,
    gif_path: str,
    duration: int = 3000,
) -> bool:
    """Generate an animated GIF from delivery images.

    Args:
        delivery_images: List of image file paths
        gif_path: Path where the GIF should be saved
        duration: Duration for each frame in milliseconds (default: 3000)

    Returns:
        bool: True if GIF was created successfully, False otherwise

    """
    try:
        # Open all images
        corrected_images = []
        for img_path in delivery_images:
            img = Image.open(img_path)
            img = ImageOps.exif_transpose(img)  # auto-rotates according to EXIF
            corrected_images.append(img)

        # Create animated GIF
        corrected_images[0].save(
            gif_path,
            format="GIF",
            append_images=corrected_images[1:],
            save_all=True,
            duration=duration,
            loop=0,  # Infinite loop
        )

        _LOGGER.debug(
            "Generated animated GIF with %d delivery images at %s",
            len(delivery_images),
            gif_path,
        )

    except (OSError, ValueError, Image.UnidentifiedImageError) as e:
        _LOGGER.error("Error creating animated GIF: %s", e)
        return False
    else:
        return True
