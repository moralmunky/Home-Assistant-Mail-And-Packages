"""Image processing and management utilities for Mail and Packages."""

import contextlib
import datetime
import hashlib
import logging
import os
import uuid
from pathlib import Path
from shutil import copyfile

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
    GENERIC_DELIVERIES_GIF,
    OVERLAY,
)

from .date import get_formatted_date
from .video import (
    _check_ffmpeg,
    _generate_mp4,
    generate_delivery_gif,
    generate_grid_img,
)

__all__ = [
    "_check_ffmpeg",
    "_generate_mp4",
    "generate_delivery_gif",
    "generate_grid_img",
]

_LOGGER = logging.getLogger(__name__)


def default_image_path(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
) -> str:
    """Return value of the default image path.

    Returns the default path based on logic
    """
    storage = None
    try:
        storage = config_entry.options.get(CONF_STORAGE) or config_entry.data.get(
            CONF_STORAGE
        )
    except AttributeError:
        with contextlib.suppress(AttributeError):
            storage = config_entry.get(CONF_STORAGE)

    if storage:
        return storage.rstrip("/") + "/"
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
            # The generic delivery camera owns this file and only rebuilds it
            # when its source images change, so a shipper's directory-wide
            # sweep of the shared image directory must not delete it.
            if file == GENERIC_DELIVERIES_GIF:
                continue
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
    try:
        check = all(item.name in overlays for item in Path(path).iterdir())
    except OSError:
        check = False

    # Copy files if they are missing
    if not check:
        for file in overlays:
            dest_file = Path(path) / file
            _LOGGER.debug("Copying file to: %s", dest_file)
            try:
                copyfile(
                    Path(__file__).parent.parent / file,
                    str(dest_file),
                )
            except OSError as err:
                _LOGGER.error("Error copying overlay %s: %s", file, err)


def resize_images(images: list, width: int, height: int) -> list:
    """Resize images."""
    all_images = []
    for image_path in images:
        try:
            img_path = Path(image_path)
            with img_path.open("rb") as fd_img:
                img = Image.open(fd_img)
                # Bake in the EXIF orientation before anything else. Delivery
                # photos come straight off a courier's handheld and are very
                # often stored rotated with an Orientation tag, and the frames
                # written below are GIF, which cannot carry EXIF at all — so
                # this is the last point at which the tag still exists. Doing
                # it any later (generate_delivery_gif also calls
                # exif_transpose) is a no-op on frames whose EXIF is gone.
                img = ImageOps.exif_transpose(img)
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

    base_path = Path(hass.config.path(default_image_path(hass, config)))

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
            return str(base_path / sub_dir), mail_none

    # Standard mail case
    path = str(base_path)
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
            if filename == GENERIC_DELIVERIES_GIF:
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
