"""Tests for init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages import (
    MailDataUpdateCoordinator,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_setup_entry,
)
from custom_components.mail_and_packages.const import (
    CONF_AUTH_TYPE,
    DOMAIN,
)
from tests.const import FAKE_CONFIG_DATA


@pytest.mark.asyncio
async def test_unload_entry(
    hass, mock_imap_no_email, integration, mock_update, mock_copy_overlays
):
    """Test unloading entities."""
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
    mock_imap_no_email,
    integration,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test setting up entities."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 48
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_no_path_no_sec(
    hass,
    mock_imap_no_email,
    integration_no_path,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test setting up entities."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 43
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_missing_imap_timeout(
    hass,
    mock_imap_no_email,
    integration_no_timeout,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test setting up entities."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 42
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_amazon_fwds_string(
    hass,
    mock_imap_no_email,
    integration_fwd_string,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test setting up entities."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 42
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_custom_img(
    hass,
    mock_imap_no_email,
    integration_custom_img,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test setting up entities."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 45
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_v4_migration(
    hass,
    mock_imap_no_email,
    integration_v4_migration,
    mock_osremove,
    mock_osmakedir,
    mock_listdir,
    mock_update_time,
    mock_copy_overlays,
    mock_hash_file,
    mock_getctime_today,
    mock_update,
):
    """Test setting up entities."""
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


async def test_migration_from_version_14_to_17():
    """Test migration from version 14 to 17."""
    # Mock config entry with version 14
    mock_config_entry = MagicMock()
    mock_config_entry.version = 14
    mock_config_entry.data = {
        "imap_security": "startTLS",
    }

    # Mock hass
    mock_hass = MagicMock()

    # Should migrate successfully
    result = await async_migrate_entry(mock_hass, mock_config_entry)
    assert result is True

    # Verify that the async_update_entry was called to update the imap_security to SSL
    args, kwargs = mock_hass.config_entries.async_update_entry.call_args
    assert kwargs["data"]["imap_security"] == "SSL"
    assert kwargs["data"]["auth_type"] == "password"
    assert kwargs["version"] == 17


async def test_migration_from_version_16_to_17():
    """Test migration from version 16 to 17 (flattening auth data)."""
    # Mock config entry with version 16 and nested auth data
    mock_config_entry = MagicMock()
    mock_config_entry.version = 16
    mock_config_entry.data = {
        "auth": {"token": "test_token", "access_token": "test_access_token"},
        "host": "imap.gmail.com",
    }

    # Mock hass
    mock_hass = MagicMock()

    # Should migrate successfully
    result = await async_migrate_entry(mock_hass, mock_config_entry)
    assert result is True

    # Verify that the async_update_entry was called to flatten the auth data
    args, kwargs = mock_hass.config_entries.async_update_entry.call_args
    assert "auth" not in kwargs["data"]
    assert kwargs["data"]["token"] == "test_token"
    assert kwargs["data"]["access_token"] == "test_access_token"
    assert kwargs["version"] == 17


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
async def test_coordinator_async_refresh_error(hass):
    """Test coordinator update failure."""
    mock_config = FAKE_CONFIG_DATA.copy()
    coordinator = MailDataUpdateCoordinator(hass, mock_config)

    with (
        patch(
            "custom_components.mail_and_packages.process_emails",
            side_effect=Exception("Test error"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_usps_hash_comparison():
    """Test coordinator binary sensor update for USPS hash comparison."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {  # noqa: SLF001
            "image_name": "test_image.gif",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "hash1", 100.0, "hash2"]
        )

        with (
            patch(
                "custom_components.mail_and_packages.default_image_path",
                return_value="custom_components/mail_and_packages/images/",
            ),
            patch(
                "custom_components.mail_and_packages.anyio.Path.exists",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.mail_and_packages.hash_file",
                side_effect=["hash1", "hash2"],
            ),
        ):
            await coordinator._binary_sensor_update()  # noqa: SLF001

            # Should set usps_update to True since hashes are different
            assert coordinator._data["usps_update"] is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_amazon_hash_comparison():
    """Test coordinator binary sensor update for Amazon hash comparison."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {  # noqa: SLF001
            "amazon_image": "test_amazon.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "hash1", 100.0, "hash2"]
        )

        with (
            patch(
                "custom_components.mail_and_packages.default_image_path",
                return_value="custom_components/mail_and_packages/images/",
            ),
            patch(
                "custom_components.mail_and_packages.anyio.Path.exists",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.mail_and_packages.hash_file",
                side_effect=["hash1", "hash2"],
            ),
        ):
            await coordinator._binary_sensor_update()  # noqa: SLF001

            # Should set amazon_update to True since hashes are different
            assert coordinator._data["amazon_update"] is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_ups_hash_comparison():
    """Test coordinator binary sensor update for UPS hash comparison."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {  # noqa: SLF001
            "ups_image": "test_ups.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "hash1", 100.0, "hash2"]
        )

        with (
            patch(
                "custom_components.mail_and_packages.default_image_path",
                return_value="custom_components/mail_and_packages/images/",
            ),
            patch(
                "custom_components.mail_and_packages.anyio.Path.exists",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.mail_and_packages.hash_file",
                side_effect=["hash1", "hash2"],
            ),
        ):
            await coordinator._binary_sensor_update()  # noqa: SLF001

            # Should set ups_update to True since hashes are different
            assert coordinator._data["ups_update"] is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_same_hashes():
    """Test coordinator binary sensor update when hashes are the same."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {  # noqa: SLF001
            "image_name": "test_image.gif",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # Order: mtime(img), hash(img), mtime(none), hash(none)
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "same_hash", 100.0, "same_hash"]
        )

        with (
            patch(
                "custom_components.mail_and_packages.default_image_path",
                return_value="custom_components/mail_and_packages/images/",
            ),
            patch(
                "custom_components.mail_and_packages.anyio.Path.exists",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.mail_and_packages.hash_file",
                side_effect=["same_hash", "same_hash"],
            ),
        ):
            await coordinator._binary_sensor_update()  # noqa: SLF001

            # Should set usps_update to False since hashes are the same
            assert coordinator._data["usps_update"] is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_coordinator_binary_sensor_update_amazon_same_hashes():
    """Test coordinator binary sensor update for Amazon when hashes are the same."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    # Patch frame.report_usage to avoid "Frame helper not set up" error
    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)
        coordinator._data = {  # noqa: SLF001
            "amazon_image": "test_amazon.jpg",
            "image_path": "custom_components/mail_and_packages/images/",
        }

        # Mock async_add_executor_job to return mtimes AND hashes
        # We provide extra values to ensure the mock doesn't run out (returning a Mock object),
        # which would cause the equality check to fail.
        mock_hass.async_add_executor_job = AsyncMock(
            side_effect=[100.0, "same_hash", 100.0, "same_hash", 100.0, "same_hash"]
        )

        with (
            patch(
                "custom_components.mail_and_packages.default_image_path",
                return_value="custom_components/mail_and_packages/images/",
            ),
            patch(
                "custom_components.mail_and_packages.anyio.Path.exists",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "custom_components.mail_and_packages.hash_file",
                side_effect=["same_hash", "same_hash"],
            ),
        ):
            await coordinator._binary_sensor_update()  # noqa: SLF001

            # Should set amazon_update to False since hashes are the same
            assert coordinator._data["amazon_update"] is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_setup_entry_refresh_failure(hass):
    """Test setup_entry when the coordinator fails to refresh data."""
    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        "host": "imap.test.com",
        "scan_interval": 5,
        "resources": [],
    }
    mock_config_entry.entry_id = "test_entry"
    with patch(
        "custom_components.mail_and_packages.MailDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.last_update_success = False
        mock_coordinator.last_exception = "IMAP Timeout"
        mock_coordinator.async_refresh = AsyncMock()
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_migrate_entry_invalid_version(hass):
    """Test migration failure or handling when the version is unsupported."""
    mock_entry = MockConfigEntry(
        domain="mail_and_packages", version=0, data={}, entry_id="test_entry"
    )
    mock_entry.add_to_hass(hass)
    result = await async_migrate_entry(hass, mock_entry)
    assert result is True
    assert mock_entry.version > 0


@pytest.mark.asyncio
async def test_async_migrate_entry_missing_amazon_fwds(hass):
    """Test migration when CONF_AMAZON_FWDS is missing (Line 271)."""
    # Create an entry specifically missing CONF_AMAZON_FWDS
    mock_entry = MockConfigEntry(
        domain="mail_and_packages",
        version=1,
        data={
            "host": "imap.test.com",
            # missing CONF_AMAZON_FWDS
        },
        entry_id="test_missing_keys",
    )
    mock_entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, mock_entry)
    assert result is True


@pytest.mark.asyncio
async def test_get_file_hash_cache_hit():
    """Test the file hash cache in MailDataUpdateCoordinator."""
    mock_hass = MagicMock()
    mock_config = FAKE_CONFIG_DATA.copy()

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = MailDataUpdateCoordinator(mock_hass, mock_config)

        file_path = "test.gif"
        mtime = 100.0
        file_hash = "abc123"

        # First call: populate cache
        mock_hass.async_add_executor_job = AsyncMock(side_effect=[mtime, file_hash])
        result1 = await coordinator._get_file_hash_if_changed(file_path)  # noqa: SLF001
        assert result1 == file_hash
        assert mock_hass.async_add_executor_job.call_count == 2

        # Second call: same mtime, should hit cache (line 271)
        mock_hass.async_add_executor_job = AsyncMock(return_value=mtime)
        result2 = await coordinator._get_file_hash_if_changed(file_path)  # noqa: SLF001
        assert result2 == file_hash
        assert mock_hass.async_add_executor_job.call_count == 1


@pytest.mark.asyncio
async def test_binary_sensor_update_missing_image_attr(hass, tmp_path):
    """Test _binary_sensor_update when an image attribute is missing (Line 335)."""
    mock_config = FAKE_CONFIG_DATA.copy()
    coordinator = MailDataUpdateCoordinator(hass, mock_config)

    # Mock data with a fake camera that doesn't have an ATTR_*_IMAGE constant
    coordinator._data = {  # noqa: SLF001
        "nonexistent_image": "test.jpg",
        "image_path": str(tmp_path),
    }

    with patch(
        "custom_components.mail_and_packages.const.CAMERA_DATA",
        {"nonexistent_camera": ["Nonexistent Camera"]},
    ):
        # This should hit line 335 and continue without error
        await coordinator._binary_sensor_update()  # noqa: SLF001
        assert "nonexistent_update" not in coordinator._data  # noqa: SLF001


@pytest.mark.asyncio
async def test_update_with_oauth(hass, mock_update):
    """Test OAuth token refresh during update."""
    mock_config = FAKE_CONFIG_DATA.copy()
    mock_config[CONF_AUTH_TYPE] = "oauth2_microsoft"
    mock_config_entry = MockConfigEntry(domain=DOMAIN, data=mock_config)

    coordinator = MailDataUpdateCoordinator(hass, mock_config)
    coordinator.config_entry = mock_config_entry

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch(
            "custom_components.mail_and_packages.process_emails",
            return_value={"test": "data"},
        ) as mock_process_emails,
    ):
        mock_session = mock_session_cls.return_value
        mock_session.async_ensure_token_valid = AsyncMock()
        mock_session.token = {"access_token": "fake_token"}

        await coordinator._async_update_data()  # noqa: SLF001

        mock_session.async_ensure_token_valid.assert_called_once()
        mock_process_emails.assert_called_once()
        called_config = mock_process_emails.call_args[0][1]
        assert called_config["oauth_token"] == "fake_token"


@pytest.mark.asyncio
async def test_update_with_oauth_error(hass, mock_update):
    """Test OAuth token refresh fails during update."""
    mock_config = FAKE_CONFIG_DATA.copy()
    mock_config[CONF_AUTH_TYPE] = "oauth2_microsoft"
    mock_config_entry = MockConfigEntry(domain=DOMAIN, data=mock_config)

    coordinator = MailDataUpdateCoordinator(hass, mock_config)
    coordinator.config_entry = mock_config_entry

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            side_effect=Exception("Failed to get implementation"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()  # noqa: SLF001
