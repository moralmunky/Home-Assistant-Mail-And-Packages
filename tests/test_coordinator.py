"""Tests for MailDataUpdateCoordinator sensor processing."""

import asyncio
import datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientResponseError
from freezegun import freeze_time
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import CONF_FOLDER, DOMAIN
from custom_components.mail_and_packages.coordinator import MailDataUpdateCoordinator
from custom_components.mail_and_packages.utils.imap import InvalidAuth
from tests.const import FAKE_CONFIG_DATA, FAKE_CONFIG_DATA_USPS_DELIVERED


@pytest.mark.asyncio
async def test_process_emails_batch_success(hass):
    """Test process_emails processes sensors in batch successfully."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = {
        "test_sensor": 5,
        "test_attribute": "value",
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert data["test_sensor"] == 5
    assert data["test_attribute"] == "value"


@pytest.mark.asyncio
async def test_process_emails_batch_exception(hass, caplog):
    """Test process_emails handles exception during batch processing."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.side_effect = Exception("Test error")

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert "Error processing shipper test_shipper: Test error" in caplog.text


@pytest.mark.asyncio
async def test_process_emails_invalid_return(hass):
    """Test process_emails gracefully handles non-dict return."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = "invalid data"

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    # Should just not crash, missing data ok
    assert "test_sensor" not in data


@pytest.mark.asyncio
async def test_mail_delivered_latches_on_across_polls(hass):
    """usps_mail_delivered should stay on for the rest of the day once seen.

    The underlying IMAP search is re-run and re-verified on every poll, so a
    transient miss must not flip a real delivery back to off — that would
    make an off->on state-trigger automation re-fire on every scan cycle.
    """
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA_USPS_DELIVERED)

    mock_shipper = AsyncMock()
    mock_shipper.name = "usps"
    mock_shipper.process_batch.side_effect = [
        {"usps_mail_delivered": 1},
        {"usps_mail_delivered": 0},
        {"usps_mail_delivered": 0},
    ]

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
        freeze_time("2026-08-05 14:17:32"),
    ):
        first = await coordinator.process_emails(hass, FAKE_CONFIG_DATA_USPS_DELIVERED)
        assert first["usps_mail_delivered"] == 1

        # Two subsequent polls where the live search comes back empty (the
        # flaky re-evaluation this bug is about) must not clear the flag.
        second = await coordinator.process_emails(hass, FAKE_CONFIG_DATA_USPS_DELIVERED)
        assert second["usps_mail_delivered"] == 1

        third = await coordinator.process_emails(hass, FAKE_CONFIG_DATA_USPS_DELIVERED)
        assert third["usps_mail_delivered"] == 1


@pytest.mark.asyncio
async def test_mail_delivered_latch_resets_on_new_day(hass):
    """usps_mail_delivered latch must reset once the day rolls over."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA_USPS_DELIVERED)

    mock_shipper = AsyncMock()
    mock_shipper.name = "usps"

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        mock_shipper.process_batch.return_value = {"usps_mail_delivered": 1}
        with freeze_time("2026-08-05 14:17:32"):
            day_one = await coordinator.process_emails(
                hass, FAKE_CONFIG_DATA_USPS_DELIVERED
            )
        assert day_one["usps_mail_delivered"] == 1

        # New day, no mail delivered yet — the latch from yesterday must not
        # leak through even though it's the same coordinator instance.
        mock_shipper.process_batch.return_value = {"usps_mail_delivered": 0}
        with freeze_time("2026-08-06 08:00:00"):
            day_two = await coordinator.process_emails(
                hass, FAKE_CONFIG_DATA_USPS_DELIVERED
            )
        assert day_two["usps_mail_delivered"] == 0


def test_latch_mail_delivered_noop_when_sensor_not_present(hass):
    """_latch_mail_delivered must not add the key when the sensor isn't in use."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    data = {"some_other_sensor": 1}
    coordinator._latch_mail_delivered(data, "2026-08-05")

    assert "usps_mail_delivered" not in data


@pytest.mark.asyncio
async def test_async_update_data_timeout_logs_and_returns_cached_data(hass, caplog):
    """When the scan exceeds its time budget, log an error and return cached data if available."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator.timeout = 0.01

    async def _slow_process(*args, **kwargs):
        await asyncio.sleep(1)
        return {}

    # Initial scan without prior data raises UpdateFailed
    with (
        patch.object(coordinator, "process_emails", side_effect=_slow_process),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()

    assert "scan exceeded its" in caplog.text
    assert "time budget" in caplog.text

    # Scan with prior cached data returns cached data instead of raising
    coordinator._data = {"mail_updated": "test_time", "usps_mail": 2}
    with patch.object(coordinator, "process_emails", side_effect=_slow_process):
        res = await coordinator._async_update_data()
        assert res == {"mail_updated": "test_time", "usps_mail": 2}


@pytest.mark.asyncio
async def test_get_imap_connection_invalid_auth(hass):
    """Test _get_imap_connection handles InvalidAuth."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            side_effect=InvalidAuth("Invalid credentials"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._get_imap_connection(FAKE_CONFIG_DATA)


@pytest.mark.asyncio
async def test_get_imap_connection_exception(hass):
    """Test _get_imap_connection handles generic Exception."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            side_effect=Exception("Connection refused"),
        ),
        pytest.raises(UpdateFailed, match="Login failed"),
    ):
        await coordinator._get_imap_connection(FAKE_CONFIG_DATA)


@pytest.mark.asyncio
async def test_process_emails_no_shipper(hass):
    """Test process_emails skips if no shipper is found."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=None,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    # Dictionary returned with nothing added since no shipper available
    assert "test_sensor" not in data


@pytest.mark.asyncio
async def test_aggregate_package_counts(hass):
    """Test that package counts are correctly aggregated."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Mock data to be aggregated
    test_data = {
        "zpackages_transit": 0,
        "zpackages_delivering": 0,
        "zpackages_delivered": 0,
        "usps_delivering": 1,
        "usps_delivered": 1,
        "ups_delivering": 2,
        "ups_delivered": 0,
        "fedex_packages": 3,
        "fedex_delivered": 2,
        "amazon_packages": 5,
        "amazon_delivering": 2,
        "amazon_delivered": 1,
        "amazon_exception": 1,
        "dhl_exception": 1,
        "unknown_sensor": 99,
        "amazon_delivered_by_others": 10,  # Should be excluded from zpackages_delivered
        "usps_mail_delivered": 3,  # Should be excluded — these are mail pieces, not packages
    }

    coordinator._aggregate_package_counts(test_data)

    # Expected Transit:
    # usps_delivering (1) + ups_delivering (2) + fedex_packages (3) + amazon_packages (5)
    # + amazon_exception (1) + dhl_exception (1)
    # = 1 + 2 + 3 + 5 + 1 + 1 = 13
    assert test_data["zpackages_transit"] == 13

    # Expected Delivering:
    # usps_delivering (1) + ups_delivering (2) + amazon_delivering (2) = 5
    assert test_data["zpackages_delivering"] == 5

    # Expected Delivered:
    # usps_delivered (1) + fedex_delivered (2) + amazon_delivered (1)
    # ups_delivered (0) is ignored as it is <= 0
    # amazon_delivered_by_others (10) and usps_mail_delivered (3) are excluded
    # = 1 + 2 + 1 = 4
    assert test_data["zpackages_delivered"] == 4


@pytest.mark.asyncio
async def test_aggregate_package_counts_no_resource(hass):
    """Test that aggregation doesn't add sensors not in initialize_data."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    test_data = {
        "usps_delivering": 1,
    }

    coordinator._aggregate_package_counts(test_data)

    assert "zpackages_transit" not in test_data
    assert "zpackages_delivered" not in test_data


@pytest.mark.asyncio
async def test_get_imap_connection_selectfolder_exception(hass):
    """Test _get_imap_connection handles exception from selectfolder."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            side_effect=Exception("Folder error"),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.logout",
        ) as mock_logout,
        pytest.raises(UpdateFailed, match="Folder selection failed"),
    ):
        await coordinator._get_imap_connection(FAKE_CONFIG_DATA)

    mock_logout.assert_called_once_with(mock_account)


# ---------------------------------------------------------------------------
# Tracking persistence tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tracking_adds_new_delivering(hass):
    """New delivering tracking numbers are added with today's date."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    today = "2026-04-22"
    coordinator._update_tracking_for_prefix("ups", ["1Z123", "1Z456"], [], today, 14)

    assert coordinator._in_transit_tracking["ups"] == {
        "1Z123": today,
        "1Z456": today,
    }


@pytest.mark.asyncio
async def test_update_tracking_removes_delivered(hass):
    """Delivering tracking numbers that appear in delivered are removed."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["ups"] = {
        "1Z123": "2026-04-20",
        "1Z456": "2026-04-21",
    }
    coordinator._update_tracking_for_prefix("ups", [], ["1Z123"], "2026-04-22", 14)

    assert "1Z123" not in coordinator._in_transit_tracking["ups"]
    assert "1Z456" in coordinator._in_transit_tracking["ups"]


@pytest.mark.asyncio
async def test_update_tracking_expires_old_entries(hass):
    """Tracking numbers older than TTL are expired."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["ups"] = {
        "1ZOLD": "2026-04-01",  # 21 days old — beyond 14-day TTL
        "1ZNEW": "2026-04-20",  # 2 days old — within TTL
    }
    coordinator._update_tracking_for_prefix("ups", [], [], "2026-04-22", 14)

    assert "1ZOLD" not in coordinator._in_transit_tracking["ups"]
    assert "1ZNEW" in coordinator._in_transit_tracking["ups"]


@pytest.mark.asyncio
async def test_update_tracking_no_duplicate_add(hass):
    """Already-known tracking numbers keep their original first-seen date."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    original_date = "2026-04-20"
    coordinator._in_transit_tracking["ups"] = {"1Z123": original_date}
    coordinator._update_tracking_for_prefix("ups", ["1Z123"], [], "2026-04-22", 14)

    assert coordinator._in_transit_tracking["ups"]["1Z123"] == original_date


@pytest.mark.asyncio
async def test_apply_tracking_state_overrides_delivering(hass):
    """_apply_tracking_state replaces IMAP-reported count with persisted count."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Pre-populate two tracking numbers in transit
    coordinator._in_transit_tracking["ups"] = {
        "1Z111": "2026-04-20",
        "1Z222": "2026-04-21",
    }

    data = {"ups_delivering": 1, "ups_delivered": 0, "ups_packages": 1}
    tracking_details = {
        "ups_delivering": ["1Z333"],  # new one found today
        "ups_delivered": [],
    }
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    # 1Z111, 1Z222 carried over + 1Z333 newly added = 3
    assert data["ups_delivering"] == 3
    # ups_packages is IMAP-backed — preserve its own count
    assert data["ups_packages"] == 1
    assert set(data["ups_tracking"]) == {"1Z111", "1Z222", "1Z333"}


@pytest.mark.asyncio
async def test_apply_tracking_state_removes_delivered(hass):
    """Packages marked delivered are removed from in-transit tracking."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["fedex"] = {
        "9261290": "2026-04-20",
        "9261999": "2026-04-21",
    }

    data = {"fedex_delivering": 2, "fedex_delivered": 1, "fedex_packages": 3}
    tracking_details = {
        "fedex_delivering": [],
        "fedex_delivered": ["9261290"],
    }
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    assert "9261290" not in coordinator._in_transit_tracking["fedex"]
    assert data["fedex_delivering"] == 1
    # fedex_packages is IMAP-backed — preserve its own count
    assert data["fedex_packages"] == 3


@pytest.mark.asyncio
async def test_apply_tracking_state_all_delivered_zeroes_count(hass):
    """Delivering count is zeroed when every in-transit package is delivered.

    Regression test: the override must fire even when the in-transit map
    becomes EMPTY, otherwise the raw IMAP count (which cannot dedup
    prior-day deliveries) leaks through as the sensor value.
    """
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["fedex"] = {
        "9261290": "2026-04-20",
        "9261999": "2026-04-21",
    }

    # Raw IMAP counts still see both delivering emails in the window;
    # delivered notifications exist for BOTH packages (on prior days, so
    # the fedex_delivered today-count is 0).
    data = {"fedex_delivering": 2, "fedex_delivered": 0, "fedex_packages": 2}
    tracking_details = {
        "fedex_delivering": ["9261290", "9261999"],
        "fedex_delivered": ["9261290", "9261999"],
    }
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    assert coordinator._in_transit_tracking["fedex"] == {}
    assert data["fedex_delivering"] == 0
    assert data["fedex_tracking"] == []
    # _packages is NOT recomputed when the map is empty: the batch-level
    # dedup (which subtracts the extended-window delivered set) already
    # made it the shipped-but-not-yet-out count, and len(in_transit) +
    # delivered_today would wrongly zero genuinely shipped packages.
    assert data["fedex_packages"] == 2


@pytest.mark.asyncio
async def test_apply_tracking_state_delivered_only_details_keeps_count(hass):
    """Delivered-only tracking details must NOT zero the delivering count.

    Regression test: a carrier whose delivering emails yield no extractable
    tracking numbers (no delivering entry in tracking_details) still has a
    legitimate email-based count. A delivered notification for an unrelated
    package must not force-override that count to len(in_transit) == 0.
    """
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Two delivering emails matched but tracking extraction found nothing;
    # an unrelated package delivered earlier in the window has a number.
    data = {"fedex_delivering": 2, "fedex_delivered": 0}
    tracking_details = {"fedex_delivered": ["9260000"]}
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    assert data["fedex_delivering"] == 2
    assert "fedex_tracking" not in data


@pytest.mark.asyncio
async def test_apply_tracking_state_no_details_keeps_email_count(hass):
    """Carriers with no tracking details keep their email-based counts."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # walmart has no tracking-number extraction this scan; its email-based
    # count must not be clobbered by an override to zero.
    data = {"walmart_delivering": 3, "ups_delivering": 1}
    tracking_details = {"ups_delivering": ["1Z111"]}
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    assert data["walmart_delivering"] == 3
    assert "walmart_tracking" not in data
    assert data["ups_delivering"] == 1


@pytest.mark.asyncio
async def test_apply_tracking_state_preserves_imap_backed_dhl_packages(hass):
    """IMAP-backed dhl_packages must not be overwritten by OFD transit totals."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._in_transit_tracking["dhl"] = {"OFD1": "2026-04-20"}
    data = {
        "dhl_delivering": 1,
        "dhl_delivered": 0,
        "dhl_packages": 3,
    }
    tracking_details = {
        "dhl_delivering": ["OFD1"],
        "dhl_delivered": [],
    }
    coordinator._apply_tracking_state(data, tracking_details, "2026-04-22")

    assert data["dhl_delivering"] == 1
    assert data["dhl_packages"] == 3
    assert data["dhl_tracking"] == ["OFD1"]


@pytest.mark.asyncio
async def test_sum_transit_counts_adds_imap_backed_packages(hass):
    """Transit total includes delivering plus IMAP-backed packages."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    data = {
        "dhl_delivering": 1,
        "dhl_packages": 2,
        "hermes_delivering": 1,
        "hermes_packages": 9,  # empty config; ignored once delivering counted
    }
    assert coordinator._sum_transit_counts(data) == 4  # dhl 1+2 + hermes 1


@pytest.mark.asyncio
async def test_apply_tracking_state_no_tracking_details(hass):
    """With empty tracking_details, data is unchanged."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    data = {"ups_delivering": 2, "ups_delivered": 1}
    coordinator._apply_tracking_state(data, {}, "2026-04-22")

    assert data["ups_delivering"] == 2
    assert data["ups_delivered"] == 1


@pytest.mark.asyncio
async def test_process_emails_passes_since_date(hass):
    """process_emails passes since_date to shippers based on CONF_CUSTOM_DAYS."""
    config = {**FAKE_CONFIG_DATA, "custom_days": 3}
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = {}

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
        patch("custom_components.mail_and_packages.coordinator.datetime") as mock_dt,
    ):
        fixed_now = datetime.datetime(2026, 4, 22, 12, 0, 0)
        mock_dt.datetime.now.return_value = fixed_now
        mock_dt.timedelta = datetime.timedelta
        mock_dt.date = datetime.date
        mock_dt.UTC = datetime.UTC
        await coordinator.process_emails(hass, config)

    call_kwargs = mock_shipper.process_batch.call_args
    since_date_passed = call_kwargs.kwargs.get("since_date")
    assert since_date_passed == "19-Apr-2026"


@pytest.mark.asyncio
async def test_process_emails_strips_tracking_details_from_output(hass):
    """_tracking_details key is consumed and not exposed in coordinator data."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper = AsyncMock()
    mock_shipper.name = "test_shipper"
    mock_shipper.process_batch.return_value = {
        "ups_delivering": 1,
        "_tracking_details": {"ups_delivering": ["1Z999"]},
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, FAKE_CONFIG_DATA)

    assert "_tracking_details" not in data


@pytest.mark.asyncio
async def test_get_imap_connection_folders_normalization(hass):
    """Test folder configuration normalization in _get_imap_connection."""
    # Case 1: folders is None / not present
    config_none = {**FAKE_CONFIG_DATA}
    config_none.pop(CONF_FOLDER, None)

    coordinator = MailDataUpdateCoordinator(hass, config_none)
    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
    ):
        await coordinator._get_imap_connection(config_none)
        assert mock_account._folders == ["INBOX"]

    # Case 2: folders is a list/tuple/set of strings
    config_list = {**FAKE_CONFIG_DATA, CONF_FOLDER: ["Junk", "INBOX"]}
    coordinator = MailDataUpdateCoordinator(hass, config_list)
    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
    ):
        await coordinator._get_imap_connection(config_list)
        assert mock_account._folders == ["Junk", "INBOX"]

    # Case 3: folders is a list of invalid types which filters to empty
    config_empty = {**FAKE_CONFIG_DATA, CONF_FOLDER: [123]}
    coordinator = MailDataUpdateCoordinator(hass, config_empty)
    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
    ):
        await coordinator._get_imap_connection(config_empty)
        assert mock_account._folders == ["INBOX"]

    # Case 4: folders is an invalid type (e.g. integer)
    config_invalid = {**FAKE_CONFIG_DATA, CONF_FOLDER: 123}
    coordinator = MailDataUpdateCoordinator(hass, config_invalid)
    mock_account = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=mock_account,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
    ):
        await coordinator._get_imap_connection(config_invalid)
        assert mock_account._folders == ["INBOX"]


@pytest.mark.asyncio
async def test_coordinator_post_de_binary_sensor_update(hass):
    """Test coordinator _binary_sensor_update correctly sets none_image for post_de."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Populate data with post_de_image attribute
    coordinator._data = {
        "post_de_image": "post_de_deliveries.gif",
    }

    # Mock the calls inside _binary_sensor_update
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.default_image_path",
            return_value="/fake_tmp",
        ),
        patch("anyio.Path.exists", return_value=True),
        patch.object(
            coordinator,
            "_get_file_hash_if_changed",
            side_effect=["hash1", "hash1"],
        ),
    ):
        await coordinator._binary_sensor_update()

    assert coordinator._data["post_de_update"] is False


@pytest.mark.asyncio
async def test_apply_tracking_state_persists_across_empty_runs(hass):
    """Verify that tracking numbers persist in data even when tracking_details is empty."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Pre-populate tracking numbers in transit
    coordinator._in_transit_tracking["ups"] = {
        "1Z111": "2026-04-22",
        "1Z222": "2026-04-22",
    }

    data = {}
    coordinator._apply_tracking_state(data, {}, "2026-04-22")

    assert data["ups_delivering"] == 2
    assert set(data["ups_tracking"]) == {"1Z111", "1Z222"}


@pytest.mark.asyncio
async def test_process_emails_merges_tracking_details_from_multiple_shippers(hass):
    """Test process_emails merges _tracking_details from multiple shippers instead of overwriting."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    mock_shipper1 = AsyncMock()
    mock_shipper1.name = "fedex"
    mock_shipper1.process_batch.return_value = {
        "_tracking_details": {"fedex_delivering": ["FEDEX123"]},
        "fedex_delivering": 1,
    }

    mock_shipper2 = AsyncMock()
    mock_shipper2.name = "ups"
    mock_shipper2.process_batch.return_value = {
        "_tracking_details": {"ups_delivering": ["UPS123"]},
        "ups_delivering": 1,
    }

    def side_effect(hass, config, sensor):
        if "fedex" in sensor:
            return mock_shipper1
        if "ups" in sensor:
            return mock_shipper2
        return None

    config = {
        **FAKE_CONFIG_DATA,
        "resources": ["fedex_delivering", "ups_delivering"],
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            side_effect=side_effect,
        ),
    ):
        data = await coordinator.process_emails(hass, config)

    assert data["fedex_delivering"] == 1
    assert data["ups_delivering"] == 1
    assert set(data["fedex_tracking"]) == {"FEDEX123"}
    assert set(data["ups_tracking"]) == {"UPS123"}


@pytest.mark.asyncio
async def test_process_emails_delivered_tracking(hass):
    """Test process_emails populates and isolates delivered tracking from in-transit."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Mock a shipper that returns both delivering and delivered details
    mock_shipper = AsyncMock()
    mock_shipper.name = "ups"
    mock_shipper.process_batch.return_value = {
        "_tracking_details": {
            "ups_delivering": ["UPS_IN_TRANSIT"],
            "ups_delivered": ["UPS_DELIVERED_TODAY", "UPS_DELIVERED_OLD"],
        },
        "ups_delivering": 1,
        "ups_delivered": 1,
        "ups_delivered_tracking": ["UPS_DELIVERED_TODAY"],
        "ups_delivering_tracking": ["UPS_IN_TRANSIT"],
    }

    config = {
        **FAKE_CONFIG_DATA,
        "resources": ["ups_delivering", "ups_delivered"],
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, config)

    # In-transit tracking should exclude the delivered ones
    assert set(data["ups_tracking"]) == {"UPS_IN_TRANSIT"}
    # Delivered tracking should show today's delivered packages
    assert set(data["ups_delivered_tracking"]) == {"UPS_DELIVERED_TODAY"}


@pytest.mark.asyncio
async def test_process_emails_delivered_tracking_reversed_order(hass):
    """Test process_emails isolates delivered tracking even with reversed insertion order."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Mock a shipper that returns delivered details before delivering details in the dict
    mock_shipper = AsyncMock()
    mock_shipper.name = "ups"
    mock_shipper.process_batch.return_value = {
        "_tracking_details": {
            "ups_delivered": ["UPS_DELIVERED_TODAY", "UPS_DELIVERED_OLD"],
            "ups_delivering": ["UPS_IN_TRANSIT"],
        },
        "ups_delivering": 1,
        "ups_delivered": 1,
        "ups_delivered_tracking": ["UPS_DELIVERED_TODAY"],
        "ups_delivering_tracking": ["UPS_IN_TRANSIT"],
    }

    config = {
        **FAKE_CONFIG_DATA,
        "resources": ["ups_delivering", "ups_delivered"],
    }

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.get_shipper_for_sensor",
            return_value=mock_shipper,
        ),
    ):
        data = await coordinator.process_emails(hass, config)

    # In-transit tracking should still correctly exclude the delivered ones
    assert set(data["ups_tracking"]) == {"UPS_IN_TRANSIT"}
    assert set(data["ups_delivered_tracking"]) == {"UPS_DELIVERED_TODAY"}


@pytest.mark.asyncio
async def test_coordinator_get_file_hash_if_changed(hass):
    """Test _get_file_hash_if_changed caching and error paths."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    with (
        patch("os.path.getmtime", return_value=12345),
        patch(
            "custom_components.mail_and_packages.coordinator.hash_file",
            return_value="hash_abc",
        ),
    ):
        hash1 = await coordinator._get_file_hash_if_changed("test_file.gif")
        assert hash1 == "hash_abc"

        # Repeated call returns cached hash directly without re-hashing
        hash2 = await coordinator._get_file_hash_if_changed("test_file.gif")
        assert hash2 == "hash_abc"

    # OSError returns None
    with patch("os.path.getmtime", side_effect=OSError("File missing")):
        assert (await coordinator._get_file_hash_if_changed("missing.gif")) is None


@pytest.mark.asyncio
async def test_coordinator_oauth_token_refresh(hass):
    """Test _async_update_data OAuth2 token refresh success and failure paths."""
    config = {**FAKE_CONFIG_DATA, "auth_type": "oauth2_google"}
    entry = MockConfigEntry(domain="mail_and_packages", data=config)
    entry.add_to_hass(hass)

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)
        coordinator.config_entry = entry

    mock_session = AsyncMock()
    mock_session.token = {"access_token": "refreshed_oauth_token"}

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.OAuth2Session",
            return_value=mock_session,
        ),
        patch.object(
            coordinator, "process_emails", AsyncMock(return_value={"test": 1})
        ),
        patch.object(coordinator, "_binary_sensor_update", AsyncMock()),
    ):
        res = await coordinator._async_update_data()
        assert res == {"test": 1}

    # Error during OAuth refresh raises UpdateFailed when no cached _data exists
    coordinator._data = {}
    mock_session_fail = AsyncMock()
    mock_session_fail.async_ensure_token_valid.side_effect = Exception(
        "OAuth refresh error"
    )

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.OAuth2Session",
            return_value=mock_session_fail,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


def _oauth_error(status: int) -> ClientResponseError:
    """Build a token endpoint error response."""
    return ClientResponseError(
        request_info=AsyncMock(),
        history=(),
        status=status,
        message="invalid_grant",
    )


@pytest.mark.asyncio
async def test_coordinator_oauth_token_revoked_triggers_reauth(hass, caplog):
    """A rejected refresh token must raise ConfigEntryAuthFailed, not UpdateFailed.

    Google answers a revoked or expired refresh token with 400 invalid_grant.
    Retrying can never recover from that, so the integration has to ask the user
    to re-consent instead of logging the same failure forever.
    """
    config = {**FAKE_CONFIG_DATA, "auth_type": "oauth2_google"}
    entry = MockConfigEntry(domain="mail_and_packages", data=config)
    entry.add_to_hass(hass)

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)
        coordinator.config_entry = entry

    mock_session = AsyncMock()
    mock_session.async_ensure_token_valid.side_effect = _oauth_error(
        HTTPStatus.BAD_REQUEST
    )

    # Cached data must not mask the auth failure.
    coordinator._data = {"cached": True}

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.OAuth2Session",
            return_value=mock_session,
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()

    # The underlying reason must be visible without enabling debug logging.
    assert "invalid_grant" in caplog.text
    assert "Reauthentication is required" in caplog.text


@pytest.mark.asyncio
async def test_coordinator_oauth_token_server_error_is_retryable(hass):
    """A 5xx from the token endpoint is transient and must stay UpdateFailed."""
    config = {**FAKE_CONFIG_DATA, "auth_type": "oauth2_google"}
    entry = MockConfigEntry(domain="mail_and_packages", data=config)
    entry.add_to_hass(hass)

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)
        coordinator.config_entry = entry

    mock_session = AsyncMock()
    mock_session.async_ensure_token_valid.side_effect = _oauth_error(
        HTTPStatus.INTERNAL_SERVER_ERROR
    )

    coordinator._data = {}

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.OAuth2Session",
            return_value=mock_session,
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_process_emails_copy_external_images_error(hass, caplog):
    """Test process_emails handles copy_images OSError/ValueError gracefully."""
    config = {**FAKE_CONFIG_DATA, "allow_external": True}
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.copy_images",
            side_effect=OSError("Copy error"),
        ),
    ):
        await coordinator.process_emails(hass, config)

    assert "Problem creating: Copy error" in caplog.text


@pytest.mark.asyncio
async def test_coordinator_get_imap_connection_folder_failures(hass):
    """Test _get_imap_connection folder selection exception and invalid folder return."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # 1. Folder selection exception
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            side_effect=Exception("IMAP select error"),
        ),
        pytest.raises(UpdateFailed, match="Folder selection failed: IMAP select error"),
    ):
        await coordinator._get_imap_connection(
            {**FAKE_CONFIG_DATA, CONF_FOLDER: "INBOX"}
        )

    # 2. Folder selection returns False
    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=False,
        ),
        pytest.raises(UpdateFailed, match="Folder selection failed: INBOX"),
    ):
        await coordinator._get_imap_connection(
            {**FAKE_CONFIG_DATA, CONF_FOLDER: "INBOX"}
        )


@pytest.mark.asyncio
async def test_coordinator_get_imap_connection_deletes_auth_failed_issue(hass):
    """Test _get_imap_connection deletes auth_failed issue if present."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # Pre-register issue in registry
    issue_registry = ir.async_get(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        "auth_failed",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="auth_failed",
    )
    assert (DOMAIN, "auth_failed") in issue_registry.issues

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.login",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.selectfolder",
            return_value=True,
        ),
    ):
        await coordinator._get_imap_connection(
            {**FAKE_CONFIG_DATA, CONF_FOLDER: "INBOX"}
        )

    assert (DOMAIN, "auth_failed") not in issue_registry.issues


@pytest.mark.asyncio
async def test_coordinator_async_update_data_error_with_cached_data_and_auth_failed(
    hass,
):
    """Test _async_update_data re-raises ConfigEntryAuthFailed and returns cached data on generic error."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    # 1. ConfigEntryAuthFailed is re-raised
    with (
        patch.object(
            coordinator,
            "process_emails",
            AsyncMock(side_effect=ConfigEntryAuthFailed("Auth failed")),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()

    # 2. Generic Exception with pre-existing cached _data returns cached _data
    coordinator._data = {"cached": "value"}
    with patch.object(
        coordinator,
        "process_emails",
        AsyncMock(side_effect=Exception("Generic update error")),
    ):
        res = await coordinator._async_update_data()
        assert res == {"cached": "value"}


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_different_hash_and_post_de(hass):
    """Test _binary_sensor_update when image hash differs from none hash for USPS and post_de."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._data = {
        "usps_image": "mail_123.jpg",
        "post_de_image": "post_de_123.jpg",
    }

    # Mock image exists check and hash_file
    with (
        patch("anyio.Path.exists", return_value=True),
        patch(
            "custom_components.mail_and_packages.coordinator.hash_file",
            side_effect=["hash_a", "hash_b", "hash_c", "hash_d"],
        ),
    ):
        await coordinator._binary_sensor_update()

    assert coordinator._data.get("usps_update") is True
    assert coordinator._data.get("post_de_update") is True


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_same_hash_and_custom_img(hass):
    """Test _binary_sensor_update false branches for image hashes equal and custom image settings."""
    config = {
        **FAKE_CONFIG_DATA,
        "amazon_custom_img": True,
        "amazon_custom_img_file": "custom_amazon.jpg",
    }
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)

    coordinator._data = {
        "usps_image": "mail_123.jpg",
        "amazon_image": "amazon_123.jpg",
    }

    with (
        patch("anyio.Path.exists", return_value=True),
        patch.object(
            coordinator,
            "_get_file_hash_if_changed",
            AsyncMock(return_value="same_hash"),
        ),
    ):
        await coordinator._binary_sensor_update()

    assert coordinator._data.get("usps_update") is False
    assert coordinator._data.get("amazon_update") is False


@pytest.mark.asyncio
async def test_coordinator_oauth_token_refresh_client_response_error_non_400_401(
    hass,
):
    """Test client response error with non-400/401 status raises UpdateFailed (line 155)."""
    config = {**FAKE_CONFIG_DATA, "auth_type": "oauth2_google"}
    entry = MockConfigEntry(domain="mail_and_packages", data=config)
    entry.add_to_hass(hass)

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, config)
        coordinator.config_entry = entry

    mock_session = AsyncMock()
    mock_session.async_ensure_token_valid.side_effect = _oauth_error(
        HTTPStatus.BAD_GATEWAY
    )

    with (
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=AsyncMock(),
        ),
        patch(
            "custom_components.mail_and_packages.coordinator.config_entry_oauth2_flow.OAuth2Session",
            return_value=mock_session,
        ),
        pytest.raises(UpdateFailed, match="OAuth token refresh failed"),
    ):
        await coordinator._async_oauth_access_token("oauth2_google")


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_missing_image_attr_and_default_none_image(
    hass,
):
    """Test _binary_sensor_update when image attribute isn't in const (line 668) and standard default none image (line 704)."""
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(hass, FAKE_CONFIG_DATA)

    coordinator._data = {
        "ups_image": "ups_123.jpg",
    }

    with (
        patch(
            "custom_components.mail_and_packages.const.CAMERA_DATA",
            {"fake_camera": {}, "ups_camera": {}},
        ),
        patch("anyio.Path.exists", return_value=True),
        patch.object(
            coordinator,
            "_get_file_hash_if_changed",
            AsyncMock(side_effect=["hash_ups", "hash_none"]),
        ),
    ):
        await coordinator._binary_sensor_update()

    assert coordinator._data.get("ups_update") is True


def test_dedupe_marketplace_duplicates_etsy():
    """Marketplace packages already counted by a carrier shipper are dropped (Etsy)."""
    data = {
        "etsy_delivering": 2,
        "etsy_delivered": 0,
        "etsy_packages": 2,
        "capost_delivering": 1,
        "etsy_carrier_tracking": {
            "3869977574": "1234567890123456",
            "4106538106": "9999999999999999",
        },
    }
    tracking_details = {
        "etsy_delivering": ["3869977574", "4106538106"],
        "capost_delivering": ["1234567890123456"],
    }

    MailDataUpdateCoordinator._dedupe_marketplace_duplicates(data, tracking_details)

    # 3869977574's carrier number is counted by Canada Post -> dropped
    assert data["etsy_delivering"] == 1
    assert tracking_details["etsy_delivering"] == ["4106538106"]
    # computed etsy_packages follows
    assert data["etsy_packages"] == 1
    # carrier side untouched; mapping consumed
    assert data["capost_delivering"] == 1
    assert "etsy_carrier_tracking" not in data


def test_dedupe_marketplace_duplicates_shopify():
    """Marketplace packages already counted by a carrier shipper are dropped (Shopify)."""
    data = {
        "shopify_delivering": 2,
        "shopify_delivered": 0,
        "shopify_carrier_tracking": {
            "MC1605": "9443743716845537",
            "PP3024": "YT2434221266046281",
        },
    }
    tracking_details = {
        "shopify_delivering": ["MC1605", "PP3024"],
        "capost_delivering": ["9443743716845537"],
    }

    MailDataUpdateCoordinator._dedupe_marketplace_duplicates(data, tracking_details)

    # MC1605's carrier number is counted by Canada Post -> dropped
    assert data["shopify_delivering"] == 1
    assert tracking_details["shopify_delivering"] == ["PP3024"]
    # carrier side untouched; mapping consumed
    assert tracking_details["capost_delivering"] == ["9443743716845537"]
    assert "shopify_carrier_tracking" not in data


def test_dedupe_marketplace_no_carriers_is_noop():
    """Without carrier-side tracking the marketplace counts are untouched."""
    data = {
        "etsy_delivering": 1,
        "etsy_carrier_tracking": {"3869977574": "1234567890123456"},
    }
    tracking_details = {"etsy_delivering": ["3869977574"]}

    MailDataUpdateCoordinator._dedupe_marketplace_duplicates(data, tracking_details)

    assert data["etsy_delivering"] == 1
    assert tracking_details["etsy_delivering"] == ["3869977574"]
    assert "etsy_carrier_tracking" not in data


def test_dedupe_marketplace_empty_marketplace_carrier_tracking():
    """Empty MARKETPLACE_CARRIER_TRACKING returns early with no changes."""
    data = {"etsy_delivering": 1, "etsy_carrier_tracking": {"123": "456"}}
    tracking_details = {"etsy_delivering": ["123"]}

    with patch(
        "custom_components.mail_and_packages.coordinator.const.MARKETPLACE_CARRIER_TRACKING",
        {},
    ):
        MailDataUpdateCoordinator._dedupe_marketplace_duplicates(data, tracking_details)

    assert data["etsy_delivering"] == 1
    assert data["etsy_carrier_tracking"] == {"123": "456"}
