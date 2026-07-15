"""Post DE Shipper class."""

from __future__ import annotations

import email
import io
import logging
import shutil
from pathlib import Path
from typing import Any

import anyio
from aioimaplib import IMAP4_SSL
from PIL import Image, UnidentifiedImageError

from custom_components.mail_and_packages.const import (
    ATTR_IMAGE_PATH,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FORWARDING_HEADER,
    CONF_GENERATE_GRID,
    CONF_GENERATE_MP4,
    CONF_POST_DE_CUSTOM_IMG_FILE,
    DEFAULT_CUSTOM_IMG_FILE,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.date import get_formatted_date
from custom_components.mail_and_packages.utils.image import (
    _generate_mp4,
    cleanup_images,
    generate_delivery_gif,
    generate_grid_img,
    random_filename,
    resize_images,
)
from custom_components.mail_and_packages.utils.imap import email_fetch, email_search

from .base import Shipper

_LOGGER = logging.getLogger(__name__)


class PostDEShipper(Shipper):
    """Post DE Briefankündigung shipper."""

    @property
    def name(self) -> str:
        """Return shipper name."""
        return "post_de"

    @classmethod
    def handles_sensor(cls, sensor_type: str) -> bool:
        """Return True if this shipper handles the given sensor type."""
        return sensor_type == "post_de_mail"

    async def process(
        self,
        account: IMAP4_SSL,
        date: str,
        sensor_type: str,
        cache: EmailCache | None = None,
    ) -> dict[str, Any]:
        """Process Post DE Briefankündigung emails."""
        if sensor_type != "post_de_mail":
            return {sensor_type: 0}

        config = self._get_config()
        image_count = 0
        images = []
        images_delete = []

        (server_response, data) = await self._search_emails(account)

        # Bail out on error
        if server_response != "OK" or data[0] is None:
            return {sensor_type: image_count}

        # Setup image directory
        post_de_dir = Path(config["image_output_path"]) / "post_de"
        if not await self._setup_image_directory(str(post_de_dir)):
            return {sensor_type: image_count}

        _LOGGER.debug("Post DE Briefankündigung email found processing...")
        for num in data[0].split():
            (image_count, images) = await self._process_post_de_email(
                account,
                num,
                str(post_de_dir),
                image_count,
                images,
                cache,
            )

        image_count = len(images)

        if image_count > 0:
            await self._generate_mail_image(
                images,
                str(post_de_dir),
                config["image_name"],
                config["gif_duration"],
                images_delete,
            )
        elif image_count == 0:
            await self._copy_nomail_image(
                str(post_de_dir),
                config["image_name"],
                config["custom_img"],
            )

        if config["gen_mp4"]:
            await self._generate_mp4_video(
                str(post_de_dir),
                config["image_name"],
            )
        if config["gen_grid"]:
            await self._generate_grid_image(
                str(post_de_dir),
                config["image_name"],
                image_count,
            )

        return {
            sensor_type: image_count,
            "post_de_image": config["image_name"],
            ATTR_IMAGE_PATH: config["image_output_path"],
            "post_de_grid_image_name": config["image_name"].replace(
                ".gif", "_grid.png"
            ),
        }

    async def process_batch(
        self,
        account: IMAP4_SSL,
        date: str,
        sensors: list[str],
        cache: EmailCache,
        since_date: str | None = None,
    ) -> dict[str, Any]:
        """Process multiple Post DE sensors in batch."""
        res = {}
        for sensor in sensors:
            res.update(await self.process(account, date, sensor, cache))

            # Replicate coordinator dict structure
            if sensor not in res:
                res[sensor] = res.get(sensor, 0)

        return res

    async def _generate_mp4_video(self, path: str, name: str):
        """Generate MP4 video from images."""
        await self.hass.async_add_executor_job(_generate_mp4, path + "/", name)

    async def _generate_grid_image(self, path: str, name: str, count: int):
        """Generate grid image from images."""
        await self.hass.async_add_executor_job(
            generate_grid_img, path + "/", name, count
        )

    async def _generate_mail_image(
        self,
        images: list,
        path: str,
        name: str,
        duration: int,
        delete_list: list,
    ):
        """Generate animated GIF from mail images."""
        try:
            _LOGGER.debug("Resizing Post DE images to 724x320...")
            all_images = await self.hass.async_add_executor_job(
                resize_images,
                images,
                724,
                320,
            )
            delete_list.extend(all_images)

            _LOGGER.debug("Generating animated GIF for Post DE")
            gif_path = str(Path(path) / name)
            await self.hass.async_add_executor_job(
                generate_delivery_gif,
                all_images,
                gif_path,
                duration * 1000,
            )
            _LOGGER.debug("Post DE mail image generated.")
        except (OSError, ValueError) as err:
            _LOGGER.error("Error attempting to generate Post DE image: %s", err)

        for image in delete_list:
            await self.hass.async_add_executor_job(
                cleanup_images,
                f"{Path(image).parent}/",
                Path(image).name,
            )

    async def _copy_nomail_image(self, path: str, name: str, custom_img: str | None):
        """Copy the 'no mail' placeholder image."""

        def _prepare():
            if not Path(path).exists():
                Path(path).mkdir(parents=True, exist_ok=True)
            target = Path(path) / name
            if target.is_file():
                cleanup_images(path + "/", name)
            src = custom_img or str(Path(__file__).parent.parent / "mail_none.gif")
            if not Path(src).is_absolute():
                src = self.hass.config.path(src)
            shutil.copyfile(src, str(target))

        _LOGGER.debug("No Post DE mail found.")
        try:
            await self.hass.async_add_executor_job(_prepare)
        except OSError as err:
            _LOGGER.error("Error attempting to copy Post DE image: %s", err)

    def _get_config(self) -> dict:
        """Get Post DE specific configuration."""

        image_path = self.config.get("image_path")
        return {
            "image_output_path": image_path,
            "gif_duration": self.config.get(CONF_DURATION),
            "image_name": self.config.get("post_de_image") or "post_de_deliveries.gif",
            "gen_mp4": self.config.get(CONF_GENERATE_MP4),
            "custom_img": self.config.get(CONF_POST_DE_CUSTOM_IMG_FILE)
            or self.config.get(CONF_CUSTOM_IMG_FILE)
            or DEFAULT_CUSTOM_IMG_FILE,
            "gen_grid": self.config.get(CONF_GENERATE_GRID),
        }

    async def _search_emails(self, account: IMAP4_SSL) -> tuple:
        """Search for Post DE Briefankündigung emails."""
        _LOGGER.debug("Attempting to find Post DE Briefankündigung mail")
        _LOGGER.debug("Post DE search date: %s", get_formatted_date())

        config = SENSOR_DATA["post_de_mail"]
        email_addresses = config.get("email", [])
        subjects = config.get("subject", [])

        forwarding_header = self.config.get(CONF_FORWARDING_HEADER, "")
        if forwarding_header and forwarding_header != "(none)":
            pass
        else:
            forwarding_header = ""
            forwarded_emails = self.config.get("forwarded_emails", [])
            if isinstance(forwarded_emails, str):
                forwarded_emails = [
                    e.strip() for e in forwarded_emails.split(",") if e.strip()
                ]
            if forwarded_emails:
                email_addresses = forwarded_emails + email_addresses

        return await email_search(
            account=account,
            address=email_addresses,
            date=get_formatted_date(),
            subject=subjects,
            header=forwarding_header,
        )

    async def _setup_image_directory(self, path: str) -> bool:
        """Ensure image directory exists and is prepared."""
        if not await anyio.Path(path).is_dir():
            try:
                await anyio.Path(path).mkdir(parents=True, exist_ok=True)
            except OSError as err:
                _LOGGER.error("Error creating directory: %s", err)
                return False

        # Clean up
        await self.hass.async_add_executor_job(cleanup_images, path + "/")
        return True

    async def _process_post_de_email(  # noqa: C901
        self,
        account: IMAP4_SSL,
        num: str,
        image_output_path: str,
        image_count: int,
        images: list,
        cache: EmailCache | None = None,
    ) -> tuple[int, list]:
        """Process a single Post DE email and extract envelope scans.

        Expected email payload format is HTML containing inline <img> tags
        referencing base64-encoded PNG/JPEG images.
        """
        if cache:
            msg_parts = (await cache.fetch(num, "(RFC822)"))[1]
        else:
            msg_parts = (await email_fetch(account, num, "(RFC822)"))[1]
        _LOGGER.debug("Processing Post DE email number: %s", num)
        for response_part in msg_parts:
            if isinstance(response_part, (bytes, bytearray)):
                msg = email.message_from_bytes(response_part)
                for part in msg.walk():
                    if part.get_content_type() in ("image/png", "image/jpeg"):
                        payload = part.get_payload(decode=True)
                        if not payload:
                            continue

                        # Check image dimensions to skip logos/icons
                        def _check_and_save(
                            img_bytes: bytes,
                            out_path: str,
                            content_type: str,
                        ) -> str | None:
                            try:
                                img = Image.open(io.BytesIO(img_bytes))
                                if img.format is None:
                                    _LOGGER.debug(
                                        "Post DE image format is unidentified (None)"
                                    )
                                    return None

                                # Validate format against expected content type
                                if content_type == "image/png" and img.format != "PNG":
                                    _LOGGER.debug(
                                        "Post DE image format mismatch: expected PNG, got %s",
                                        img.format,
                                    )
                                    return None
                                if (
                                    content_type == "image/jpeg"
                                    and img.format != "JPEG"
                                ):
                                    _LOGGER.debug(
                                        "Post DE image format mismatch: expected JPEG, got %s",
                                        img.format,
                                    )
                                    return None

                                width, height = img.size
                                if width > 150 and height > 100:
                                    ext = (
                                        ".png"
                                        if content_type == "image/png"
                                        else ".jpg"
                                    )
                                    filename = random_filename(ext=ext)
                                    target = Path(out_path) / filename
                                    with target.open("wb") as f:
                                        f.write(img_bytes)
                                    return str(target)
                            except UnidentifiedImageError as err:
                                _LOGGER.warning(
                                    "Unidentified image found in Post DE email: %s", err
                                )
                            except (OSError, ValueError, TypeError) as err:
                                _LOGGER.debug(
                                    "Error checking/saving Post DE image: %s", err
                                )
                            return None

                        saved_path = await self.hass.async_add_executor_job(
                            _check_and_save,
                            payload,
                            image_output_path,
                            part.get_content_type(),
                        )
                        if saved_path:
                            images.append(saved_path)
                            image_count += 1
                            _LOGGER.debug(
                                "Extracted Post DE mail image: %s", saved_path
                            )

        return image_count, images
