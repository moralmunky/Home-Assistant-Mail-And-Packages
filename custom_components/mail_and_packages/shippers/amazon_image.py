"""Image processing mixin for Amazon shipper."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from shutil import copyfile
from typing import Any

import anyio

from custom_components.mail_and_packages.const import (
    AMAZON_DELIVERED_SUBJECT,
    CONF_DURATION,
)
from custom_components.mail_and_packages.utils.amazon import (
    amazon_email_addresses,
    download_amazon_img,
    filter_amazon_strings,
)
from custom_components.mail_and_packages.utils.date import get_today
from custom_components.mail_and_packages.utils.image import (
    cleanup_images,
    generate_delivery_gif,
    random_filename,
    resize_images,
)
from custom_components.mail_and_packages.utils.imap import (
    email_fetch,
    email_search,
)

from .amazon_helpers import _amazon_attr, _is_amazon_delivered

_LOGGER = logging.getLogger(__name__)


class AmazonImageMixin:
    """Mixin providing image processing, GIF generation, and placeholder handling."""

    hass: Any
    config: dict[str, Any]

    async def _amazon_search(
        self,
        account: Any,
        image_path: str,
        amazon_image_name: str,
        amazon_domain: str,
        fwds: list[str] | None = None,
        cache: Any = None,
        forwarding_header: str = "",
    ) -> int:
        """Find Amazon Delivered email and handle images."""
        _LOGGER.debug("=== AMAZON DELIVERED SEARCH START ===")
        subjects = _amazon_attr("AMAZON_DELIVERED_SUBJECT", AMAZON_DELIVERED_SUBJECT)
        today = _amazon_attr("get_today", get_today)().strftime("%d-%b-%Y")
        count = 0
        all_image_urls = []

        cleanup_fn = _amazon_attr("cleanup_images", cleanup_images)
        await self.hass.async_add_executor_job(
            cleanup_fn,
            f"{image_path or ''}amazon/",
        )

        email_addresses_fn = _amazon_attr(
            "amazon_email_addresses", amazon_email_addresses
        )
        address_list = email_addresses_fn(fwds, amazon_domain)
        _LOGGER.debug("Amazon email search addresses: %s", address_list)
        if amazon_domain:
            filter_fn = _amazon_attr("filter_amazon_strings", filter_amazon_strings)
            subjects = filter_fn(subjects, amazon_domain)

        search_fn = _amazon_attr("email_search", email_search)
        (server_response, data) = await search_fn(
            account=account,
            address=address_list,
            date=today,
            subject=subjects,
            header=forwarding_header,
        )
        if server_response == "OK" and data[0]:
            fetch_fn = _amazon_attr("email_fetch", email_fetch)
            for email_id in data[0].split():
                fetch_id = (
                    email_id.decode() if isinstance(email_id, bytes) else email_id
                )
                if cache:
                    msg_data = (await cache.fetch(fetch_id, "(RFC822)"))[1]
                else:
                    msg_data = (await fetch_fn(account, fetch_id, "(RFC822)"))[1]

                is_delivered, urls = _is_amazon_delivered(msg_data, subjects)
                if is_delivered:
                    count += 1
                    for url in urls:
                        if url not in all_image_urls:
                            all_image_urls.append(url)

        await self._process_amazon_images(
            all_image_urls, image_path, amazon_image_name, count
        )

        return count

    async def _process_amazon_images(
        self,
        image_urls: list[str],
        image_base_path: str,
        image_name: str,
        email_count: int,
    ) -> None:
        """Process and save Amazon delivery images."""
        if not image_base_path or not image_name:
            return

        path_cls = _amazon_attr("Path", Path)
        amazon_path = path_cls(image_base_path) / "amazon"
        image_files = await self._download_all_images(image_urls, image_base_path)

        if len(image_files) > 1:
            await self._create_amazon_gif(image_files, amazon_path, image_name)
        elif len(image_files) == 1:
            await self._save_single_amazon_image(
                image_files[0], amazon_path, image_name
            )
        else:
            await self._copy_amazon_placeholder(amazon_path, image_name)

    async def _download_all_images(self, urls: list[str], base_path: str) -> list[str]:
        """Download all image URLs to temporary files."""
        image_files = []
        path_cls = _amazon_attr("Path", Path)
        amazon_path = path_cls(base_path) / "amazon"
        download_fn = _amazon_attr("download_amazon_img", download_amazon_img)
        for url in urls:
            temp_filename = random_filename()
            await download_fn(url, base_path, temp_filename, self.hass)
            full_temp_path = amazon_path / temp_filename
            if await anyio.Path(full_temp_path).exists():
                image_files.append(str(full_temp_path))
        return image_files

    async def _create_amazon_gif(
        self, image_files: list[str], amazon_path: Path, image_name: str
    ) -> None:
        """Create animated GIF from multiple images."""
        _LOGGER.debug("Combining %d Amazon images into GIF", len(image_files))
        resizer = _amazon_attr("resize_images", resize_images)
        resized_images = await self.hass.async_add_executor_job(
            resizer, image_files, 724, 320
        )
        gif_path = str(amazon_path / image_name)
        duration = self.config.get(CONF_DURATION, 5) * 1000
        gif_generator = _amazon_attr("generate_delivery_gif", generate_delivery_gif)
        await self.hass.async_add_executor_job(
            gif_generator, resized_images, gif_path, duration
        )
        cleanup_fn = _amazon_attr("cleanup_images", cleanup_images)
        for img in image_files + resized_images:
            if await anyio.Path(img).exists():
                path_cls = _amazon_attr("Path", Path)
                await self.hass.async_add_executor_job(
                    cleanup_fn, str(path_cls(img).parent) + "/", path_cls(img).name
                )

    async def _save_single_amazon_image(
        self, image_file: str, amazon_path: Path, image_name: str
    ) -> None:
        """Save a single image by renaming it to the final name."""
        final_path = amazon_path / image_name
        if await anyio.Path(final_path).exists():
            await anyio.Path(final_path).unlink()
        path_cls = _amazon_attr("Path", Path)
        await self.hass.async_add_executor_job(path_cls(image_file).rename, final_path)
        _LOGGER.debug("Single Amazon image saved: %s", image_name)

    async def _copy_amazon_placeholder(
        self, amazon_path: Path, image_name: str
    ) -> None:
        """Copy the Amazon no-delivery placeholder."""
        path_cls = _amazon_attr("Path", Path)
        nomail = f"{path_cls(__file__).parent.parent}/no_deliveries_amazon.jpg"
        _LOGGER.debug("No Amazon images found in emails, using placeholder")
        try:
            if not await anyio.Path(amazon_path).exists():
                with contextlib.suppress(OSError):
                    await anyio.Path(amazon_path).mkdir(parents=True, exist_ok=True)
            copier = _amazon_attr("copyfile", copyfile)
            await self.hass.async_add_executor_job(
                copier, nomail, str(amazon_path / image_name)
            )
        except OSError as err:
            _LOGGER.error("Error attempting to copy image: %s", err)
