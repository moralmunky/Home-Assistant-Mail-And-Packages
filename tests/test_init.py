"""Tests for init."""

from unittest.mock import patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import DOMAIN
from tests.const import (
    FAKE_CONFIG_DATA,
    FAKE_CONFIG_DATA_AMAZON_FWD_STRING,
    FAKE_CONFIG_DATA_CUSTOM_IMG,
    FAKE_CONFIG_DATA_MISSING_TIMEOUT,
    FAKE_CONFIG_DATA_NO_PATH,
)


@pytest.mark.asyncio
async def test_unload_entry(hass, integration, mock_update, mock_copy_overlays):
    """Test unloading entities."""
    entry = integration

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 48
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 48
    assert len(hass.states.async_entity_ids(DOMAIN)) == 0

    assert await hass.config_entries.async_remove(entries[0].entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


@pytest.mark.asyncio
async def test_setup_entry(
    hass,
    integration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test settting up entities."""
    entry = integration

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 48
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_no_path_no_sec(
    hass,
    integration_no_path,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test settting up entities."""
    entry = integration_no_path

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 43
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_missing_imap_timeout(
    hass,
    integration_no_timeout,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test settting up entities."""
    entry = integration_no_timeout

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 42
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_amazon_fwds_string(
    hass,
    integration_fwd_string,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test settting up entities."""
    entry = integration_fwd_string

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 42
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_custom_img(
    hass,
    integration_custom_img,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test settting up entities."""
    entry = integration_custom_img

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 43
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

@pytest.mark.asyncio
async def test_v4_migration(
    hass,
    integration_v4_migration,
    mock_imap_no_email,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test settting up entities."""
    entry = integration_v4_migration

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 42
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1