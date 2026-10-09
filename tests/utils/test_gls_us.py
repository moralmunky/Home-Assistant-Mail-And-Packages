"""Tests for the GLS USA delivery-photo download."""

import base64
import re
from pathlib import Path
from unittest.mock import patch

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.mail_and_packages.utils.gls_us import (
    GLS_US_SUMMARIES_URL,
    _pick_pod_stop,
    download_gls_us_pod,
)

TRACKING = "SH552778893058102026"
PHOTO = b"\xff\xd8\xff\xe0 fake jpeg bytes"
POD_URL = re.compile(r"^https://connect\.gls-us\.com/api/public/tracking/GetPodImage")


def _shipment(stop_id, delivered_at, status="delivered", has_pod=True):
    """Build one shipment the way GLS USA's summary endpoint returns it."""
    return {
        "trackingNumber": TRACKING,
        "status": status,
        "stopId": stop_id,
        "deliveredAt": delivered_at,
        "hasPodImage": has_pod,
    }


def _saved_files(directory: Path) -> list[Path]:
    return list(directory.iterdir())


def _summary(*shipments):
    return {"shipments": list(shipments), "isSuccess": True, "statusCode": 200}


def _pod(content=None):
    content = base64.b64encode(PHOTO).decode() if content is None else content
    return {"content": content, "isSuccess": True, "statusCode": 200}


async def _download(hass, tmp_path, tracking=None):
    return await download_gls_us_pod(
        hass,
        [TRACKING] if tracking is None else tracking,
        str(tmp_path),
        "butcherbox",
        "butcherbox_delivery.jpg",
    )


@pytest.mark.asyncio
async def test_saves_delivery_photo(hass, tmp_path):
    """A delivered shipment with a photo is saved under the shipper's folder."""
    (tmp_path / "butcherbox").mkdir()
    with aioresponses() as mock:
        mock.post(
            GLS_US_SUMMARIES_URL, payload=_summary(_shipment(1747742656, "2026-10-09"))
        )
        mock.get(POD_URL, payload=_pod())

        assert await _download(hass, tmp_path) is True

        pod_call = next(
            call
            for (method, url), calls in mock.requests.items()
            if method == "GET"
            for call in calls
        )
    assert pod_call.kwargs["params"] == {"stopId": "1747742656", "isMasked": "true"}
    assert (tmp_path / "butcherbox" / "butcherbox_delivery.jpg").read_bytes() == PHOTO


@pytest.mark.asyncio
async def test_sends_every_tracking_number_in_one_lookup(hass, tmp_path):
    """GLS USA takes a comma-separated list and skips numbers it doesn't know."""
    with aioresponses() as mock:
        mock.post(GLS_US_SUMMARIES_URL, payload=_summary())

        assert await _download(hass, tmp_path, ["SH1", "SH2"]) is False

        ((_, calls),) = mock.requests.items()
    assert calls[0].kwargs["json"] == {"trackingNumbers": "SH1,SH2", "isFreight": False}


def test_picks_most_recent_delivery_with_a_photo():
    """Only delivered shipments that have a photo count; the newest wins."""
    shipments = [
        _shipment(1, "2026-10-01T10:00:00"),
        _shipment(2, "2026-10-09T14:36:54"),
        _shipment(3, "2026-10-10T09:00:00", has_pod=False),
        _shipment(4, None, status="in transit"),
    ]
    assert _pick_pod_stop(shipments) == 2
    assert _pick_pod_stop([_shipment(5, None, status="in transit")]) is None
    assert _pick_pod_stop([]) is None


@pytest.mark.asyncio
async def test_no_tracking_numbers_makes_no_request(hass, tmp_path):
    """Nothing to look up means no call to GLS USA at all."""
    with aioresponses() as mock:
        assert await _download(hass, tmp_path, []) is False
        assert not mock.requests


@pytest.mark.asyncio
async def test_unknown_shipment(hass, tmp_path):
    """GLS USA answers an unknown number with an empty list, not an error."""
    with aioresponses() as mock:
        mock.post(GLS_US_SUMMARIES_URL, payload={"shipments": [], "isSuccess": False})
        assert await _download(hass, tmp_path) is False
    assert not (tmp_path / "butcherbox").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("summary_status", "pod_status", "pod_body"),
    [
        (500, None, None),
        (200, 500, None),
        # What GetPodImage returns when the photo is unavailable.
        (200, 200, {"content": None, "statusCode": 500, "isSuccess": False}),
        (200, 200, _pod(content="not base64!")),
    ],
)
async def test_failures_save_nothing(
    hass, tmp_path, summary_status, pod_status, pod_body
):
    """Every failure returns False so the caller falls back to its placeholder."""
    (tmp_path / "butcherbox").mkdir()
    with aioresponses() as mock:
        mock.post(
            GLS_US_SUMMARIES_URL,
            status=summary_status,
            payload=_summary(_shipment(1747742656, "2026-10-09")),
        )
        if pod_status is not None:
            mock.get(POD_URL, status=pod_status, payload=pod_body)

        assert await _download(hass, tmp_path) is False
    assert not _saved_files(tmp_path / "butcherbox")


@pytest.mark.asyncio
async def test_network_error(hass, tmp_path):
    """A network failure is logged and treated as no photo."""
    with aioresponses() as mock:
        mock.post(GLS_US_SUMMARIES_URL, exception=aiohttp.ClientError("boom"))
        assert await _download(hass, tmp_path) is False


@pytest.mark.asyncio
async def test_oversized_photo_is_discarded(hass, tmp_path):
    """A photo over the size cap is not written."""
    (tmp_path / "butcherbox").mkdir()
    with (
        aioresponses() as mock,
        patch("custom_components.mail_and_packages.utils.gls_us._MAX_IMAGE_SIZE", 4),
    ):
        mock.post(
            GLS_US_SUMMARIES_URL, payload=_summary(_shipment(1747742656, "2026-10-09"))
        )
        mock.get(POD_URL, payload=_pod())

        assert await _download(hass, tmp_path) is False
    assert not _saved_files(tmp_path / "butcherbox")
