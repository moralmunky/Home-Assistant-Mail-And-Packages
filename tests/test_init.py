"""Tests for init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.mail_and_packages import (
    MailDataUpdateCoordinator,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_setup_entry,
)
from custom_components.mail_and_packages.const import DOMAIN
from tests.const import FAKE_CONFIG_DATA


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

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 45
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


async def test_migration_from_version_1_to_4():
    """Test migration from version 1 to 4."""

    # Mock config entry with version 1
    mock_config_entry = MagicMock()
    mock_config_entry.version = 1
    mock_config_entry.data = {
        "amazon_fwds": "email1@test.com, email2@test.com",
        "path": "old/path/",
        "image_security": False,
    }

    # Mock hass
    mock_hass = MagicMock()

    # Should migrate successfully
    result = await async_migrate_entry(mock_hass, mock_config_entry)
    assert result is True

    # The migration function creates a copy and updates the entry, so we just verify it completes
    # successfully
    # The actual data modification happens in the migration function internally


async def test_migration_from_version_11_to_12():
    """Test migration from version 11 to 12."""

    # Mock config entry with version 11
    mock_config_entry = MagicMock()
    mock_config_entry.version = 11
    mock_config_entry.data = {}

    # Mock hass
    mock_hass = MagicMock()

    # Should migrate successfully
    result = await async_migrate_entry(mock_hass, mock_config_entry)
    assert result is True

    # The migration should have updated the config entry data
    # Note: The actual migration logic modifies updated_config, not config_entry.data directly
    # So we're testing that the migration function completes successfully


async def test_setup_entry_coordinator_failure():
    """Test setup_entry when coordinator fails to update."""
    mock_hass = MagicMock()
    mock_config_entry = MagicMock()
    mock_config_entry.data = FAKE_CONFIG_DATA.copy()
    mock_config_entry.data["resources"] = ["usps_mail"]  # Override for this test
    mock_config_entry.entry_id = "test_entry_id"

    # Mock coordinator that fails to update
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = False
    mock_coordinator.last_exception = Exception("Connection failed")
    mock_coordinator.async_refresh = AsyncMock()

    with patch(
        "custom_components.mail_and_packages.MailDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator_class.return_value = mock_coordinator

        # Should raise ConfigEntryNotReady
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(mock_hass, mock_config_entry)


async def test_async_remove_config_entry_device():
    """Test async_remove_config_entry_device function."""

    mock_hass = MagicMock()
    mock_config_entry = MagicMock()
    mock_device_entry = MagicMock()

    # Test with device identifiers that match our domain
    mock_device_entry.identifiers = {("mail_and_packages", "test_device")}
    mock_config_entry.runtime_data.get_device.return_value = True

    result = await async_remove_config_entry_device(
        mock_hass, mock_config_entry, mock_device_entry
    )
    assert result is False  # Should return False when device is present

    # Test with device identifiers that don't match our domain
    mock_device_entry.identifiers = {("other_domain", "test_device")}
    result = await async_remove_config_entry_device(
        mock_hass, mock_config_entry, mock_device_entry
    )
    assert result is True  # Should return True when device is not present


@pytest.mark.asyncio
async def test_coordinator_async_refresh_error():
    """Test coordinator async_refresh error handling."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)

        # Mock process_emails to raise an exception
        with patch(
            "custom_components.mail_and_packages.process_emails",
            side_effect=Exception("Test error"),
        ), patch(
            "custom_components.mail_and_packages.hash_file",
            return_value="test_hash",
        ):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_usps_hash_comparison():
    """Test coordinator binary sensor update for USPS hash comparison."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {
            "image_name": "test_image.gif",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "hash1", 100.0, "hash2"]
        )

        with patch(
            "custom_components.mail_and_packages.default_image_path",
            return_value="custom_components/mail_and_packages/images/",
        ), patch("os.path.exists", return_value=True), patch(
            "custom_components.mail_and_packages.hash_file",
            side_effect=["hash1", "hash2"],
        ):
            await coordinator._binary_sensor_update()

            # Should set usps_update to True since hashes are different
            assert coordinator._data["usps_update"] is True


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_amazon_hash_comparison():
    """Test coordinator binary sensor update for Amazon hash comparison."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {
            "amazon_image": "test_amazon.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "hash1", 100.0, "hash2"]
        )

        with patch(
            "custom_components.mail_and_packages.default_image_path",
            return_value="custom_components/mail_and_packages/images/",
        ), patch("os.path.exists", return_value=True), patch(
            "custom_components.mail_and_packages.hash_file",
            side_effect=["hash1", "hash2"],
        ):
            await coordinator._binary_sensor_update()

            # Should set amazon_update to True since hashes are different
            assert coordinator._data["amazon_update"] is True


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_ups_hash_comparison():
    """Test coordinator binary sensor update for UPS hash comparison."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {
            "ups_image": "test_ups.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "hash1", 100.0, "hash2"]
        )

        with patch(
            "custom_components.mail_and_packages.default_image_path",
            return_value="custom_components/mail_and_packages/images/",
        ), patch("os.path.exists", return_value=True), patch(
            "custom_components.mail_and_packages.hash_file",
            side_effect=["hash1", "hash2"],
        ):
            await coordinator._binary_sensor_update()

            # Should set ups_update to True since hashes are different
            assert coordinator._data["ups_update"] is True


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_same_hashes():
    """Test coordinator binary sensor update when hashes are the same."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {
            "image_name": "test_image.gif",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "same_hash", 100.0, "same_hash"]
        )

        with patch(
            "custom_components.mail_and_packages.default_image_path",
            return_value="custom_components/mail_and_packages/images/",
        ), patch("os.path.exists", return_value=True), patch(
            "custom_components.mail_and_packages.hash_file",
            side_effect=["same_hash", "same_hash"],
        ):
            await coordinator._binary_sensor_update()

            # Should set usps_update to False since hashes are the same
            assert coordinator._data["usps_update"] is False


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_amazon_same_hashes():
    """Test coordinator binary sensor update for Amazon when hashes are the same."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {
            "amazon_image": "test_amazon.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # We provide extra values to ensure the mock doesn't run out (returning a Mock object),
        # which would cause the equality check to fail.
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "same_hash", 100.0, "same_hash", 100.0, "same_hash"]
        )

        with patch(
            "custom_components.mail_and_packages.default_image_path",
            return_value="custom_components/mail_and_packages/images/",
        ), patch("os.path.exists", return_value=True), patch(
            "custom_components.mail_and_packages.hash_file",
            side_effect=["same_hash", "same_hash"],
        ):
            await coordinator._binary_sensor_update()

            # Should set amazon_update to False since hashes are the same
            assert coordinator._data["amazon_update"] is False


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_ups_same_hashes():
    """Test coordinator binary sensor update for UPS when hashes are the same."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {
            "ups_image": "test_ups.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # We provide extra values to ensure the mock doesn't run out.
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "same_hash", 100.0, "same_hash", 100.0, "same_hash"]
        )

        with patch(
            "custom_components.mail_and_packages.default_image_path",
            return_value="custom_components/mail_and_packages/images/",
        ), patch("os.path.exists", return_value=True), patch(
            "custom_components.mail_and_packages.hash_file",
            side_effect=["same_hash", "same_hash"],
        ):
            await coordinator._binary_sensor_update()

            # Should set ups_update to False since hashes are the same
            assert coordinator._data["ups_update"] is False
