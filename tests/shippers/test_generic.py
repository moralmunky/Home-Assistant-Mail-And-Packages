"""Tests for generic shipper utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
)
from custom_components.mail_and_packages.shippers import generic
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from custom_components.mail_and_packages.utils.cache import EmailCache


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

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
    ):
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
async def test_usps_delivered_class(hass, mock_imap_usps_delivered_individual):
    """Test USPS delivered email parsing via GenericShipper class."""
    shipper = GenericShipper(
        hass,
        {
            "image_path": "test/path/usps/",
        },
    )

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
    ):
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

    with (
        patch("custom_components.mail_and_packages.shippers.generic.Path.mkdir"),
    ):
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

    # fedex_packages is an empty dict in SENSOR_DATA (no email/subject keys)
    result = await shipper.process(mock_account, "today", "fedex_packages")
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []
    # Verify no IMAP search was attempted
    mock_account.search.assert_not_called()
    assert "Skipping email search for fedex_packages" in caplog.text


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
        assert "forward@test.com" in mock_search.call_args[0][1]


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
        search_addresses = mock_search.call_args[0][1]
        assert "forward@test.com" in search_addresses
        assert "other@test.com" in search_addresses


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
        # Called once for process_emails_by_type and once for check_amazon_mentions
        assert mock_find.call_count == 2


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
            return {"ups_packages": 1, ATTR_TRACKING: ["T1"]}
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
        assert result["ups_delivering"] == 1  # T1 removed
        # ups_packages = delivering(1 after dedup) + delivered(1) = 2
        assert result["ups_packages"] == 2

        # FedEx Deduplication
        assert result["fedex_delivered"] == 1
        assert result["fedex_delivering"] == 0  # F1 removed

        # Tracking Aggregation
        assert set(result[ATTR_TRACKING]) == {"T1", "T2", "F1"}


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
        result = await shipper.process(mock_account, "today", "ups_packages")
        mock_search.assert_not_called()
        assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_ups_packages_with_forwarded_emails_skips_imap(hass):
    """Test that ups_packages skips IMAP even when forwarded_emails are configured.

    Regression test: previously forwarded_emails were prepended to the empty
    email list and sent as a broad FROM-only IMAP query, matching all forwarder
    mail instead of UPS mail.
    """
    shipper = GenericShipper(hass, {"forwarded_emails": ["forwarder@example.com"]})
    mock_account = AsyncMock()
    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
    ) as mock_search:
        result = await shipper.process(mock_account, "today", "ups_packages")
        mock_search.assert_not_called()
        assert result[ATTR_COUNT] == 0


def test_compute_package_totals(hass):
    """Test _compute_package_totals sets _packages as delivering + delivered."""
    shipper = GenericShipper(hass, {})
    batch_results = [
        ("ups_delivering", {"ups_delivering": 3, ATTR_COUNT: 3, ATTR_TRACKING: []}),
        ("ups_delivered", {"ups_delivered": 1, ATTR_COUNT: 1, ATTR_TRACKING: []}),
        ("ups_packages", {"ups_packages": 0, ATTR_COUNT: 0, ATTR_TRACKING: []}),
        ("fedex_delivering", {"fedex_delivering": 2, ATTR_COUNT: 2, ATTR_TRACKING: []}),
        ("fedex_delivered", {"fedex_delivered": 0, ATTR_COUNT: 0, ATTR_TRACKING: []}),
        ("fedex_packages", {"fedex_packages": 0, ATTR_COUNT: 0, ATTR_TRACKING: []}),
    ]
    shipper._compute_package_totals(batch_results)

    _, ups_res = next(r for r in batch_results if r[0] == "ups_packages")
    assert ups_res["ups_packages"] == 4  # 3 delivering + 1 delivered
    assert ups_res[ATTR_COUNT] == 4

    _, fedex_res = next(r for r in batch_results if r[0] == "fedex_packages")
    assert fedex_res["fedex_packages"] == 2  # 2 delivering + 0 delivered
    assert fedex_res[ATTR_COUNT] == 2


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
    call_date = mock_search.call_args[0][2]
    assert call_date == "19-Apr-2026"


@pytest.mark.asyncio
async def test_process_delivered_uses_since_date(hass):
    """_delivered sensors also use since_date so delivered tracking numbers are
    found and can cancel out old in-transit emails for the same package."""
    shipper = GenericShipper(hass, {"image_path": "/tmp/test/"})
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

    call_date = mock_search.call_args[0][2]
    assert call_date == "19-Apr-2026"


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

    call_date = mock_search.call_args[0][2]
    assert call_date == "19-Apr-2026"


@pytest.mark.asyncio
async def test_process_packages_ignores_since_date(hass):
    """Empty-config _packages sensors do no IMAP search regardless of since_date."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.shippers.generic.email_search",
    ) as mock_search:
        await shipper.process(
            mock_account,
            "22-Apr-2026",
            "ups_packages",
            since_date="19-Apr-2026",
        )

    mock_search.assert_not_called()
