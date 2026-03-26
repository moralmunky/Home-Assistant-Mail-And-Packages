"""USPS Shipper class."""

from __future__ import annotations

import base64
import email
import logging
import re
import shutil
from pathlib import Path
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

    @classmethod
    def handles_sensor(cls, sensor_type: str) -> bool:
        """Return True if this shipper handles the given sensor type."""
        return sensor_type == "usps_mail"

    async def process(
        self, account: IMAP4_SSL, date: str, sensor_type: str
    ) -> dict[str, Any]:
        """Process USPS Informed Delivery emails."""
        config = self._get_usps_config()
        image_count = 0
        images = []
        images_delete = []

        (server_response, data) = await self._search_informed_delivery(account)

        # Bail out on error
        if server_response != "OK" or data[0] is None:
            return {ATTR_COUNT: image_count}

        # Setup image directory and overlays
        if not await self._setup_image_directory(config["image_output_path"]):
            return {ATTR_COUNT: image_count}

        all_msg_content = ""
        if server_response == "OK":
            _LOGGER.debug("Informed Delivery email found processing...")
            for num in data[0].split():
                (image_count, images, email_content) = await self._process_usps_email(
                    account, num, config["image_output_path"], image_count, images
                )
                all_msg_content += email_content

        # Process images
        images = await self._process_usps_images(all_msg_content, images)
        image_count = len(images)

        if image_count > 0:
            await self._generate_mail_image(
                images,
                config["image_output_path"],
                config["image_name"],
                config["gif_duration"],
                images_delete,
            )
        elif image_count == 0:
            await self._copy_nomail_image(
                config["image_output_path"], config["image_name"], config["custom_img"]
            )

        if config["gen_mp4"]:
            await self._generate_mp4_video(
                config["image_output_path"], config["image_name"]
            )
        if config["gen_grid"]:
            await self._generate_grid_image(
                config["image_output_path"], config["image_name"], image_count
            )

        return {ATTR_COUNT: image_count}

    async def _generate_mp4_video(self, path: str, name: str):
        """Generate MP4 video from images."""
        await self.hass.async_add_executor_job(_generate_mp4, path, name)

    async def _generate_grid_image(self, path: str, name: str, count: int):
        """Generate grid image from images."""
        await self.hass.async_add_executor_job(generate_grid_img, path, name, count)

    async def _process_usps_images(self, content: str, images: list) -> list:
        """Process USPS images (placeholder and filtering)."""
        # Placeholder images
        if re.compile(r"\bimage-no-mailpieces?700\.jpg\b").search(content) is not None:
            placeholder = Path(__file__).parent.parent / "image-no-mailpieces700.jpg"
            if placeholder.exists():
                images.append(str(placeholder))
                _LOGGER.debug(
                    "Placeholder image found using: image-no-mailpieces700.jpg."
                )

        # Announcement images removal
        return self._remove_announcement_images(images)

    def _remove_announcement_images(self, images: list) -> list:
        """Remove announcement images."""
        return [
            el
            for el in images
            if not any(
                ignore in el
                for ignore in ["mailerProvidedImage", "ra_0", "Mail Attachment.txt"]
            )
        ]

    async def _generate_mail_image(
        self, images: list, path: str, name: str, duration: int, delete_list: list
    ):
        """Generate animated GIF from mail images."""
        _LOGGER.debug("Resizing images to 724x320...")
        all_images = await self.hass.async_add_executor_job(
            resize_images, images, 724, 320
        )
        delete_list.extend(all_images)

        try:
            _LOGGER.debug("Generating animated GIF")
            gif_path = str(Path(path) / name)
            await self.hass.async_add_executor_job(
                generate_delivery_gif, all_images, gif_path, duration * 1000
            )
            _LOGGER.debug("Mail image generated.")
        except (OSError, ValueError) as err:
            _LOGGER.error("Error attempting to generate image: %s", err)

        for image in delete_list:
            await self.hass.async_add_executor_job(
                cleanup_images, f"{Path(image).parent}/", Path(image).name
            )

    async def _copy_nomail_image(self, path: str, name: str, custom_img: str | None):
        """Copy the 'no mail' placeholder image."""

        def _prepare():
            if not Path(path).exists():
                Path(path).mkdir(parents=True, exist_ok=True)
            target = Path(path) / name
            if target.is_file():
                cleanup_images(path, name)
            src = custom_img or str(Path(__file__).parent.parent / "mail_none.gif")
            shutil.copyfile(src, str(target))

        _LOGGER.debug("No mail found.")
        try:
            await self.hass.async_add_executor_job(_prepare)
        except OSError as err:
            _LOGGER.error("Error attempting to copy image: %s", err)

    def _get_usps_config(self) -> dict:
        """Get USPS specific configuration."""
        return {
            "image_output_path": self.config.get("image_path"),
            "gif_duration": self.config.get(CONF_DURATION),
            "image_name": self.config.get("image_name"),
            "gen_mp4": self.config.get(CONF_GENERATE_MP4),
            "custom_img": self.config.get(CONF_CUSTOM_IMG_FILE)
            or DEFAULT_CUSTOM_IMG_FILE,
            "gen_grid": self.config.get(CONF_GENERATE_GRID),
        }

    async def _search_informed_delivery(self, account: IMAP4_SSL) -> tuple:
        """Search for USPS Informed Delivery emails."""
        forwarded_emails = self.config.get("forwarded_emails", [])
        _LOGGER.debug("Attempting to find Informed Delivery mail")
        _LOGGER.debug("Informed delivery search date: %s", get_formatted_date())

        if forwarded_emails:
            email_addresses = forwarded_emails + SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL]
        else:
            email_addresses = SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL]

        return await email_search(
            account,
            email_addresses,
            get_formatted_date(),
            SENSOR_DATA[ATTR_USPS_MAIL][ATTR_SUBJECT][0],
        )

    async def _setup_image_directory(self, path: str) -> bool:
        """Ensure image directory exists and is prepared."""
        if not await anyio.Path(path).is_dir():
            try:
                await anyio.Path(path).mkdir(parents=True, exist_ok=True)
            except OSError as err:
                _LOGGER.error("Error creating directory: %s", err)
                return False

        # Clean up and setup overlays
        await self.hass.async_add_executor_job(cleanup_images, path)
        await self.hass.async_add_executor_job(copy_overlays, path)
        return True

    async def _process_usps_email(
        self,
        account: IMAP4_SSL,
        num: str,
        image_output_path: str,
        image_count: int,
        images: list,
    ) -> tuple[int, list, str]:
        """Process a single USPS Informed Delivery email."""
        msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
        _LOGGER.debug("Processing email number: %s", num)
        all_content = ""
        for response_part in msg_parts:
            if isinstance(response_part, (bytes, bytearray)):
                all_content += str(response_part, "utf-8", errors="ignore")
                msg = email.message_from_bytes(response_part)
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        (image_count, images) = await self._extract_usps_images(
                            part, image_output_path, image_count, images
                        )
                    elif part.get_content_type() == "image/jpeg":
                        (image_count, images) = await self._extract_jpeg_attachment(
                            part, image_output_path, image_count, images
                        )
        return image_count, images, all_content

    async def _extract_usps_images(
        self,
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

        if "data:image/jpeg;base64" not in content:
            return image_count, images

        soup = BeautifulSoup(content, "html.parser")
        found_images = soup.find_all(id="mailpiece-image-src-id")

        for image in found_images:
            filename = random_filename()
            img_data = str(image["src"]).split(",")[1]
            try:
                target_path = Path(image_output_path) / filename
                await self.hass.async_add_executor_job(
                    io_save_file, target_path, base64.b64decode(img_data)
                )
                images.append(str(target_path))
                image_count += 1
            except (OSError, ValueError, TypeError) as err:
                _LOGGER.error("Error extracting image: %s", err)

        return image_count, images

    async def _extract_jpeg_attachment(
        self,
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
            await self.hass.async_add_executor_job(
                io_save_file,
                target_path,
                part.get_payload(decode=True),
            )
            images.append(str(target_path))
            image_count += 1
        except OSError as err:
            _LOGGER.critical("Error opening filepath: %s", err)

        return image_count, images
