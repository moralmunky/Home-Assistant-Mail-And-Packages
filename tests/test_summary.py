"""Tests for the combined "All mailboxes" summary."""

import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_RESOURCES, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages import (
    _async_mailboxes_changed,
    async_remove_config_entry_device,
    update_listener,
)
from custom_components.mail_and_packages.config_flow import (
    MailAndPackagesFlowHandler,
)
from custom_components.mail_and_packages.const import (
    AMAZON_ORDER,
    CONF_ENTRY_TYPE,
    CONFIG_VER,
    DOMAIN,
    ENTRY_TYPE_SUMMARY,
    SIGNAL_MAILBOX_UPDATED,
    SUMMARY_UNIQUE_ID,
)
from custom_components.mail_and_packages.diagnostics import (
    async_get_device_diagnostics,
)
from custom_components.mail_and_packages.summary import (
    _as_datetime,
    _as_int,
    _identifiers,
    combine,
    deduplicated_count,
    is_summary_entry,
    loaded_mailbox_data,
    mailbox_entries,
    summary_entry,
    summary_keys,
    tracking_key,
)

RESOURCES = [
    "amazon_packages",
    "mail_updated",
    "ups_delivered",
    "ups_delivering",
    "usps_mail",
    "zpackages_transit",
]

MAILBOX_A = {
    "usps_mail": 2,
    "ups_delivering": 2,
    "ups_tracking": ["1Z1", "1Z2"],
    "ups_delivered": 1,
    "ups_delivered_tracking": ["1Z9"],
    "zpackages_transit": 3,
    "amazon_packages": 1,
    AMAZON_ORDER: ["111-1"],
    "mail_updated": dt.datetime(2026, 10, 13, 10, 0, tzinfo=dt.UTC),
}

MAILBOX_B = {
    "usps_mail": 1,
    "ups_delivering": 1,
    "ups_tracking": ["1Z2"],
    "ups_delivered": 1,
    "ups_delivered_tracking": ["1Z9"],
    "zpackages_transit": 1,
    "amazon_packages": 1,
    AMAZON_ORDER: ["111-1"],
    "mail_updated": "2026-10-13T11:00:00",
}


def _add_mailbox(
    hass: HomeAssistant,
    username: str,
    data: dict,
    resources: list[str] | None = None,
) -> MockConfigEntry:
    """Add a loaded mailbox entry whose coordinator holds data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Mail and Packages ({username})",
        data={
            CONF_HOST: "imap.example.com",
            CONF_USERNAME: username,
            CONF_RESOURCES: RESOURCES if resources is None else resources,
        },
        version=CONFIG_VER,
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(coordinator=SimpleNamespace(data=dict(data)))
    return entry


def _add_summary(hass: HomeAssistant, version: int = CONFIG_VER) -> MockConfigEntry:
    """Add a summary entry that is not set up yet."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mail and Packages (All mailboxes)",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_SUMMARY},
        unique_id=SUMMARY_UNIQUE_ID,
        version=version,
    )
    entry.add_to_hass(hass)
    return entry


def _state(hass: HomeAssistant, summary: MockConfigEntry, key: str):
    """Return the state object of one summary sensor."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"summary_{key}_{summary.entry_id}"
    )
    assert entity_id is not None, key
    return hass.states.get(entity_id)


@pytest.fixture
async def summary_setup(hass):
    """Two loaded mailboxes and a set up summary entry (migrated from v1)."""
    mailbox_a = _add_mailbox(hass, "a@example.com", MAILBOX_A)
    mailbox_b = _add_mailbox(hass, "b@example.com", MAILBOX_B)
    summary = _add_summary(hass, version=1)
    assert await hass.config_entries.async_setup(summary.entry_id)
    await hass.async_block_till_done()
    return mailbox_a, mailbox_b, summary


# Pure helpers


def test_tracking_key():
    """Each sensor reads identifiers from the same key PackagesSensor uses."""
    assert tracking_key("amazon_packages") == AMAZON_ORDER
    assert tracking_key("ups_delivering") == "ups_tracking"
    assert tracking_key("ups_delivered") == "ups_delivered_tracking"
    assert tracking_key("fedex") == "fedex_tracking"


def test_identifiers_ignore_junk():
    """Only non-empty list values count as identifiers."""
    assert _identifiers({"k": "1Z1"}, "k") == set()
    assert _identifiers({}, "k") == set()
    assert _identifiers({"k": [" 1Z1 ", "", "  ", 42]}, "k") == {"1Z1", "42"}


def test_deduplicated_count():
    """Shared identifiers count once; the result stays within sane bounds."""
    assert deduplicated_count([], []) == 0
    assert deduplicated_count([2, 1], [{"a", "b"}, {"b"}]) == 2
    assert deduplicated_count([3, 2], [set(), set()]) == 5
    # Never below the largest single mailbox count.
    assert deduplicated_count([1, 1], [{"a", "b"}, {"a", "b"}]) == 1


def test_as_int_and_as_datetime():
    """Values that are not counts or timestamps are ignored."""
    assert _as_int(True) is None
    assert _as_int("5") is None
    assert _as_int(-3) == 0
    assert _as_int(2.7) == 2
    aware = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    assert _as_datetime(aware) == aware
    assert _as_datetime(dt.datetime(2026, 1, 1)) == aware
    assert _as_datetime("2026-01-01T00:00:00+00:00") == aware
    assert _as_datetime("not a date") is None
    assert _as_datetime(5) is None


def test_combine_without_data():
    """A sensor no mailbox reports has no value."""
    assert combine("usps_mail", {"a": {}}) == (None, {})
    assert combine("mail_updated", {"a": {"mail_updated": None}}) == (None, {})


def test_combine_totals_count_shared_packages_once():
    """Cross shipper totals use every shipper's identifiers."""
    value, attributes = combine("zpackages_transit", {"a": MAILBOX_A, "b": MAILBOX_B})
    # 3 + 1 with 1Z2 and the Amazon order in both mailboxes, but never
    # below the largest single mailbox count.
    assert value == 3
    assert attributes["mailboxes"] == {"a": 3, "b": 1}
    assert attributes["tracking_#"] == ["111-1", "1Z1", "1Z2"]


def test_entry_helpers(hass):
    """Mailbox and summary entries are told apart."""
    mailbox = _add_mailbox(hass, "a@example.com", MAILBOX_A)
    _add_mailbox(hass, "b@example.com", {}, resources=["usps_mail", "unknown"])
    assert summary_entry(hass) is None
    summary = _add_summary(hass)
    assert is_summary_entry(summary)
    assert not is_summary_entry(mailbox)
    assert summary_entry(hass) is summary
    assert summary not in mailbox_entries(hass)
    assert summary_keys(hass, ["usps_mail", "ups_delivered"]) == {
        "usps_mail",
        "ups_delivered",
    }


def test_loaded_mailbox_data_skips_unloaded_and_missing(hass):
    """Only loaded mailboxes with coordinator data are combined."""
    _add_mailbox(hass, "a@example.com", MAILBOX_A)
    unloaded = _add_mailbox(hass, "b@example.com", MAILBOX_B)
    unloaded.mock_state(hass, ConfigEntryState.NOT_LOADED)
    no_data = _add_mailbox(hass, "c@example.com", {})
    no_data.runtime_data = SimpleNamespace(coordinator=SimpleNamespace(data=None))
    assert list(loaded_mailbox_data(hass)) == ["a@example.com"]


# Summary entry setup and sensors


async def test_summary_sensors(hass, summary_setup):
    """The summary combines both mailboxes, counting shared packages once."""
    _, _, summary = summary_setup
    assert summary.state is ConfigEntryState.LOADED
    assert summary.version == CONFIG_VER

    usps = _state(hass, summary, "usps_mail")
    assert usps.state == "3"
    assert usps.attributes["mailboxes"] == {"a@example.com": 2, "b@example.com": 1}
    assert "tracking_#" not in usps.attributes

    delivering = _state(hass, summary, "ups_delivering")
    assert delivering.state == "2"
    assert delivering.attributes["tracking_#"] == ["1Z1", "1Z2"]

    assert _state(hass, summary, "ups_delivered").state == "1"
    assert _state(hass, summary, "amazon_packages").state == "1"
    assert _state(hass, summary, "zpackages_transit").state == "3"
    assert _state(hass, summary, "mail_updated").state == "2026-10-13T11:00:00+00:00"


async def test_summary_recalculates_on_mailbox_update(hass, summary_setup):
    """A mailbox refresh updates the totals; no loaded mailbox means unavailable."""
    mailbox_a, mailbox_b, summary = summary_setup

    mailbox_b.runtime_data.coordinator.data["usps_mail"] = 5
    async_dispatcher_send(hass, SIGNAL_MAILBOX_UPDATED)
    await hass.async_block_till_done()
    assert _state(hass, summary, "usps_mail").state == "7"

    mailbox_a.mock_state(hass, ConfigEntryState.NOT_LOADED)
    mailbox_b.mock_state(hass, ConfigEntryState.NOT_LOADED)
    async_dispatcher_send(hass, SIGNAL_MAILBOX_UPDATED)
    await hass.async_block_till_done()
    assert _state(hass, summary, "usps_mail").state == "unavailable"


async def test_mailboxes_changed_refreshes_or_reloads_summary(hass, summary_setup):
    """Same sensor types refresh the totals; new types reload the summary."""
    mailbox_a, _, summary = summary_setup

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        _async_mailboxes_changed(hass)
        reload.assert_not_called()

        hass.config_entries.async_update_entry(
            mailbox_a,
            options={CONF_RESOURCES: [*RESOURCES, "fedex_delivered"]},
        )
        _async_mailboxes_changed(hass)
        reload.assert_called_once_with(summary.entry_id)


async def test_mailboxes_changed_ignores_unloaded_summary(hass):
    """Nothing happens while the summary entry is not loaded."""
    _add_mailbox(hass, "a@example.com", MAILBOX_A)
    _add_mailbox(hass, "b@example.com", MAILBOX_B)
    _add_summary(hass)
    with (
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
        patch.object(hass.config_entries.flow, "async_init") as flow_init,
    ):
        _async_mailboxes_changed(hass)
    reload.assert_not_called()
    flow_init.assert_not_called()


async def test_summary_listener_device_and_diagnostics(hass, summary_setup):
    """The summary skips reloads, allows device removal and has diagnostics."""
    _, _, summary = summary_setup
    with patch.object(hass.config_entries, "async_reload") as reload:
        assert await update_listener(hass, summary) is None
    reload.assert_not_called()

    device = MagicMock()
    assert await async_remove_config_entry_device(hass, summary, device) is True
    assert await async_get_device_diagnostics(hass, summary, device) == {
        "summary_sensors": RESOURCES
    }


# Config flow


async def test_summary_has_no_options(hass):
    """Only mailboxes get an options flow."""
    mailbox = _add_mailbox(hass, "a@example.com", MAILBOX_A)
    summary = _add_summary(hass)
    assert MailAndPackagesFlowHandler.async_supports_options_flow(mailbox)
    assert not MailAndPackagesFlowHandler.async_supports_options_flow(summary)


async def test_discovery_needs_two_mailboxes(hass):
    """The summary is not offered for a single mailbox."""
    _add_mailbox(hass, "a@example.com", MAILBOX_A)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "summary_needs_mailboxes"


async def test_discovery_creates_summary(hass):
    """Confirming the discovered summary creates the entry."""
    _add_mailbox(hass, "a@example.com", MAILBOX_A)
    _add_mailbox(hass, "b@example.com", MAILBOX_B)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "summary_confirm"
    assert result["description_placeholders"] == {"count": "2"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mail and Packages (All mailboxes)"
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_SUMMARY}


async def test_unignore_offers_summary_again(hass):
    """The unignore step offers the summary again."""
    _add_mailbox(hass, "a@example.com", MAILBOX_A)
    _add_mailbox(hass, "b@example.com", MAILBOX_B)
    flow = MailAndPackagesFlowHandler()
    flow.hass = hass
    flow.context = {"source": config_entries.SOURCE_INTEGRATION_DISCOVERY}
    result = await flow.async_step_unignore({"unique_id": SUMMARY_UNIQUE_ID})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "summary_confirm"


async def test_summary_cannot_be_reconfigured(hass):
    """The summary has nothing to reconfigure."""
    summary = _add_summary(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": summary.entry_id,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "summary_not_configurable"
