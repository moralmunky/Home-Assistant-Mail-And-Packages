"""PledgeBox / 4PX patterns from a redacted real-message example.

PledgeBox is a crowdfunding pledge manager, not a carrier: its
"Shipping Update" emails relay the tracking code the creator uploaded
for the physical courier named in the body. The genuine sample on file
is an in-transit notice carried by 4PX. All names, addresses, project
details and tracking identifiers here are synthetic, in the genuine
formats, not copied from mail.
"""

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    FOURPX_TRACKING_PATTERN,
    MARKETPLACE_CARRIER_TRACKING,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
)
from custom_components.mail_and_packages.coordinator import (
    MailDataUpdateCoordinator,
)
from custom_components.mail_and_packages.coordinator.helpers import (
    aggregate_package_counts,
)
from custom_components.mail_and_packages.coordinator.tracking import (
    apply_tracking_state,
    attribute_fourpx_pledgebox_packages,
    dedupe_marketplace_duplicates,
)
from custom_components.mail_and_packages.shippers import get_shipper_for_sensor
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from custom_components.mail_and_packages.summary import (
    _total_identifiers,
    deduplicated_count,
)
from tests.conftest import _generate_fetch_side_effect, _generate_search_side_effect

FOURPX_CODE = "4PX1000000000001CN"
UPS_CODE = "1Z9999999999999999"
FEDEX_CODE = "999999999999"


# ---------------------------------------------------------------------------
# Sensor registration
# ---------------------------------------------------------------------------


def test_pledgebox_and_fourpx_registered():
    """Both prefixes are known shippers with a complete sensor set."""
    assert "pledgebox" in SHIPPERS
    assert "fourpx" in SHIPPERS
    for prefix in ("pledgebox", "fourpx"):
        for suffix in ("delivering", "packages", "tracking"):
            assert f"{prefix}_{suffix}" in SENSOR_DATA
        for suffix in ("delivering", "packages"):
            assert f"{prefix}_{suffix}" in SENSOR_TYPES


def test_no_delivered_sensor_without_a_sample():
    """No delivered state is invented: no genuine delivered sample exists."""
    for prefix in ("pledgebox", "fourpx"):
        assert f"{prefix}_delivered" not in SENSOR_DATA
        assert f"{prefix}_delivered" not in SENSOR_TYPES


def test_pledgebox_delivering_config_matches_sample():
    """The delivering search is exactly the sample-backed sender/subject/body."""
    config = SENSOR_DATA["pledgebox_delivering"]
    assert config["email"] == ["none-reply@survey.pledgebox.com"]
    assert config["subject"] == ["Shipping Update"]
    assert config["body"] == ["In Transit"]
    assert SENSOR_DATA["pledgebox_packages"] == {}


def test_fourpx_performs_no_search_of_its_own():
    """4PX has no sample-backed direct email format, so it never searches."""
    assert SENSOR_DATA["fourpx_delivering"] == {}
    assert SENSOR_DATA["fourpx_packages"] == {}


def test_pledgebox_and_fourpx_use_generic_shipper():
    """Both prefixes resolve to the generic shipper in the registry."""
    hass = MagicMock()
    for sensor in (
        "pledgebox_delivering",
        "pledgebox_packages",
        "fourpx_delivering",
        "fourpx_packages",
    ):
        shipper = get_shipper_for_sensor(hass, {}, sensor)
        assert isinstance(shipper, GenericShipper)


# ---------------------------------------------------------------------------
# Tracking patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (f"Tracking Code\n{FOURPX_CODE}", FOURPX_CODE),
        (f"Tracking Code: {UPS_CODE}", UPS_CODE),
        (f"Tracking Code\n{FEDEX_CODE}", FEDEX_CODE),
        ("Tracking Code\n" + "9" * 22, "9" * 22),
    ],
)
def test_pledgebox_tracking_pattern_extracts_courier_number(body, expected):
    """The label-anchored pattern extracts whatever courier number follows."""
    pattern = SENSOR_DATA["pledgebox_tracking"]["pattern"][0]
    found = re.search(pattern, body)
    assert found is not None and found.group(1) == expected
    # The marketplace carrier extraction anchors on the same label.
    carrier = re.search(MARKETPLACE_CARRIER_TRACKING["pledgebox"], body, re.IGNORECASE)
    assert carrier is not None and carrier.group(1) == expected


@pytest.mark.parametrize(
    "body",
    [
        "Tracking Code\nSHORT12",  # below the 8-character minimum
        f"Your code is {FOURPX_CODE}",  # no "Tracking Code" label
        "Tracking Code",  # label with no number at all
        "",
    ],
)
def test_pledgebox_tracking_pattern_rejects_unlabelled_or_short(body):
    """Unlabelled numbers and too-short tokens are not tracking codes."""
    pattern = SENSOR_DATA["pledgebox_tracking"]["pattern"][0]
    assert re.search(pattern, body) is None


def test_fourpx_pattern_fullmatch():
    """FOURPX_TRACKING_PATTERN matches the genuine format in full only."""
    pattern = re.compile(FOURPX_TRACKING_PATTERN)
    assert pattern.fullmatch(FOURPX_CODE)
    assert SENSOR_DATA["fourpx_tracking"]["pattern"] == [f"({FOURPX_TRACKING_PATTERN})"]


@pytest.mark.parametrize(
    "token",
    [
        "4PX100000000001CN",  # 12 digits: too short
        "4PX10000000000001CN",  # 14 digits: too long
        "4PX1000000000001US",  # wrong origin suffix
        "4px1000000000001cn",  # the genuine format is upper case
        f"X{FOURPX_CODE}",  # 4PX-shaped substring of a longer token
        f"{FOURPX_CODE}7",  # trailing digit makes a different token
        UPS_CODE,
        "",
    ],
)
def test_fourpx_pattern_rejects_lookalikes(token):
    """Lookalike tokens must never attribute a package to 4PX."""
    assert re.compile(FOURPX_TRACKING_PATTERN).fullmatch(token) is None


# ---------------------------------------------------------------------------
# Generic shipper parsing of the sanitized genuine samples
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pledgebox_in_transit_4px(hass, mock_imap_pledgebox_in_transit):
    """The 4PX sample counts once, with its code and carrier mapping."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(
        mock_imap_pledgebox_in_transit, "today", "pledgebox_delivering"
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [FOURPX_CODE]
    assert result["pledgebox_carrier_tracking"] == {FOURPX_CODE: FOURPX_CODE}


@pytest.mark.asyncio
async def test_pledgebox_in_transit_ups(hass, mock_imap_pledgebox_in_transit_ups):
    """A non-4PX courier's code is extracted the same way."""
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(
        mock_imap_pledgebox_in_transit_ups, "today", "pledgebox_delivering"
    )
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [UPS_CODE]
    assert result["pledgebox_carrier_tracking"] == {UPS_CODE: UPS_CODE}


@pytest.mark.asyncio
async def test_pledgebox_duplicate_emails_count_once(
    hass, mock_imap_pledgebox_in_transit
):
    """Two PledgeBox emails for the same code are one package."""
    mock_imap = mock_imap_pledgebox_in_transit
    mock_imap.search = AsyncMock(return_value=MagicMock(result="OK", lines=[b"1 2"]))
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1 2"])
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(mock_imap, "today", "pledgebox_delivering")
    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [FOURPX_CODE]


def _raw_pledgebox_email(subject: str, body: str) -> str:
    return (
        "From: PledgeBox <none-reply@survey.pledgebox.com>\r\n"
        "To: redacted@example.com\r\n"
        f"Subject: {subject}\r\n"
        "Date: Tue, 10 Nov 2026 17:38:38 -0800\r\n"
        "MIME-Version: 1.0\r\n"
        "Content-Type: text/plain; charset=UTF-8\r\n\r\n"
        f"{body}\r\n"
    )


@pytest.mark.asyncio
async def test_pledgebox_shipping_update_without_in_transit_body(hass, mock_imap):
    """A Shipping Update without the in-transit status does not count."""
    raw = _raw_pledgebox_email(
        "Shipping Update",
        "Your pledge survey is ready.\r\nTracking Code\r\n" + FOURPX_CODE,
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.search.side_effect = _generate_search_side_effect()
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(raw)
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(mock_imap, "today", "pledgebox_delivering")
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []


@pytest.mark.asyncio
async def test_pledgebox_other_subject_does_not_count(hass, mock_imap):
    """PledgeBox mail with a different subject is not a shipping update."""
    raw = _raw_pledgebox_email(
        "Your PledgeBox survey",
        "In Transit\r\nTracking Code\r\n" + FOURPX_CODE,
    )
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.uid.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_imap.search.side_effect = _generate_search_side_effect()
    mock_imap.fetch.side_effect = _generate_fetch_side_effect(raw)
    shipper = GenericShipper(hass, {"image_path": "test/path/"})
    result = await shipper.process(mock_imap, "today", "pledgebox_delivering")
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []


@pytest.mark.asyncio
async def test_fourpx_delivering_skips_imap_search(hass, caplog):
    """The attributed-only 4PX sensor returns zero without searching."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()
    result = await shipper.process(mock_account, "today", "fourpx_delivering")
    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []
    mock_account.search.assert_not_called()
    assert (
        "Skipping email search for fourpx_delivering: no email addresses configured"
        in caplog.text
    )


# ---------------------------------------------------------------------------
# 4PX attribution (coordinator)
# ---------------------------------------------------------------------------


def _attribution_data():
    return {
        "pledgebox_delivering": 1,
        "pledgebox_packages": 1,
        "fourpx_delivering": 0,
        "fourpx_packages": 0,
        "pledgebox_carrier_tracking": {FOURPX_CODE: FOURPX_CODE},
    }


def test_attribute_fourpx_pledgebox_delivering():
    """A PledgeBox package with a 4PX number moves to 4PX."""
    data = _attribution_data()
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE]}

    MailDataUpdateCoordinator._attribute_fourpx_pledgebox_packages(
        data, tracking_details
    )

    assert data["pledgebox_delivering"] == 0
    assert data["pledgebox_packages"] == 0
    assert data["fourpx_delivering"] == 1
    assert data["fourpx_packages"] == 1
    assert tracking_details["fourpx_delivering"] == [FOURPX_CODE]
    # The PledgeBox id stays until the dedup pass removes it.
    assert tracking_details["pledgebox_delivering"] == [FOURPX_CODE]


def test_attribute_then_dedupe_counts_fourpx_package_once():
    """Pipeline order: attribution moves it, dedup drops the PledgeBox copy."""
    data = _attribution_data()
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE]}

    MailDataUpdateCoordinator._attribute_fourpx_pledgebox_packages(
        data, tracking_details
    )
    MailDataUpdateCoordinator._dedupe_marketplace_duplicates(data, tracking_details)

    assert data["pledgebox_delivering"] == 0
    assert data["fourpx_delivering"] == 1
    assert tracking_details["pledgebox_delivering"] == []
    assert tracking_details["fourpx_delivering"] == [FOURPX_CODE]
    assert "pledgebox_carrier_tracking" not in data


def test_full_pipeline_tracking_state_counts_once():
    """After attribution + dedup + tracking state, totals count one package."""
    data = _attribution_data()
    data["zpackages_transit"] = 0
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE]}

    attribute_fourpx_pledgebox_packages(data, tracking_details)
    dedupe_marketplace_duplicates(data, tracking_details)
    apply_tracking_state({}, data, tracking_details, "2026-11-10", 14)
    aggregate_package_counts(data)

    assert data["fourpx_delivering"] == 1
    assert data["fourpx_tracking"] == [FOURPX_CODE]
    assert data["fourpx_packages"] == 1
    assert data["pledgebox_delivering"] == 0
    assert data["pledgebox_tracking"] == []
    assert data["zpackages_transit"] == 1


def test_attribute_fourpx_two_packages():
    """Two different 4PX packages both move."""
    other = "4PX2000000000002CN"
    data = _attribution_data()
    data["pledgebox_delivering"] = 2
    data["pledgebox_packages"] = 2
    data["pledgebox_carrier_tracking"] = {FOURPX_CODE: FOURPX_CODE, other: other}
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE, other]}

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["pledgebox_delivering"] == 0
    assert data["pledgebox_packages"] == 0
    assert data["fourpx_delivering"] == 2
    assert data["fourpx_packages"] == 2
    assert tracking_details["fourpx_delivering"] == [FOURPX_CODE, other]


def test_attribute_fourpx_carrier_record_wins():
    """When 4PX already holds the number, attribution leaves it alone."""
    data = _attribution_data()
    data["fourpx_delivering"] = 1
    data["fourpx_packages"] = 1
    tracking_details = {
        "pledgebox_delivering": [FOURPX_CODE],
        "fourpx_delivering": [FOURPX_CODE],
    }

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["pledgebox_delivering"] == 1
    assert data["fourpx_delivering"] == 1
    assert tracking_details["fourpx_delivering"] == [FOURPX_CODE]

    # The dedup pass then drops the PledgeBox copy: counted once.
    dedupe_marketplace_duplicates(data, tracking_details)
    assert data["pledgebox_delivering"] == 0
    assert data["fourpx_delivering"] == 1


def test_attribute_fourpx_second_source_defers():
    """A second mapping for the same 4PX number does not move twice."""
    data = _attribution_data()
    data["pledgebox_delivering"] = 2
    data["pledgebox_packages"] = 2
    data["pledgebox_carrier_tracking"] = {
        FOURPX_CODE: FOURPX_CODE,
        "OTHERID": FOURPX_CODE,
    }
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE, "OTHERID"]}

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["fourpx_delivering"] == 1
    assert data["pledgebox_delivering"] == 1
    assert tracking_details["fourpx_delivering"] == [FOURPX_CODE]


@pytest.mark.parametrize(
    "carrier_num",
    [
        UPS_CODE,  # a different courier's number stays with PledgeBox
        FEDEX_CODE,
        f"{FOURPX_CODE}7",  # 4PX-shaped substring of a longer token
        f"X{FOURPX_CODE}",
    ],
)
def test_attribute_fourpx_other_numbers_do_not_move(carrier_num):
    """Non-4PX numbers are not attributed to 4PX."""
    data = _attribution_data()
    data["pledgebox_carrier_tracking"] = {carrier_num: carrier_num}
    tracking_details = {"pledgebox_delivering": [carrier_num]}

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["pledgebox_delivering"] == 1
    assert data["pledgebox_packages"] == 1
    assert data["fourpx_delivering"] == 0
    assert "fourpx_delivering" not in tracking_details


def test_attribute_fourpx_no_mapping_is_noop():
    """Without a usable carrier mapping nothing moves."""
    data = {
        "pledgebox_delivering": 1,
        "pledgebox_carrier_tracking": ["not-a-dict"],
        "fourpx_delivering": 0,
    }
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE]}

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["pledgebox_delivering"] == 1
    assert data["fourpx_delivering"] == 0
    assert "fourpx_delivering" not in tracking_details

    data = {"pledgebox_delivering": 1, "fourpx_delivering": 0}
    attribute_fourpx_pledgebox_packages(data, tracking_details)
    assert data["pledgebox_delivering"] == 1
    assert data["fourpx_delivering"] == 0


def test_attribute_fourpx_unlisted_state_does_not_move():
    """A mapped number whose package is not in the delivering list stays."""
    data = _attribution_data()
    tracking_details = {"pledgebox_delivering": []}

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["pledgebox_delivering"] == 1
    assert data["pledgebox_packages"] == 1
    assert data["fourpx_delivering"] == 0
    assert data["fourpx_packages"] == 0
    assert "fourpx_delivering" not in tracking_details


def test_attribute_fourpx_without_count_keys():
    """Attribution still records 4PX tracking when count keys are absent."""
    data = {
        "fourpx_delivering": 0,
        "pledgebox_carrier_tracking": {FOURPX_CODE: FOURPX_CODE},
    }
    tracking_details = {"pledgebox_delivering": [FOURPX_CODE]}

    attribute_fourpx_pledgebox_packages(data, tracking_details)

    assert data["fourpx_delivering"] == 1
    assert "pledgebox_delivering" not in data
    assert "pledgebox_packages" not in data
    assert "fourpx_packages" not in data
    assert tracking_details["fourpx_delivering"] == [FOURPX_CODE]


def test_attribute_fourpx_totals_stay_consistent():
    """Moved packages keep the per-prefix totals aggregation consumes."""
    data = _attribution_data()

    attribute_fourpx_pledgebox_packages(data, {"pledgebox_delivering": [FOURPX_CODE]})

    assert data["pledgebox_delivering"] + data["fourpx_delivering"] == 1
    assert data["fourpx_packages"] == data["fourpx_delivering"]


# ---------------------------------------------------------------------------
# Duplicates: PledgeBox vs a carrier shipper reporting the same number
# ---------------------------------------------------------------------------


def test_pledgebox_ups_duplicate_carrier_wins():
    """UPS reporting the same number drops the PledgeBox copy."""
    data = {
        "pledgebox_delivering": 1,
        "pledgebox_packages": 1,
        "ups_delivering": 1,
        "pledgebox_carrier_tracking": {UPS_CODE: UPS_CODE},
    }
    tracking_details = {
        "pledgebox_delivering": [UPS_CODE],
        "ups_delivering": [UPS_CODE],
    }

    # Not a 4PX number, so attribution does not move it first.
    attribute_fourpx_pledgebox_packages(data, tracking_details)
    assert data["pledgebox_delivering"] == 1

    dedupe_marketplace_duplicates(data, tracking_details)
    assert data["pledgebox_delivering"] == 0
    assert data["pledgebox_packages"] == 0
    assert tracking_details["pledgebox_delivering"] == []
    assert data["ups_delivering"] == 1


def test_pledgebox_number_without_carrier_report_stays():
    """A PledgeBox package no carrier reports stays under PledgeBox."""
    data = {
        "pledgebox_delivering": 1,
        "pledgebox_packages": 1,
        "pledgebox_carrier_tracking": {UPS_CODE: UPS_CODE},
    }
    tracking_details = {"pledgebox_delivering": [UPS_CODE]}

    dedupe_marketplace_duplicates(data, tracking_details)

    assert data["pledgebox_delivering"] == 1
    assert data["pledgebox_packages"] == 1
    assert tracking_details["pledgebox_delivering"] == [UPS_CODE]


def test_summary_identifiers_include_fourpx_and_pledgebox():
    """Cross-mailbox totals see both prefixes' tracking identifiers."""
    data = {"fourpx_tracking": [FOURPX_CODE], "pledgebox_tracking": [UPS_CODE]}
    assert _total_identifiers(data, "zpackages_transit") == {FOURPX_CODE, UPS_CODE}
    # And the same number reported by two mailboxes counts once there.
    assert deduplicated_count([1, 1], [{FOURPX_CODE}, {FOURPX_CODE}]) == 1
