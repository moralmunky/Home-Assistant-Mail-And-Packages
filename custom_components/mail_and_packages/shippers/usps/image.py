"""USPS image extraction utilities."""

from __future__ import annotations

import base64
import email
import logging
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from custom_components.mail_and_packages.const import ASSET_ROOT
from custom_components.mail_and_packages.utils.image import (
    io_save_file,
    random_filename,
)

_LOGGER = logging.getLogger(__name__)


async def extract_usps_images(
    hass: Any,
    part: email.message.Message,
    image_output_path: str,
    image_count: int,
    images: list,
) -> tuple[int, list]:
    """Extract images from an email part (HTML/Base64)."""
    payload = part.get_payload(decode=True)
    content = (
        payload.decode("utf-8", "ignore")
        if isinstance(payload, (bytes, bytearray))
        else str(payload)
    )

    # New USPS format: unscanned mailpieces use a div with a specific id.
    # Check here on properly decoded HTML — raw RFC822 content is
    # quoted-printable encoded and soft line breaks could split the string.
    if "mailpiece-with-no-image-id" in content:
        placeholder = ASSET_ROOT / "image-no-mailpieces700.jpg"
        placeholder_str = str(placeholder)
        if placeholder.exists() and placeholder_str not in images:
            images.append(placeholder_str)
            image_count += 1
            _LOGGER.debug(
                "Placeholder image found using: image-no-mailpieces700.jpg.",
            )

    if "data:image/jpeg;base64" not in content:
        return image_count, images

    soup = BeautifulSoup(content, "html.parser")
    found_images = soup.find_all(id="mailpiece-image-src-id")

    for image in found_images:
        filename = random_filename()
        img_data = str(image["src"]).split(",")[1]
        try:
            target_path = Path(image_output_path) / filename
            await hass.async_add_executor_job(
                io_save_file,
                target_path,
                base64.b64decode(img_data),
            )
            images.append(str(target_path))
            image_count += 1
        except (OSError, ValueError, TypeError) as err:
            _LOGGER.error("Error extracting image: %s", err)

    return image_count, images


async def extract_jpeg_attachment(
    hass: Any,
    part: email.message.Message,
    image_output_path: str,
    image_count: int,
    images: list,
) -> tuple[int, list]:
    """Extract image from JPEG attachment."""
    _LOGGER.debug("Extracting image from email attachment")
    filename = part.get_filename()
    junkmail = ["mailer", "content", "package"]
    if filename is None:
        return image_count, images
    if any(junk in filename for junk in junkmail):
        return image_count, images

    try:
        target_path = Path(image_output_path) / filename
        await hass.async_add_executor_job(
            io_save_file,
            target_path,
            part.get_payload(decode=True),
        )
        images.append(str(target_path))
        image_count += 1
    except OSError as err:
        _LOGGER.critical("Error opening filepath: %s", err)

    return image_count, images
