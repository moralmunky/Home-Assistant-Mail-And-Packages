"""Amazon image download and processing utilities."""

from __future__ import annotations

import email
import logging
import re
from pathlib import Path
from typing import Any

import aiohttp
from aioimaplib import IMAP4_SSL
from yarl import URL

from custom_components.mail_and_packages.const import (
    AMAZON_IMG_LIST,
    AMAZON_IMG_PATTERN,
)
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.image import io_save_file
from custom_components.mail_and_packages.utils.imap import email_fetch

_LOGGER = logging.getLogger(__name__)

_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
_IMAGE_URL_PATTERN = re.compile(AMAZON_IMG_PATTERN)


def _allowed_image_url(candidate: str) -> URL | None:
    """Return the URL aiohttp can fetch from an approved Amazon image host."""
    try:
        url = URL(candidate.replace("&amp;", "&"))
    except ValueError:
        return None
    if (
        url.scheme != "https"
        or url.raw_host not in AMAZON_IMG_LIST
        or url.port != 443
        or url.raw_user is not None
        or url.raw_password is not None
    ):
        return None
    return url


async def download_amazon_img(
    img_url: str,
    img_path: str,
    img_name: str,
    hass: Any,
) -> None:
    """Download image from url."""
    url = _allowed_image_url(img_url)
    if url is None:
        return

    img_path_obj = Path(img_path) / "amazon"
    filepath = img_path_obj / img_name
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url, allow_redirects=False) as resp:
                if resp.status != 200:
                    return
                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type:
                    return
                content_length = int(resp.headers.get("content-length", 0))
                if content_length > _MAX_IMAGE_SIZE:
                    _LOGGER.warning(
                        "Amazon image too large to download (%d bytes), skipping",
                        content_length,
                    )
                    return
                data = await resp.read()
                if len(data) > _MAX_IMAGE_SIZE:
                    _LOGGER.warning(
                        "Amazon image exceeds size limit after download, discarding"
                    )
                    return
                await hass.async_add_executor_job(io_save_file, filepath, data)
        except aiohttp.ClientError as err:
            _LOGGER.error("Problem downloading file: %s", err)


def extract_amazon_image_urls(msg: email.message.Message) -> list[str]:
    """Extract Amazon delivery image URLs from a message."""
    urls = []
    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue
        part_payload = part.get_payload(decode=True)
        if not isinstance(part_payload, (bytes, bytearray)):
            continue
        part_content = part_payload.decode("utf-8", "ignore")
        for match in _IMAGE_URL_PATTERN.finditer(part_content):
            full_url = match.group()
            if full_url not in urls and _allowed_image_url(full_url) is not None:
                urls.append(full_url)
    return urls


async def get_amazon_image_urls(
    sdata: Any,
    account: IMAP4_SSL,
    cache: EmailCache | None = None,
) -> list[str]:
    """Find all Amazon delivery image URLs."""
    mail_list = sdata.split()
    urls: list[str] = []
    for i in mail_list:
        if cache:
            data = (await cache.fetch(i, "(RFC822)"))[1]
        else:
            data = (await email_fetch(account, i, "(RFC822)"))[1]
        for response_part in data:
            if isinstance(response_part, (bytes, bytearray)):
                msg = email.message_from_bytes(response_part)
                for full_url in extract_amazon_image_urls(msg):
                    if full_url not in urls:
                        urls.append(full_url)
    return urls
