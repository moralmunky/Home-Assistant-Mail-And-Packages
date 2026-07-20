"""Tests for generic shipper utilities."""

import re
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    CONF_FORWARDING_HEADER,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.shippers import generic
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from custom_components.mail_and_packages.utils.cache import EmailCache
from tests.conftest import _generate_fetch_side_effect


@pytest.mark.asyncio
async def test_generic_handles_sensor(hass):
    """Test GenericShipper handles_sensor method (Line 48)."""
    assert GenericShipper.handles_sensor("ups_delivered") is True
    assert GenericShipper.handles_sensor("non_existent_sensor") is False


@pytest.mark.asyncio
async def test_generic_shipper_basic(hass):
    """Test GenericShipper basic initialization (Line 43)."""
    shipper = GenericShipper(hass, {})
    assert shipper.name == "generic"


@pytest.mark.asyncio
async def test_ups_delivered_class(hass, mock_imap_ups_delivered):
    """Test UPS delivered email parsing via GenericShipper class."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/ups/",
            "image_name": "testfilename.jpg",
        },
    )

    with (patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),):
        result = await shipper.process(
            mock_imap_ups_delivered,
            "today",
            "ups_delivered",
        )
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["1Z2345YY0678901234"]


@pytest.mark.asyncio
async def test_fedex_delivered_class(hass, mock_imap_fedex_delivered_with_photo):
    """Test FedEx delivered email parsing via GenericShipper class."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/fedex/",
            "image_name": "testfilename.jpg",
        },
    )

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch(
            "custom_components.mail_and_packages.shippers.generic.generic_delivery_image_extraction",
            return_value=True,
        ),
    ):
        result = await shipper.process(
            mock_imap_fedex_delivered_with_photo,
            "today",
            "fedex_delivered",
        )
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["885814254426"]


@pytest.mark.asyncio
async def test_image_extraction_runs_off_event_loop(
    hass, mock_imap_fedex_delivered_with_photo
):
    """generic_delivery_image_extraction must run in an executor thread.

    Regression test: it parses the full email and writes the image with
    blocking file I/O; calling it directly from the coordinator path
    triggers HA's blocking-call-in-event-loop detection. The probe records
    which thread each extraction call runs on and asserts none of them is
    the event-loop thread.

    The probe is installed with ``new=`` (a plain function, not a Mock) on
    purpose: the test harness's ``async_add_executor_job`` wrapper runs
    Mock targets inline on the loop, which would defeat the thread check.
    """
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/fedex/",
            "image_name": "testfilename.jpg",
        },
    )

    loop_thread = threading.get_ident()
    extract_threads: list[int] = []

    def _extract_probe(*args):
        extract_threads.append(threading.get_ident())
        return True

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch(
            "custom_components.mail_and_packages.shippers.generic.generic_delivery_image_extraction",
            new=_extract_probe,
        ),
    ):
        result = await shipper.process(
            mock_imap_fedex_delivered_with_photo,
            "today",
            "fedex_delivered",
        )

    assert result[ATTR_COUNT] == 1
    # The fixture email yields one extraction call per bytes response part.
    assert len(extract_threads) >= 1
    assert all(tid != loop_thread for tid in extract_threads), (
        "generic_delivery_image_extraction ran on the event-loop thread "
        "instead of an executor thread"
    )


@pytest.mark.asyncio
async def test_usps_delivered_class(hass, mock_imap_usps_delivered_individual):
    """Test USPS delivered email parsing via GenericShipper class."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/usps/",
        },
    )

    with (patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),):
        result = await shipper.process(
            mock_imap_usps_delivered_individual,
            "today",
            "usps_delivered",
        )
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["92001901755477000000000000"]


@pytest.mark.asyncio
async def test_usps_exception_class(hass, mock_imap_usps_exception):
    """Test USPS exception email parsing via GenericShipper class."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/usps/",
        },
    )

    with (patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),):
        result = await shipper.process(
            mock_imap_usps_exception,
            "today",
            "usps_exception",
        )
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["92748902410637553123456789"]


@pytest.mark.asyncio
async def test_generic_sensor_not_found(hass):
    """Test GenericShipper with a sensor not in SENSOR_DATA."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    result = await shipper.process(mock_account, "today", "non_existent_sensor")
    assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_generic_packages_sensor_skips_search(hass, caplog):
    """Test that *_packages sensors with no email config skip IMAP search."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    caplog.set_level("DEBUG")

    # capost_packages is an empty dict in SENSOR_DATA (no email/subject keys)
    result = await shipper.process(mock_account, "today", "capost_packages")
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []
    # Verify no IMAP search was attempted
    mock_account.search.assert_not_called()
    assert (
        "Skipping email search for capost_packages: no email addresses configured"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_generic_non_packages_sensor_no_email_skips_search(hass, caplog):
    """Test that a non-_packages sensor with no email config also skips IMAP search."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    caplog.set_level("DEBUG")

    # poczta_polska_delivered is an empty dict in SENSOR_DATA
    result = await shipper.process(mock_account, "today", "poczta_polska_delivered")
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []
    mock_account.search.assert_not_called()
    assert (
        "Skipping email search for poczta_polska_delivered: no email addresses configured"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_generic_with_images_and_amazon_mentions(hass):
    """Test GenericShipper with image extraction and Amazon mentions."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/ups/",
            "image_name": "testfilename.jpg",
        },
    )

    # ups_delivered will trigger shipper_name = "ups"
    # which will trigger image extraction

    msg_bytes = b"Subject: Your UPS Package was delivered\n\nYour Amazon order was delivered by UPS. amazon.com/help"
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK",
        lines=[b"RFC822", msg_bytes],
    )

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch(
            "custom_components.mail_and_packages.shippers.generic.generic_delivery_image_extraction",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["1Z123"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        result = await shipper.process(mock_account, "today", "ups_delivered")
        assert result[ATTR_COUNT] == 1
        assert result["amazon_delivered_by_others"] == 1
        assert result[ATTR_TRACKING] == ["1Z123"]


@pytest.mark.asyncio
async def test_generic_ups_exception(hass):
    """Test GenericShipper with UPS exception."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    # No body search needed for ups_exception usually, just IDs

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["1Z999"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        result = await shipper.process(mock_account, "today", "ups_exception")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["1Z999"]


@pytest.mark.asyncio
async def test_generic_fedex_exception(hass):
    """Test GenericShipper with FedEx exception (carrier parity with UPS)."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["123456789012"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        result = await shipper.process(mock_account, "today", "fedex_exception")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["123456789012"]


@pytest.mark.asyncio
async def test_generic_image_extraction_no_shipper(hass):
    """Test GenericShipper image extraction logic when no shipper name is found."""
    # Test path where sensor_type doesn't map to a shipper name for image extraction
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])

    result = await shipper.process(mock_account, "today", "z_generic_delivered")
    assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_generic_multiple_emails(hass):
    """Test GenericShipper with multiple emails for a single sensor."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()
    # Mocking search returning 2 email IDs
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1 2"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["1Z123", "1Z456"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        result = await shipper.process(mock_account, "today", "ups_delivered")
        assert result[ATTR_COUNT] == 2
        assert result[ATTR_TRACKING] == ["1Z123", "1Z456"]


@pytest.mark.asyncio
async def test_process_tracking_numbers_invalid_key(hass):
    """Test _process_tracking_numbers with invalid tracking key (Line 135-139)."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    # "non_existent_delivered" splits to "non_existent" -> "non_existent_tracking"
    # which is not in SENSOR_DATA
    result = await shipper._process_tracking_numbers(
        "non_existent_delivered",
        [b"1"],
        mock_account,
    )
    assert result == []


@pytest.mark.asyncio
async def test_setup_image_extraction_not_delivered(hass):
    """Test _setup_image_extraction with non-delivery sensor (Line 153)."""
    shipper = GenericShipper(hass, {})
    result = await shipper._setup_image_extraction("ups_exception", "/path")
    assert result is None


@pytest.mark.asyncio
async def test_generic_forwarded_emails(hass):
    """Test GenericShipper with forwarded emails (Line 70)."""
    shipper = GenericShipper(
        hass,
        {
            "forwarded_emails": ["forward@test.com"],
            "image_path": "test/path/",
        },
    )
    mock_acc = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_acc, "today", "ups_delivered")
        assert "forward@test.com" in mock_search.call_args.kwargs["address"]


@pytest.mark.asyncio
async def test_generic_forwarded_emails_string(hass):
    """Test that a legacy string value for forwarded_emails is normalized to a list."""
    shipper = GenericShipper(
        hass,
        {
            "forwarded_emails": "forward@test.com, other@test.com",
            "image_path": "test/path/",
        },
    )
    mock_acc = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_acc, "today", "ups_delivered")
        search_addresses = mock_search.call_args.kwargs["address"]
        assert "forward@test.com" in search_addresses
        assert "other@test.com" in search_addresses


@pytest.mark.asyncio
async def test_generic_forwarding_header_mode(hass):
    """Test GenericShipper in header mode: forwarded_emails not prepended, header kwarg passed."""
    shipper = GenericShipper(
        hass,
        {
            CONF_FORWARDING_HEADER: "X-SimpleLogin-Original-From",
            "forwarded_emails": ["should-not-appear@example.com"],
            "image_path": "test/path/",
        },
    )
    mock_acc = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_acc, "today", "ups_delivered")
        search_addresses = mock_search.call_args.kwargs["address"]
        assert "should-not-appear@example.com" not in search_addresses
        assert mock_search.call_args.kwargs["header"] == "X-SimpleLogin-Original-From"


@pytest.mark.asyncio
async def test_generic_body_search(hass):
    """Test GenericShipper with body search (Lines 209-211)."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_acc = AsyncMock()
    mock_acc.search.return_value = MagicMock(result="OK", lines=[b"1"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text",
            new_callable=AsyncMock,
            return_value=1,
        ) as mock_find,
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text_matches",
            new_callable=AsyncMock,
            return_value=(1, [b"1"]),
        ) as mock_find_matches,
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        # dhl_delivered has "body" in SENSOR_DATA
        result = await shipper.process(mock_acc, "today", "dhl_delivered")
        assert result[ATTR_COUNT] == 1
        assert mock_find.call_count == 1
        assert mock_find_matches.call_count == 1


@pytest.mark.asyncio
async def test_generic_body_search_no_match(hass):
    """Test GenericShipper with body search failing to match."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_acc = AsyncMock()
    mock_acc.search.return_value = MagicMock(result="OK", lines=[b"1"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text_matches",
            new_callable=AsyncMock,
            return_value=(0, []),
        ) as mock_find_matches,
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
        ) as mock_tracking,
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        result = await shipper.process(mock_acc, "today", "dhl_delivered")
        assert result[ATTR_COUNT] == 0
        assert mock_find_matches.call_count == 1
        assert mock_tracking.call_count == 0


@pytest.mark.asyncio
async def test_generic_placeholder_default(hass):
    """Test _copy_generic_placeholder falls back to mail_none.gif (Line 118)."""
    shipper = GenericShipper(hass, {})
    shipper_cfg = {
        "name": "non_existent_courier",
        "image_path": "/fake/path",
        "image_name": "test.gif",
    }

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.anyio.Path.exists",
            return_value=False,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.copyfile",
        ) as mock_copy,
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
    ):
        await shipper._copy_generic_placeholder(shipper_cfg)
        # Verify that it tried to copy mail_none.gif
        assert "mail_none.gif" in mock_copy.call_args[0][0]


@pytest.mark.asyncio
async def test_process_batch(hass):
    """Test process_batch for Generic shipper."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    mock_cache = MagicMock()

    with patch.object(shipper, "process", new_callable=AsyncMock) as mock_process:
        # Mock process to return a result that requires the "sensor not in sensor_res" logic
        async def _mock_process(account, date, sensor, cache, **kwargs):
            if sensor == "ups_delivered":
                # Trigger the coordinator dictionary logic fallback
                return {ATTR_COUNT: 5}
            return {sensor: 0}

        mock_process.side_effect = _mock_process

        sensors = ["ups_delivered"]
        result = await shipper.process_batch(mock_account, "today", sensors, mock_cache)

        assert result["ups_delivered"] == 5


@pytest.mark.asyncio
async def test_process_with_cache(hass):
    """Test Generic shipper processing with EmailCache."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    cache = EmailCache(mock_account)

    # Populate cache for _broad_search_then_filter (Lines 299, etc.)
    # ups_delivered has many subjects, so it will use broad search
    cache._cache_headers["1"] = (
        "OK",
        [b"Subject: Your UPS Package was delivered"],
    )
    cache._cache_rfc822["1"] = (
        "OK",
        [b"RFC822", b"Subject: Your UPS Package was delivered\n\n1Z123"],
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
    ):
        result = await shipper.process(
            mock_account, "today", "ups_delivered", cache=cache
        )
        assert result[ATTR_COUNT] == 1


@pytest.mark.asyncio
async def test_generic_image_found(hass):
    """Test GenericShipper when an image is successfully extracted (Line 299)."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/ups/",
            "image_name": "testfilename.jpg",
        },
    )
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch(
            "custom_components.mail_and_packages.shippers.generic.generic_delivery_image_extraction",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["1Z123"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch",
            new_callable=AsyncMock,
            return_value=("OK", [b"RFC822", b"body"]),
        ),
        patch.object(
            shipper, "_copy_generic_placeholder", new_callable=AsyncMock
        ) as mock_copy,
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        result = await shipper.process(mock_account, "today", "ups_delivered")
        assert result[ATTR_COUNT] == 1
        # image_found is true, so _copy_generic_placeholder should NOT be called
        mock_copy.assert_not_called()


@pytest.mark.asyncio
async def test_generic_search_coverage_edges(hass):
    """Test GenericShipper coverage for Line 219 and 233."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    # Patch SENSOR_DATA to give ups_delivered only 2 subjects, hitting the 'else' branch
    # but still having a valid camera config (ups_camera).
    modified_sensor_data = generic.SENSOR_DATA.copy()
    modified_sensor_data["ups_delivered"] = {
        **modified_sensor_data["ups_delivered"],
        "subject": ["Subject 1", "Subject 2"],
    }

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.SENSOR_DATA",
            modified_sensor_data,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            new_callable=AsyncMock,
            side_effect=[
                ("OK", [b"1"]),  # Subject 1 finds ID 1
                ("OK", [b"1"]),  # Subject 2 finds ID 1 again -> Hits Line 219
            ],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_fetch",
            new_callable=AsyncMock,
            return_value=("OK", [b"RFC822", b"body"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.generic_delivery_image_extraction",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
        patch.object(shipper, "_copy_generic_placeholder", new_callable=AsyncMock),
        patch(
            "custom_components.mail_and_packages.shippers.generic.GenericShipper._verify_matched_subjects",
            new_callable=AsyncMock,
            side_effect=lambda a, b, c, d, cache=None: b,
        ),
    ):
        # We use 'ups_delivered' because it has a camera entry ('ups_camera')
        result = await shipper.process(mock_account, "today", "ups_delivered")
        # Line 233 hit because image_found = True
        assert result[ATTR_COUNT] == 1


@pytest.mark.asyncio
async def test_process_batch_deduplication(hass):
    """Test process_batch deduplication and tracking aggregation."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    mock_cache = MagicMock()

    async def _mock_process(account, date, sensor, cache, **kwargs):
        if sensor == "ups_delivered":
            return {"ups_delivered": 1, ATTR_TRACKING: ["T1"]}
        if sensor == "ups_delivering":
            return {"ups_delivering": 2, ATTR_TRACKING: ["T1", "T2"], ATTR_COUNT: 2}
        if sensor == "ups_packages":
            # T1 already in delivered/delivering; T3 is a new upcoming shipment
            return {"ups_packages": 2, ATTR_TRACKING: ["T1", "T3"]}
        if sensor == "fedex_delivered":
            return {"fedex_delivered": 1, ATTR_TRACKING: ["F1"]}
        if sensor == "fedex_delivering":
            return {"fedex_delivering": 1, ATTR_TRACKING: ["F1"]}
        return {sensor: 0, ATTR_TRACKING: []}

    with patch.object(shipper, "process", side_effect=_mock_process):
        sensors = [
            "ups_delivered",
            "ups_delivering",
            "ups_packages",
            "fedex_delivered",
            "fedex_delivering",
        ]
        result = await shipper.process_batch(mock_account, "today", sensors, mock_cache)

        # UPS Deduplication
        assert result["ups_delivered"] == 1
        assert result["ups_delivering"] == 1  # T1 removed (already delivered)
        # ups_packages has its own IMAP search; T1 and T2 are removed (in pipeline)
        # leaving only T3 (upcoming shipment not yet delivering/delivered)
        assert result["ups_packages"] == 1

        # FedEx Deduplication
        assert result["fedex_delivered"] == 1
        assert result["fedex_delivering"] == 0  # F1 removed

        # Tracking Aggregation
        assert set(result[ATTR_TRACKING]) == {"T1", "T2", "F1", "T3"}


@pytest.mark.asyncio
async def test_process_batch_dedup_uses_extended_window_delivered(hass):
    """Dedup subtracts packages delivered on PRIOR days, not just today.

    Regression test: ATTR_TRACKING on _delivered sensors holds only
    today's deliveries (the sensor resets at midnight); the dedup set
    must come from pre_filtered_tracking (the extended-window list) or
    packages delivered yesterday stay in _delivering until they age out.
    """
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    mock_cache = MagicMock()

    async def _mock_process(account, date, sensor, cache, **kwargs):
        if sensor == "fedex_delivered":
            # Delivered emails exist for F1+F2 earlier in the window; none today
            return {
                "fedex_delivered": 0,
                ATTR_TRACKING: [],
                "pre_filtered_tracking": ["F1", "F2"],
            }
        if sensor == "fedex_delivering":
            return {
                "fedex_delivering": 2,
                ATTR_TRACKING: ["F1", "F2"],
                ATTR_COUNT: 2,
            }
        return {sensor: 0, ATTR_TRACKING: []}

    with patch.object(shipper, "process", side_effect=_mock_process):
        result = await shipper.process_batch(
            mock_account, "today", ["fedex_delivered", "fedex_delivering"], mock_cache
        )

        assert result["fedex_delivered"] == 0
        assert result["fedex_delivering"] == 0  # F1+F2 delivered on prior days
        assert result["_tracking_details"]["fedex_delivered"] == ["F1", "F2"]
        assert "fedex_delivering" not in result["_tracking_details"]


@pytest.mark.asyncio
async def test_generic_image_reset_on_zero_count(hass):
    """Test GenericShipper camera image resets when count is zero."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/ups/",
            "image_name": "testfilename.jpg",
        },
    )
    mock_account = AsyncMock()

    # Mock _search_for_emails to return count=0, image_found=False
    with (
        patch.object(
            shipper,
            "_search_for_emails",
            new_callable=AsyncMock,
            return_value=(0, [], False),
        ),
        patch.object(
            shipper,
            "_setup_image_extraction",
            new_callable=AsyncMock,
            return_value={
                "name": "ups",
                "image_path": "test/path/ups/",
                "image_name": "testfilename.jpg",
            },
        ),
        patch.object(
            shipper,
            "_copy_generic_placeholder",
            new_callable=AsyncMock,
        ) as mock_copy,
    ):
        result = await shipper.process(mock_account, "today", "ups_delivered")
        assert result[ATTR_COUNT] == 0
        # This is what we are testing: it should be called even if count is 0
        mock_copy.assert_called_once()


@pytest.mark.asyncio
async def test_verify_matched_subjects(hass, caplog):
    """Test _verify_matched_subjects filters emails locally for debugging."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    caplog.set_level("DEBUG")

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_fetch_headers",
        new_callable=AsyncMock,
        return_value=("OK", [b"Subject: Your package has been delivered"]),
    ):
        expected_subjects = ["Your package has been delivered"]
        verified = await shipper._verify_matched_subjects(
            mock_account, [b"42"], "fedex_delivered", expected_subjects
        )
        assert "Matched email for fedex_delivered (ID 42)" in caplog.text
        assert "Your package has been delivered" in caplog.text
        assert verified == [b"42"]


@pytest.mark.asyncio
async def test_verify_matched_subjects_rejection(hass, caplog):
    """Test _verify_matched_subjects rejects emails that don't match expected subjects."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    caplog.set_level("DEBUG")

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_fetch_headers",
        new_callable=AsyncMock,
        return_value=(
            "OK",
            [b"Subject: Your shipment is scheduled for delivery tomorrow 380636585874"],
        ),
    ):
        expected_subjects = [
            "Your package has been delivered",
            "Your packages have been delivered",
            "Your shipment was delivered",
        ]
        verified = await shipper._verify_matched_subjects(
            mock_account, [b"42"], "fedex_delivered", expected_subjects
        )
        assert "Subject did not match any expected subjects" in caplog.text
        assert verified == []


@pytest.mark.asyncio
async def test_verify_matched_subjects_with_cache(hass, caplog):
    """Test _verify_matched_subjects uses cache when available."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    cache = EmailCache(mock_account)
    caplog.set_level("DEBUG")

    # Pre-populate the cache
    cache._cache_headers["42"] = (
        "OK",
        [b"Subject: Your UPS Package was delivered"],
    )

    expected_subjects = ["Your UPS Package was delivered"]
    verified = await shipper._verify_matched_subjects(
        mock_account, [b"42"], "ups_delivered", expected_subjects, cache=cache
    )
    assert "Matched email for ups_delivered (ID 42)" in caplog.text
    assert verified == [b"42"]


@pytest.mark.asyncio
async def test_verify_matched_subjects_error(hass, caplog):
    """Test _verify_matched_subjects handles fetch errors gracefully."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    caplog.set_level("DEBUG")

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_fetch_headers",
        new_callable=AsyncMock,
        side_effect=OSError("Connection lost"),
    ):
        expected_subjects = ["Some subject"]
        verified = await shipper._verify_matched_subjects(
            mock_account, [b"99"], "fedex_delivered", expected_subjects
        )
        assert "Could not fetch subject for email" in caplog.text
        assert verified == []


@pytest.mark.asyncio
async def test_verify_matched_subjects_empty_expected(hass):
    """Test _verify_matched_subjects bypasses filtering when expected_subjects is empty."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    # Pass empty list for expected_subjects
    verified = await shipper._verify_matched_subjects(
        mock_account, [b"123", b"456"], "ups_exception", []
    )

    # Verify that the exact same list of email IDs is returned
    assert verified == [b"123", b"456"]
    # Verify no IMAP fetch calls were made
    mock_account.fetch.assert_not_called()


def test_decode_subject_string_with_encoding(hass):
    """Test _decode_subject when decode_header returns a string and an encoding."""
    shipper = GenericShipper(hass, {})
    with patch(
        "custom_components.mail_and_packages.shippers.generic.decode_header",
        return_value=[("A string instead of bytes", "utf-8")],
    ):
        result = shipper._decode_subject(b"Subject: dummy")
        assert result == "A string instead of bytes"


@pytest.mark.asyncio
async def test_ups_packages_empty_config_skips_imap(hass):
    """Test that ups_packages with empty SENSOR_DATA config skips IMAP search."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
    ) as mock_search:
        # capost_packages still has {} config — skips IMAP
        result = await shipper.process(mock_account, "today", "capost_packages")
        mock_search.assert_not_called()
        assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_ups_packages_searches_imap(hass):
    """Test that ups_packages now performs an IMAP search with its own config."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [b""]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "ups_packages")
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        # Verify UPS emails are passed
        assert "mcinfo@ups.com" in call_args.kwargs["address"]


@pytest.mark.asyncio
async def test_ups_packages_with_forwarded_emails_includes_both(hass):
    """Test that forwarded_emails are prepended to UPS emails for ups_packages."""
    shipper = GenericShipper(hass, {"forwarded_emails": ["forwarder@example.com"]})
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [b""]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "ups_packages")
        mock_search.assert_called_once()
        email_list = mock_search.call_args.kwargs["address"]
        assert "forwarder@example.com" in email_list
        assert "mcinfo@ups.com" in email_list


def test_compute_package_totals(hass):
    """Test _compute_package_totals sets _packages as delivering + delivered for carriers with empty config."""
    shipper = GenericShipper(hass, {})
    # capost_packages still has {} config — should be computed as delivering + delivered
    # dhl_packages also has {} config
    batch_results = [
        (
            "capost_delivering",
            {"capost_delivering": 3, ATTR_COUNT: 3, ATTR_TRACKING: []},
        ),
        ("capost_delivered", {"capost_delivered": 1, ATTR_COUNT: 1, ATTR_TRACKING: []}),
        ("capost_packages", {"capost_packages": 0, ATTR_COUNT: 0, ATTR_TRACKING: []}),
        ("dhl_delivering", {"dhl_delivering": 2, ATTR_COUNT: 2, ATTR_TRACKING: []}),
        ("dhl_delivered", {"dhl_delivered": 0, ATTR_COUNT: 0, ATTR_TRACKING: []}),
        ("dhl_packages", {"dhl_packages": 0, ATTR_COUNT: 0, ATTR_TRACKING: []}),
    ]
    shipper._compute_package_totals(batch_results)

    _, capost_res = next(r for r in batch_results if r[0] == "capost_packages")
    assert capost_res["capost_packages"] == 4  # 3 delivering + 1 delivered
    assert capost_res[ATTR_COUNT] == 4

    _, dhl_res = next(r for r in batch_results if r[0] == "dhl_packages")
    assert dhl_res["dhl_packages"] == 2  # 2 delivering + 0 delivered
    assert dhl_res[ATTR_COUNT] == 2


@pytest.mark.asyncio
async def test_process_delivering_uses_since_date(hass):
    """_delivering sensors use since_date for their IMAP search."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(
            mock_account, "22-Apr-2026", "ups_delivering", since_date="19-Apr-2026"
        )

    # The search date passed to IMAP should be since_date, not today
    call_date = mock_search.call_args.kwargs["date"]
    assert call_date == "19-Apr-2026"


@pytest.mark.asyncio
async def test_process_delivered_uses_since_date(hass):
    """_delivered sensors search twice: since_date for tracking dedup, date for count.

    The first call uses since_date so delivered tracking numbers can cancel out
    old in-transit emails. The second call uses today's date so the sensor count
    resets at midnight.
    """
    shipper = GenericShipper(hass, {"image_path": "/tmp/test/"})  # noqa: S108
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            return_value=("OK", [None]),
        ) as mock_search,
        patch.object(hass, "async_add_executor_job", new_callable=AsyncMock),
    ):
        await shipper.process(
            mock_account, "22-Apr-2026", "ups_delivered", since_date="19-Apr-2026"
        )

    assert mock_search.call_count == 2
    # First call: extended window for tracking deduplication
    assert mock_search.call_args_list[0].kwargs["date"] == "19-Apr-2026"
    # Second call: today only so the count resets at midnight
    assert mock_search.call_args_list[1].kwargs["date"] == "22-Apr-2026"


@pytest.mark.asyncio
async def test_process_exception_uses_since_date(hass):
    """_exception sensors use since_date for their IMAP search."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(
            mock_account,
            "22-Apr-2026",
            "walmart_exception",
            since_date="19-Apr-2026",
        )

    call_date = mock_search.call_args.kwargs["date"]
    assert call_date == "19-Apr-2026"


@pytest.mark.asyncio
async def test_process_packages_ignores_since_date(hass):
    """Empty-config _packages sensors do no IMAP search regardless of since_date."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
    ) as mock_search:
        # capost_packages still has {} config — skips IMAP even with since_date
        await shipper.process(
            mock_account,
            "22-Apr-2026",
            "capost_packages",
            since_date="19-Apr-2026",
        )

    mock_search.assert_not_called()


@pytest.mark.asyncio
async def test_ups_packages_uses_since_date(hass):
    """ups_packages with real config uses since_date for IMAP search window."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        return_value=("OK", [b""]),
    ) as mock_search:
        await shipper.process(
            mock_account,
            "22-Apr-2026",
            "ups_packages",
            since_date="19-Apr-2026",
        )

    mock_search.assert_called_once()
    # since_date should be passed as the search date, not the regular date
    assert mock_search.call_args.kwargs["date"] == "19-Apr-2026"


@pytest.mark.asyncio
async def test_aliexpress_delivered_class(hass):
    """Test AliExpress delivered email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch.object(
            shipper,
            "_verify_matched_subjects",
            new_callable=AsyncMock,
            return_value=[b"1"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text_matches",
            new_callable=AsyncMock,
            return_value=(1, [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["LP123456789DE"],
        ),
    ):
        result = await shipper.process(mock_account, "today", "aliexpress_delivered")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["LP123456789DE"]


@pytest.mark.asyncio
async def test_intelcom_dragonfly_delivered(hass):
    """Test Dragonfly (Intelcom) delivered email parsing."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch.object(
            shipper,
            "_verify_matched_subjects",
            new_callable=AsyncMock,
            return_value=[b"1"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text_matches",
            new_callable=AsyncMock,
            return_value=(1, [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["INTLCMI19292929"],
        ),
    ):
        result = await shipper.process(mock_account, "today", "intelcom_delivered")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["INTLCMI19292929"]


@pytest.mark.asyncio
async def test_intelcom_dragonfly_delivering(hass):
    """Test Dragonfly (Intelcom) delivering email parsing."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch.object(
            shipper,
            "_verify_matched_subjects",
            new_callable=AsyncMock,
            return_value=[b"1"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text_matches",
            new_callable=AsyncMock,
            return_value=(1, [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["INTLCMI19292929"],
        ),
    ):
        result = await shipper.process(mock_account, "today", "intelcom_delivering")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["INTLCMI19292929"]


@pytest.mark.asyncio
async def test_purolator_delivering_alternate_subject(hass):
    """Test Purolator delivering email parsing with alternate subject line."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch.object(
            shipper,
            "_verify_matched_subjects",
            new_callable=AsyncMock,
            return_value=[b"1"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.find_text_matches",
            new_callable=AsyncMock,
            return_value=(1, [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            new_callable=AsyncMock,
            return_value=["BVH001683614"],
        ),
    ):
        result = await shipper.process(mock_account, "today", "purolator_delivering")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_TRACKING] == ["BVH001683614"]


@pytest.mark.asyncio
async def test_aliexpress_delivered_2026_format(hass, mock_imap_aliexpress_delivered):
    """Test AliExpress delivered email parsing (2026 subject format)."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_aliexpress_delivered,
        "today",
        "aliexpress_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["JY26CAA0D000551012"]


@pytest.mark.asyncio
async def test_aliexpress_with_local_carrier_2026_format(
    hass, mock_imap_aliexpress_with_local_carrier
):
    """Test AliExpress with-local-carrier email parsing (2026 subject format)."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_aliexpress_with_local_carrier,
        "today",
        "aliexpress_delivering",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["JY26CAA0D000551012"]


@pytest.mark.asyncio
async def test_aliexpress_order_shipped_2026_format(
    hass, mock_imap_aliexpress_order_shipped
):
    """Test AliExpress order-shipped email parsing (2026 subject format)."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_aliexpress_order_shipped,
        "today",
        "aliexpress_delivering",
    )
    assert result[ATTR_COUNT] == 1
    assert len(result[ATTR_TRACKING]) == 1


@pytest.mark.asyncio
async def test_purolator_shipment_delivered_2026_format(
    hass, mock_imap_purolator_shipment_delivered
):
    """Test Purolator delivered email parsing (2026 bilingual subject format)."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_purolator_shipment_delivered,
        "today",
        "purolator_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["RKP000051945"]


@pytest.mark.asyncio
async def test_purolator_shipment_out_for_delivery_2026_format(
    hass, mock_imap_purolator_shipment_out_for_delivery
):
    """Test Purolator out-for-delivery email parsing (2026 bilingual format)."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_purolator_shipment_out_for_delivery,
        "today",
        "purolator_delivering",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["RKP000051945"]


@pytest.mark.asyncio
async def test_etsy_delivered_class(hass, mock_imap_etsy_delivered):
    """Test Etsy delivered email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_etsy_delivered,
        "today",
        "etsy_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["3869977574"]


@pytest.mark.asyncio
async def test_etsy_on_the_way_class(hass, mock_imap_etsy_on_the_way):
    """Test Etsy on-the-way email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_etsy_on_the_way,
        "today",
        "etsy_delivering",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["3869977574"]


@pytest.mark.asyncio
async def test_shopify_on_the_way_class(hass, mock_imap_shopify_on_the_way):
    """Test standard Shopify on-the-way email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_shopify_on_the_way,
        "today",
        "shopify_packages",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["MC1605"]


@pytest.mark.asyncio
async def test_shopify_delivered_class(hass, mock_imap_shopify_delivered):
    """Test standard Shopify delivered email parsing via GenericShipper."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})

    result = await shipper.process(
        mock_imap_shopify_delivered,
        "today",
        "shopify_delivered",
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == ["53495"]


@pytest.mark.parametrize(
    ("subject", "expected_sensor"),
    [
        ("Order 8211968327931234: order shipped", "aliexpress_delivering"),
        ("Order 8211968327931234: collected by the carrier", "aliexpress_delivering"),
        (
            "Package JY26CAA0D000551012: left the departure region",
            "aliexpress_delivering",
        ),
        ("Package JY26CAA0D000551012: at customs", "aliexpress_delivering"),
        ("Package JY26CAA0D000551012 has cleared customs", "aliexpress_delivering"),
        ("Package JY26CAA0D000551012: in your country/region", "aliexpress_delivering"),
        ("Package HM0000010001198611: in local transit", "aliexpress_delivering"),
        ("Package JY26CAA0D000551012: with local carrier", "aliexpress_delivering"),
        ("Package JY26CAA0D000551012 has been delivered", "aliexpress_delivered"),
        # Non-shipping notifications from the same sender must not match
        ("Order 8211968327931234: order confirmed", None),
        ("Order 8211968327931234: awaiting confirmation", None),
        ("Order 8211968327931234: how did it go?", None),
        ("Your delayed delivery coupon code", None),
    ],
)
def test_aliexpress_2026_subject_patterns(subject, expected_sensor):
    """Each real 2026 AliExpress subject maps to exactly one sensor (or none)."""
    matched = [
        sensor
        for sensor in ("aliexpress_delivered", "aliexpress_delivering")
        if any(
            expected.lower() in subject.lower()
            for expected in SENSOR_DATA[sensor][ATTR_SUBJECT]
        )
    ]
    if expected_sensor is None:
        assert matched == []
    else:
        assert matched == [expected_sensor]


@pytest.mark.parametrize(
    ("subject", "expected_sensor"),
    [
        # 2026 "Purolator shipment <PIN>:" bilingual format
        (
            (
                "Purolator shipment RKP000051945: Your package has been delivered "
                "/Envoi de Purolator RKP000051945 : Votre colis a été livré"
            ),
            "purolator_delivered",
        ),
        (
            (
                "Purolator shipment RKP000051945: Your package is now out for delivery"
                "/ Envoi de Purolator RKP000051945 : Votre colis est en cours de livraison"
            ),
            "purolator_delivering",
        ),
        # Older "Purolator - " format (still observed mid-2025)
        (
            (
                "Purolator - Your shipment is delivered / Votre envoi a été livré"
                "- +/- PIN/NIC:335596611426"
            ),
            "purolator_delivered",
        ),
        (
            (
                "Purolator - Your shipment is out for delivery / Votre envoi est en "
                "voie d'être livré - - PIN/NIC:607828110629"
            ),
            "purolator_delivering",
        ),
        (
            (
                "Purolator - Your shipment is on its way / Votre envoi est en route "
                "- PIN/NIC:335596611426"
            ),
            "purolator_delivering",
        ),
        (
            (
                "Purolator - Your shipment has been picked up / Votre envoi a été "
                "ramassé - PIN/NIC:335596611426"
            ),
            "purolator_packages",
        ),
        # Non-shipping notifications from the same sender must not match
        (
            (
                "Access Your Purolator Your Way Account /Accédez à votre compte "
                "Purolator Votre façon"
            ),
            None,
        ),
        (
            (
                "Verify your email to track and customize your Purolator delivery "
                "preferences/Vérifiez votre adresse courriel pour faire le suivi de "
                "vos préférences de livraison de Purolator et les personnaliser"
            ),
            None,
        ),
        (
            (
                "Purolator PIN/NIC 335596611426  - A summary of your shipment "
                "/ Un résumé de votre envoi"
            ),
            None,
        ),
        ("Shipment Update / Mise à jour d' expédition - PIN/NIC: 335596611426", None),
        (
            (
                "Purolator - Your shipment is ready for pickup / Votre colis est "
                "prêt pour la cueillette - PIN/NIC:335596611426"
            ),
            None,
        ),
    ],
)
def test_purolator_2026_subject_patterns(subject, expected_sensor):
    """Each real Purolator subject maps to exactly one sensor (or none)."""
    matched = [
        sensor
        for sensor in (
            "purolator_delivered",
            "purolator_delivering",
            "purolator_packages",
        )
        if any(
            expected.lower() in subject.lower()
            for expected in SENSOR_DATA[sensor][ATTR_SUBJECT]
        )
    ]
    if expected_sensor is None:
        assert matched == []
    else:
        assert matched == [expected_sensor]


@pytest.mark.parametrize(
    ("subject", "expected_sensor"),
    [
        (
            "It's here! Your order from YverInc has been delivered.",
            "etsy_delivered",
        ),
        (
            "Another package for your Etsy order is on the way (Receipt #3869977574)",
            "etsy_delivering",
        ),
        ("Your Etsy order is on the way (Receipt #3620921447)", "etsy_delivering"),
        ("Your Etsy Order dispatched (Receipt #3620921447)", "etsy_delivering"),
        ("And it’s off! Deutsche Post has your order 🚚", "etsy_delivering"),
        ("Ding! Order updates are waiting in the app 📦", "etsy_delivering"),
        # Non-shipping notifications from Etsy senders must not match
        ("Your Etsy Purchase from TheVinc (4106538106)", None),
        ("John Doe, you have a new item to review.", None),
        ("John Doe, did you recently sign into Etsy?", None),
        ("Sports + vintage = winning combo", None),
    ],
)
def test_etsy_subject_patterns(subject, expected_sensor):
    """Each real Etsy subject maps to exactly one sensor (or none)."""
    matched = [
        sensor
        for sensor in ("etsy_delivered", "etsy_delivering")
        if any(
            expected.lower() in subject.lower()
            for expected in SENSOR_DATA[sensor][ATTR_SUBJECT]
        )
    ]
    if expected_sensor is None:
        assert matched == []
    else:
        assert matched == [expected_sensor]


@pytest.mark.parametrize(
    ("subject", "expected_sensor"),
    [
        ("A shipment from order MC1605 is on the way", "shopify_packages"),
        ("A shipment from order #24498 is on the way", "shopify_packages"),
        ("A shipment from order BAK(2)-563319 is on the way", "shopify_packages"),
        ("A shipment from order MC1605 is out for delivery", "shopify_delivering"),
        ("A shipment from order #53495 has been delivered", "shopify_delivered"),
        # Non-shipping mail from Shopify's shared senders must not match
        ("Order #77220 confirmed", None),
        ("Your GreenPan cart? Saved ✅ over on Shop.", None),
        ("Customer account confirmation", None),
    ],
)
def test_shopify_subject_patterns(subject, expected_sensor):
    """Each standard Shopify template subject maps to exactly one sensor."""
    matched = [
        sensor
        for sensor in ("shopify_delivered", "shopify_delivering", "shopify_packages")
        if any(
            expected.lower() in subject.lower()
            for expected in SENSOR_DATA[sensor][ATTR_SUBJECT]
        )
    ]
    if expected_sensor is None:
        assert matched == []
    else:
        assert matched == [expected_sensor]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 2026 package IDs (letters+digits, 16-18 chars)
        ("Package JY26CAA0D000551012 has been delivered", "JY26CAA0D000551012"),
        ("Package HM0000010001198611: in local transit", "HM0000010001198611"),
        ("Package AP00823271816356: at customs", "AP00823271816356"),
        # UPU S10 format (pre-existing) still matches
        ("Sendung LP123456789DE zugestellt", "LP123456789DE"),
        # Plain 13-digit numeric (pre-existing) still matches
        ("tracking 1234567890123 status", "1234567890123"),
    ],
)
def test_aliexpress_tracking_pattern(text, expected):
    """The AliExpress tracking pattern extracts old and new tracking formats."""
    pattern = SENSOR_DATA["aliexpress_tracking"]["pattern"][0]
    match = re.search(pattern, text)
    assert match is not None
    assert match.group(0) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 2026 alphanumeric PIN (3 letters + 9 digits)
        (
            "Purolator shipment RKP000051945: Your package has been delivered",
            "RKP000051945",
        ),
        # Older alphanumeric PIN format
        ("PIN/NIC:CFY002985537", "CFY002985537"),
        # Numeric PINs (pre-existing pattern) still match
        ("PIN/NIC:335596611426", "335596611426"),
        ("PIN/NIC:607828110629123", "607828110629123"),
    ],
)
def test_purolator_tracking_pattern(text, expected):
    """The Purolator tracking pattern extracts old and new PIN formats."""
    pattern = SENSOR_DATA["purolator_tracking"]["pattern"][0]
    match = re.search(pattern, text)
    assert match is not None
    assert match.group(0) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Subject form
        ("Your Etsy order is on the way (Receipt #3869977574)", "3869977574"),
        # Body form ("Order" and number split across lines)
        ("h001.token )\nOrder\n#3869977574 (\nhttps://etsy.com", "3869977574"),
        # Purchase-receipt style parenthesised number must NOT match
        ("Your Etsy Purchase from TheVinc (4106538106)", None),
    ],
)
def test_etsy_tracking_pattern(text, expected):
    """The Etsy tracking pattern extracts receipt numbers from subject or body."""
    pattern = SENSOR_DATA["etsy_tracking"]["pattern"][0]
    match = re.search(pattern, text)
    if expected is None:
        assert match is None
    else:
        assert match is not None
        assert match.group(1) == expected


@pytest.mark.asyncio
async def test_etsy_carrier_tracking_extraction(hass, mock_imap):
    """A carrier tracking number embedded in a marketplace email is mapped."""
    email_file = await hass.async_add_executor_job(
        Path("tests/test_emails/etsy_on_the_way.eml").read_text
    )
    email_file = email_file.replace(
        "Track your package for the latest updates.",
        "Canada Post tracking number: 1234567890123456",
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)

    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(mock_imap, "today", "etsy_delivering")

    assert result[ATTR_COUNT] == 1
    assert result["etsy_carrier_tracking"] == {"3869977574": "1234567890123456"}


@pytest.mark.asyncio
async def test_etsy_no_carrier_tracking_is_noop(hass, mock_imap_etsy_on_the_way):
    """Marketplace emails without a carrier tracking number map nothing."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(
        mock_imap_etsy_on_the_way, "today", "etsy_delivering"
    )
    assert result[ATTR_COUNT] == 1
    assert "etsy_carrier_tracking" not in result


@pytest.mark.asyncio
async def test_etsy_carrier_tracking_without_cache(hass, mock_imap):
    """Test carrier tracking extraction when cache is None (hits email_fetch path)."""
    email_file = await hass.async_add_executor_job(
        Path("tests/test_emails/etsy_on_the_way.eml").read_text
    )
    email_file = email_file.replace(
        "Track your package for the latest updates.",
        "Canada Post tracking number: 1234567890123456",
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(email_file)

    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
        AsyncMock(return_value=("OK", [b"1"])),
    ):
        result = await shipper.process(
            mock_imap, "today", "etsy_delivering", cache=None
        )

    assert result[ATTR_COUNT] == 1
    assert result["etsy_carrier_tracking"] == {"3869977574": "1234567890123456"}


def test_find_carrier_number_payload_decode_errors():
    """Test _find_carrier_number handles AttributeError and ValueError during payload decode."""
    part1 = MagicMock()
    part1.get_content_type.return_value = "text/plain"
    part1.get_payload.side_effect = AttributeError("No payload")

    part2 = MagicMock()
    part2.get_content_type.return_value = "text/plain"
    part2.get_payload.side_effect = ValueError("Invalid payload")

    part3 = MagicMock()
    part3.get_content_type.return_value = "text/plain"
    part3.get_payload.return_value.decode.return_value = (
        "Canada Post tracking number: 9876543210987654"
    )

    mock_msg = MagicMock()
    mock_msg.walk.return_value = [part1, part2, part3]

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email.message_from_bytes",
        return_value=mock_msg,
    ):
        pattern = re.compile(r"Canada Post tracking number:\s*(\d{16})")
        res = generic._find_carrier_number([b"dummy email bytes"], pattern)
        assert res == "9876543210987654"


@pytest.mark.asyncio
async def test_generic_shipper_process_batch_merges_carrier_tracking(hass):
    """Test process_batch merges multiple sensor _carrier_tracking results."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()

    with patch.object(
        shipper,
        "process",
        AsyncMock(
            side_effect=[
                {
                    ATTR_COUNT: 1,
                    ATTR_TRACKING: ["111"],
                    "etsy_carrier_tracking": {"111": "222"},
                },
                {
                    ATTR_COUNT: 1,
                    ATTR_TRACKING: ["333"],
                    "etsy_carrier_tracking": {"333": "444"},
                },
            ]
        ),
    ):
        res = await shipper.process_batch(
            mock_account,
            "today",
            ["etsy_delivering", "etsy_delivered"],
            cache=AsyncMock(),
        )

    assert res["etsy_carrier_tracking"] == {"111": "222", "333": "444"}


def test_find_carrier_number_non_bytes_and_non_text_parts():
    """Test _find_carrier_number skips non-bytes response parts and non-text MIME parts."""
    part_image = MagicMock()
    part_image.get_content_type.return_value = "image/png"

    part_text = MagicMock()
    part_text.get_content_type.return_value = "text/plain"
    part_text.get_payload.return_value.decode.return_value = (
        "Canada Post tracking number: 1111222233334444"
    )

    mock_msg = MagicMock()
    mock_msg.walk.return_value = [part_image, part_text]

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email.message_from_bytes",
        return_value=mock_msg,
    ):
        pattern = re.compile(r"Canada Post tracking number:\s*(\d{16})")
        # Passing integer 123 (non-bytes) and dummy bytes
        res = generic._find_carrier_number([123, b"dummy email bytes"], pattern)
        assert res == "1111222233334444"


@pytest.mark.asyncio
async def test_collect_carrier_tracking_with_cache_and_empty_tracking(hass):
    """Test _collect_carrier_tracking with cache branch and empty get_tracking branch."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    mock_account = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.fetch.return_value = ("OK", [b"dummy email content"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.get_tracking",
            AsyncMock(side_effect=[[], ["3869977574"]]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic._find_carrier_number",
            return_value="9999888877776666",
        ),
    ):
        res = await shipper._collect_carrier_tracking(
            "etsy_delivering", [b"1 2"], mock_account, cache=mock_cache
        )

    assert res == {"etsy_carrier_tracking": {"3869977574": "9999888877776666"}}
    mock_cache.fetch.assert_called_once_with(b"2", "(RFC822)")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("A shipment from order #53495 has been delivered", "53495"),
        ("A shipment from order MC1605 is on the way", "MC1605"),
        ("A shipment from order BAK(2)-563319 is on the way", "BAK(2)-563319"),
        ("A shipment from order PP3024 is on the way", "PP3024"),
    ],
)
def test_shopify_tracking_pattern(text, expected):
    """The Shopify tracking pattern extracts the order id from the subject."""
    pattern = SENSOR_DATA["shopify_tracking"]["pattern"][0]
    match = re.search(pattern, text)
    assert match is not None
    assert match.group(1) == expected
