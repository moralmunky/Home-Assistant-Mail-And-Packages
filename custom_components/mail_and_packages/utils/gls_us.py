"""GLS USA proof-of-delivery photo download.

Some shippers (ButcherBox) hand their boxes to GLS USA and only email a link to
their own tracking page, so there is no delivery photo in the mailbox to
extract. GLS USA's public tracking site can still show one: it looks the
shipment up by the shipper's tracking number, and a delivered shipment that
has a photo exposes it by its ``stopId``. Both calls are anonymous, the same
ones gls-us.com's track-and-trace page makes. Only the masked photo is public;
the unmasked one needs a GLS account.
"""

from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.mail_and_packages.utils.image import io_save_file

_LOGGER = logging.getLogger(__name__)

GLS_US_API = "https://connect.gls-us.com/api/public/tracking"
GLS_US_SUMMARIES_URL = f"{GLS_US_API}/TrackShipmentSummariesByTrackingNumbers"
GLS_US_POD_URL = f"{GLS_US_API}/GetPodImage"

_TIMEOUT = aiohttp.ClientTimeout(total=30)
_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB, same cap as the Amazon download


def _pick_pod_stop(shipments: list[dict[str, Any]]) -> int | None:
    """Return the stopId of the most recently delivered shipment with a photo."""
    candidates = [
        s
        for s in shipments
        if s.get("status") == "delivered" and s.get("hasPodImage") and s.get("stopId")
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda s: s.get("deliveredAt") or "")
    return int(latest["stopId"])


async def download_gls_us_pod(
    hass: HomeAssistant,
    tracking_numbers: list[str],
    image_path: str,
    shipper_name: str,
    image_name: str,
) -> bool:
    """Save the newest GLS USA delivery photo for these tracking numbers.

    Writes ``<image_path>/<shipper_name>/<image_name>`` and returns True when a
    photo was saved. Every failure (unknown number, not delivered yet, no photo,
    network error) returns False so the caller falls back to its placeholder.
    """
    if not tracking_numbers:
        return False

    session = async_get_clientsession(hass)
    try:
        async with session.post(
            GLS_US_SUMMARIES_URL,
            json={"trackingNumbers": ",".join(tracking_numbers), "isFreight": False},
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug("GLS USA tracking lookup returned HTTP %s", resp.status)
                return False
            summary = await resp.json(content_type=None)

        stop_id = _pick_pod_stop((summary or {}).get("shipments") or [])
        if stop_id is None:
            _LOGGER.debug(
                "GLS USA has no delivery photo for %s", ", ".join(tracking_numbers)
            )
            return False

        async with session.get(
            GLS_US_POD_URL,
            params={"stopId": str(stop_id), "isMasked": "true"},
            timeout=_TIMEOUT,
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug("GLS USA photo request returned HTTP %s", resp.status)
                return False
            pod = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.warning("Problem fetching GLS USA delivery photo: %s", err)
        return False

    content = (pod or {}).get("content")
    if not content:
        _LOGGER.debug("GLS USA returned no photo for stop %s", stop_id)
        return False

    try:
        data = base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError):
        _LOGGER.warning("GLS USA delivery photo was not valid base64")
        return False
    if len(data) > _MAX_IMAGE_SIZE:
        _LOGGER.warning("GLS USA delivery photo exceeds size limit, discarding")
        return False

    target = Path(image_path) / shipper_name / image_name
    await hass.async_add_executor_job(io_save_file, target, data)
    _LOGGER.debug("Saved GLS USA delivery photo for stop %s to %s", stop_id, target)
    return True
