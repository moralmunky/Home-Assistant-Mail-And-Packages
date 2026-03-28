"""Image processing and management utilities for Mail and Packages."""

import datetime
import hashlib
import logging
import os
import subprocess  # nosec
import uuid
from pathlib import Path
from shutil import copyfile, which

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from PIL import Image, ImageOps

from custom_components.mail_and_packages.const import (
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
    OVERLAY,
)

from .date import get_formatted_date

_LOGGER = logging.getLogger(__name__)


async def _check_ffmpeg() -> bool:
    """Check if ffmpeg is installed.

    Returns boolean
    """
    return which("ffmpeg")


def default_image_path(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
) -> str:
    """Return value of the default image path.

    Returns the default path based on logic
    """
    storage = None
    try:
        storage = config_entry.get(CONF_STORAGE)
    except AttributeError:
        storage = config_entry.data[CONF_STORAGE]

    if storage:
        return storage
    return "custom_components/mail_and_packages/images/"


def hash_file(filename: str) -> str:
    """Return the SHA-1 hash of the file passed into it.

    Returns hash of file as string
    """
    # make a hash object
    the_hash = hashlib.sha1()  # nosec

    # open file for reading in binary mode
    with Path(filename).open("rb") as file:
        # loop till the end of the file
        chunk = 0
        while chunk != b"":
            # read only 1024 bytes at a time
            chunk = file.read(1024)
            the_hash.update(chunk)

    # return the hex representation of digest
    return the_hash.hexdigest()


def _delete_file(file_path: Path, context: str) -> bool:
    """Delete a single file with error handling."""
    try:
        if file_path.exists():
            file_path.unlink()
            _LOGGER.debug("%s - Successfully removed: %s", context, file_path)
            return True
        _LOGGER.debug("%s - File does not exist: %s", context, file_path)
    except OSError as err:
        _LOGGER.error("Error attempting to remove image in %s: %s", context, err)
    return False


def _cleanup_directory(path: str) -> None:
    """Handle directory-wide cleanup."""
    if not Path(path).is_dir():
        _LOGGER.debug("cleanup_images - Directory does not exist: %s", path)
        return

    try:
        files_before = [x.name for x in Path(path).iterdir()]
        _LOGGER.debug(
            "cleanup_images - Files in directory BEFORE cleanup: %s",
            files_before,
        )
        for file in files_before:
            if file.endswith((".gif", ".mp4", ".jpg", ".png")):
                full_path = Path(path) / file
                _delete_file(full_path, "cleanup_images")

        files_after = []
        if Path(path).is_dir():
            files_after = [f.name for f in Path(path).iterdir()]

        _LOGGER.debug(
            "cleanup_images - Files in directory AFTER cleanup: %s",
            files_after,
        )
    except FileNotFoundError:
        _LOGGER.debug("cleanup_images - Directory removed during cleanup: %s", path)
    except OSError as err:
        _LOGGER.error("Error listing directory for cleanup: %s", err)


def cleanup_images(path: str, image: str | None = None) -> None:
    """Clean up image storage directory.

    Only suppose to delete .gif, .mp4, and .jpg files
    """
    _LOGGER.debug("=== cleanup_images CALLED === path: %s, image: %s", path, image)

    if isinstance(path, tuple):
        path, image = path

    if image is not None:
        full_path = Path(path) / image
        _delete_file(full_path, "cleanup_images")
        return

    _cleanup_directory(path)


def copy_overlays(path: str) -> None:
    """Copy overlay images to image output path."""
    overlays = OVERLAY
    check = all(item.name in overlays for item in Path(path).iterdir())

    # Copy files if they are missing
    if not check:
        for file in overlays:
            _LOGGER.debug("Copying file to: %s", path + file)
            copyfile(
                Path(__file__).parent.parent / file,
                path + file,
            )


def resize_images(images: list, width: int, height: int) -> list:
    """Resize images."""
    all_images = []
    for image_path in images:
        try:
            img_path = Path(image_path)
            with img_path.open("rb") as fd_img:
                img = Image.open(fd_img)
                img.thumbnail((width, height), resample=Image.Resampling.LANCZOS)
                img = ImageOps.pad(
                    img,
                    (width, height),
                    method=Image.Resampling.LANCZOS,
                )
                img = img.crop((0, 0, width, height))
                new_image_path = img_path.parent / f"{img_path.stem}_resized.gif"
                img.save(new_image_path, "GIF")
                all_images.append(str(new_image_path))

        except (OSError, ValueError) as err:
            _LOGGER.error("Error processing image %s: %s", image_path, err)
            continue

    return all_images


def random_filename(ext: str = ".jpg") -> str:
    """Generate random filename."""
    return f"{uuid.uuid4()!s}{ext}"


def io_save_file(path: str | Path, data: bytes) -> None:
    """Write bytes to a file synchronously (for use in executor)."""
    with Path(path).open("wb") as the_file:
        the_file.write(data)


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
        # Construct path string with trailing slash to ensure cleanup_images concatenates correctly
        cleanup_images(str(mp4_file.parent) + "/", mp4_file.name)
        _LOGGER.debug("Removing old mp4: %s", mp4_file)

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

    gif_image = Path(path + image_file)
    png_file = image_file.replace(".gif", "_grid.png")
    png_image = Path(path).joinpath(png_file)

    filecheck = png_image.is_file()

    _LOGGER.debug("Generating png image grid %s from %s", png_image, gif_image)
    if filecheck:
        # cleanup_images expects a tuple or string path, so we use string parts here
        # or we could update cleanup_images to handle Path objects natively later.
        cleanup_images(str(png_image.parent) + "/", png_image.name)
        _LOGGER.debug("Removing old png grid: %s", png_image)

    # TODO: find a way to call ffmpeg the right way from HA
    subprocess.call(
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
    )


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


def _get_courier_info(
    hass: HomeAssistant,
    config: ConfigEntry,
    amazon: bool,
    ups: bool,
    walmart: bool,
    fedex: bool,
) -> tuple[str, str]:
    """Determine the path and default image for the active courier."""
    configs = [
        (
            amazon,
            CONF_AMAZON_CUSTOM_IMG,
            CONF_AMAZON_CUSTOM_IMG_FILE,
            DEFAULT_AMAZON_CUSTOM_IMG_FILE,
            "no_deliveries_amazon.jpg",
            "amazon",
        ),
        (
            ups,
            CONF_UPS_CUSTOM_IMG,
            CONF_UPS_CUSTOM_IMG_FILE,
            DEFAULT_UPS_CUSTOM_IMG_FILE,
            "no_deliveries_ups.jpg",
            "ups",
        ),
        (
            walmart,
            CONF_WALMART_CUSTOM_IMG,
            CONF_WALMART_CUSTOM_IMG_FILE,
            DEFAULT_WALMART_CUSTOM_IMG_FILE,
            "no_deliveries_walmart.jpg",
            "walmart",
        ),
        (
            fedex,
            CONF_FEDEX_CUSTOM_IMG,
            CONF_FEDEX_CUSTOM_IMG_FILE,
            DEFAULT_FEDEX_CUSTOM_IMG_FILE,
            "no_deliveries_fedex.jpg",
            "fedex",
        ),
    ]

    base_path = f"{hass.config.path()}/{default_image_path(hass, config)}"

    for (
        active,
        img_conf,
        file_conf,
        default_file_conf,
        local_default,
        sub_dir,
    ) in configs:
        if active:
            _LOGGER.debug("Processing %s image file name", sub_dir.title())
            if config.get(img_conf):
                mail_none = config.get(file_conf) or default_file_conf
                _LOGGER.debug("Using custom %s image: %s", sub_dir.title(), mail_none)
            else:
                mail_none = str(Path(__file__).parent.parent / local_default)
                _LOGGER.debug("Using default %s image: %s", sub_dir.title(), mail_none)
            return f"{base_path}{sub_dir}", mail_none

    # Standard mail case
    path = base_path.rstrip("/")
    if config.get(CONF_CUSTOM_IMG):
        mail_none = config.get(CONF_CUSTOM_IMG_FILE) or DEFAULT_CUSTOM_IMG_FILE
    else:
        mail_none = str(Path(__file__).parent.parent / "mail_none.gif")
    return path, mail_none


def _get_image_name_from_directory(
    path: str, mail_none: str, sha1: str, ext: str
) -> str:
    """Check existing images and return a filename."""
    image_name = os.path.split(mail_none)[1]
    today = get_formatted_date()

    try:
        for file_path in Path(path).iterdir():
            if not file_path.is_file():
                continue
            filename = file_path.name
            if filename == "generic_deliveries.gif":
                continue
            is_image_file = filename.endswith(".gif") or (
                filename.endswith(".jpg") and ext == ".jpg"
            )
            if is_image_file:
                try:
                    created = datetime.datetime.fromtimestamp(
                        file_path.stat().st_ctime,
                    ).strftime("%d-%b-%Y")
                    # If it's the correct hash OR created today, we can reuse it
                    if sha1 == hash_file(str(file_path)) or today == created:
                        image_name = filename
                        break
                    image_name = f"{uuid.uuid4()!s}{ext}"
                except OSError as err:
                    _LOGGER.error("Problem accessing file %s: %s", filename, err)
    except OSError as err:
        _LOGGER.error("Error accessing directory %s: %s", path, err)

    if image_name in mail_none:
        image_name = f"{uuid.uuid4()!s}{ext}"
        _LOGGER.debug("=== image_file_name GENERATED NEW UUID: %s ===", image_name)
    else:
        _LOGGER.debug("=== image_file_name USING EXISTING: %s ===", image_name)

    return image_name


def image_file_name(
    hass: HomeAssistant,
    config: ConfigEntry,
    amazon: bool = False,
    ups: bool = False,
    walmart: bool = False,
    fedex: bool = False,
) -> str:
    """Determine if filename is to be changed or not.

    Returns filename
    """
    _LOGGER.debug(
        "=== image_file_name CALLED === - amazon: %s, ups: %s, walmart: %s, fedex: %s",
        amazon,
        ups,
        walmart,
        fedex,
    )

    path, mail_none = _get_courier_info(hass, config, amazon, ups, walmart, fedex)
    image_name = os.path.split(mail_none)[1]

    # Path check
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except OSError as err:
        _LOGGER.error("Error creating directory: %s", err)
        return image_name

    # SHA1 file hash check
    try:
        sha1 = hash_file(mail_none)
    except OSError as err:
        _LOGGER.error("Problem accessing file: %s, error returned: %s", mail_none, err)
        return image_name

    ext = ".jpg" if ups or walmart or fedex else ".gif"
    return _get_image_name_from_directory(path, mail_none, sha1, ext)
