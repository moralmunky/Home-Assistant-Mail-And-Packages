"""USPS Shipper class."""
from __future__ import annotations

import base64
import email
import logging
import re
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio
from aioimaplib import IMAP4_SSL
from bs4 import BeautifulSoup

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_EMAIL,
    ATTR_SUBJECT,
    ATTR_USPS_MAIL,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_GENERATE_GRID,
    CONF_GENERATE_MP4,
    DEFAULT_CUSTOM_IMG_FILE,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.utils.date import get_formatted_date
from custom_components.mail_and_packages.utils.image import (
    _generate_mp4,
    cleanup_images,
    copy_overlays,
    generate_delivery_gif,
    generate_grid_img,
    io_save_file,
    random_filename,
    resize_images,
)
from custom_components.mail_and_packages.utils.imap import email_fetch, email_search

from .base import Shipper

_LOGGER = logging.getLogger(__name__)


class USPSShipper(Shipper):
    """USPS Informed Delivery shipper."""

    @property
    def name(self) -> str:
        """Return shipper name."""
        return "usps"

    async def process(
        self, account: IMAP4_SSL, date: str, sensor_type: str
    ) -> dict[str, Any]:
        """Process USPS Informed Delivery emails."""
        # Note: image_path and other configs should be extracted from self.config
        # For now, we'll keep the logic similar to get_mails but adapted to the class
        image_output_path = self.config.get("image_path")
        gif_duration = self.config.get(CONF_DURATION)
        image_name = self.config.get("image_name")
        gen_mp4 = self.config.get(CONF_GENERATE_MP4)
        custom_img = self.config.get(CONF_CUSTOM_IMG_FILE) or DEFAULT_CUSTOM_IMG_FILE
        gen_grid = self.config.get(CONF_GENERATE_GRID)
        forwarded_emails = self.config.get("forwarded_emails", [])

        image_count = 0
        images = []
        images_delete = []

        _LOGGER.debug("Attempting to find Informed Delivery mail")
        _LOGGER.debug("Informed delivery search date: %s", get_formatted_date())

        if forwarded_emails:
            email_addresses = forwarded_emails + SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL]
        else:
            email_addresses = SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL]

        (server_response, data) = await email_search(
            account,
            email_addresses,
            get_formatted_date(),
            SENSOR_DATA[ATTR_USPS_MAIL][ATTR_SUBJECT][0],
        )

        # Bail out on error
        if server_response != "OK" or data[0] is None:
            return {ATTR_COUNT: image_count}

        # Check to see if the path exists, if not make it
        if not await anyio.Path(image_output_path).is_dir():
            try:
                await anyio.Path(image_output_path).mkdir(parents=True, exist_ok=True)
            except OSError as err:
                _LOGGER.error("Error creating directory: %s", err)
                return {ATTR_COUNT: image_count}

        # Clean up image directory
        _LOGGER.debug("Cleaning up image directory: %s", image_output_path)
        await self.hass.async_add_executor_job(cleanup_images, image_output_path)

        # Copy overlays to image directory
        _LOGGER.debug("Checking for overlay files in: %s", image_output_path)
        await self.hass.async_add_executor_job(copy_overlays, image_output_path)

        if server_response == "OK":
            _LOGGER.debug("Informed Delivery email found processing...")
            for num in data[0].split():
                msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
                _LOGGER.debug("Processing email number: %s", num)
                for response_part in msg_parts:
                    if isinstance(response_part, (bytes, bytearray)):
                        msg = email.message_from_bytes(response_part)
                        _LOGGER.debug("Email parsed successfully.")
                        for part in msg.walk():
                            if part.get_content_type() == "text/html":
                                _LOGGER.debug("Found html email processing...")
                                payload = part.get_payload(decode=True)
                                if isinstance(payload, (bytes, bytearray)):
                                    try:
                                        content = payload.decode("utf-8", "ignore")
                                    except ValueError:
                                        content = str(payload)
                                else:
                                    content = str(payload)
                                soup = BeautifulSoup(content, "html.parser")
                                found_images = soup.find_all(id="mailpiece-image-src-id")
                                if not found_images:
                                    continue
                                if "data:image/jpeg;base64" not in content:
                                    _LOGGER.debug("Unexpected html format found.")
                                    continue

                                for image in found_images:
                                    filename = random_filename()
                                    img_data = str(image["src"]).split(",")[1]
                                    try:
                                        target_path = Path(image_output_path) / filename
                                        await self.hass.async_add_executor_job(
                                            io_save_file,
                                            target_path,
                                            base64.b64decode(img_data),
                                        )
                                        images.append(str(target_path))
                                        image_count += 1
                                    except (OSError, ValueError) as err:
                                        _LOGGER.critical("Error opening filepath: %s", err)
                                        return {ATTR_COUNT: image_count}

                            elif part.get_content_type() == "image/jpeg":
                                _LOGGER.debug("Extracting image from email")
                                filename = part.get_filename()
                                junkmail = ["mailer", "content", "package"]
                                if filename is None:
                                    continue
                                if any(junk in filename for junk in junkmail):
                                    continue
                                try:
                                    target_path = Path(image_output_path) / filename
                                    await self.hass.async_add_executor_job(
                                        io_save_file,
                                        target_path,
                                        part.get_payload(decode=True),
                                    )
                                    images.append(str(target_path))
                                    image_count += 1
                                except OSError as err:
                                    _LOGGER.critical("Error opening filepath: %s", err)
                                    return {ATTR_COUNT: image_count}

            # Remove duplicate images
            images = list(dict.fromkeys(images))
            images_delete = images[:]

            # Placeholder images
            # Check the last fetched message for the placeholder text
            if re.compile(r"\bimage-no-mailpieces?700\.jpg\b").search(str(msg_parts)) is not None:
                placeholder = Path(__file__).parent.parent / "image-no-mailpieces700.jpg"
                if placeholder.exists():
                    images.append(str(placeholder))
                    image_count += 1
                    _LOGGER.debug("Placeholder image found using: image-no-mailpieces700.jpg.")

            # Announcement images removal
            images = [
                el
                for el in images
                if not any(
                    ignore in el
                    for ignore in ["mailerProvidedImage", "ra_0", "Mail Attachment.txt"]
                )
            ]
            image_count = len(images)

            if image_count > 0:
                _LOGGER.debug("Resizing images to 724x320...")
                all_images = await self.hass.async_add_executor_job(
                    resize_images, images, 724, 320
                )
                for image in all_images:
                    images_delete.append(image)

                try:
                    _LOGGER.debug("Generating animated GIF")
                    gif_path = str(Path(image_output_path) / image_name)
                    await self.hass.async_add_executor_job(
                        generate_delivery_gif, all_images, gif_path, gif_duration * 1000
                    )
                    _LOGGER.debug("Mail image generated.")
                except (OSError, ValueError) as err:
                    _LOGGER.error("Error attempting to generate image: %s", err)

                for image in images_delete:
                    await self.hass.async_add_executor_job(
                        cleanup_images,
                        f"{Path(image).parent}/",
                        Path(image).name,
                    )

            elif image_count == 0:
                if not Path(image_output_path).exists():
                    Path(image_output_path).mkdir(parents=True, exist_ok=True)
                _LOGGER.debug("No mail found.")
                target_file = Path(image_output_path) / image_name
                if target_file.is_file():
                    await self.hass.async_add_executor_job(
                        cleanup_images, image_output_path, image_name
                    )

                try:
                    _LOGGER.debug("Copying nomail gif")
                    if custom_img is not None:
                        nomail = custom_img
                    else:
                        nomail = str(Path(__file__).parent.parent / "mail_none.gif")

                    await self.hass.async_add_executor_job(
                        copyfile, nomail, str(target_file)
                    )
                except OSError as err:
                    _LOGGER.error("Error attempting to copy image: %s", err)

            if gen_mp4:
                await self.hass.async_add_executor_job(
                    _generate_mp4, image_output_path, image_name
                )
            if gen_grid:
                await self.hass.async_add_executor_job(
                    generate_grid_img, image_output_path, image_name, image_count
                )

        return {ATTR_COUNT: image_count}
