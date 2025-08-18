"""Tests for migration functionality."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mail_and_packages.const import (
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    DOMAIN,
)

pytestmark = pytest.mark.asyncio


async def test_migration_from_version_10_to_11(hass, caplog):
    """Test migration from version 10 to version 11 adds custom image fields."""
    # Create a config that simulates version 10 (without custom image fields)
    v10_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v10_config,
        version=10,  # Start with version 10
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert "Migration complete to version 11" in caplog.text

    # Verify the new fields were added with correct defaults
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
    )

    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )

    # Verify version was updated
    assert entry.version == 11

    # Verify existing fields were preserved
    assert entry.data["amazon_days"] == 3
    assert entry.data["amazon_domain"] == "amazon.com"
    assert entry.data["host"] == "imap.test.email"


async def test_migration_from_version_9_to_11(hass, caplog):
    """Test migration from version 9 to version 11 adds all missing fields."""
    # Create a config that simulates version 9 (missing storage field too)
    v9_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v9_config,
        version=9,  # Start with version 9
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert "Migration complete to version 11" in caplog.text

    # Verify all missing fields were added
    assert "storage" in entry.data
    assert entry.data["storage"] == "custom_components/mail_and_packages/images/"

    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
    )

    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )

    # Verify version was updated
    assert entry.version == 11


async def test_migration_from_version_11_no_changes(hass, caplog):
    """Test that migration from version 11 doesn't make unnecessary changes."""
    # Create a config that's already at version 11
    v11_config = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": False,
        "custom_img_file": "custom_components/mail_and_packages/images/mail_none.gif",
        "amazon_custom_img": False,
        "amazon_custom_img_file": "custom_components/mail_and_packages/no_deliveries_amazon.jpg",
        "ups_custom_img": False,
        "ups_custom_img_file": "custom_components/mail_and_packages/no_deliveries_ups.jpg",
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v11_config,
        version=11,  # Already at version 11
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration message appears
    assert "Migration complete to version 11" in caplog.text

    # Verify all fields are still present and unchanged
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is False
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
    )

    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )

    # Verify version remains 11
    assert entry.version == 11


async def test_migration_preserves_existing_custom_image_settings(hass, caplog):
    """Test that migration preserves existing custom image settings if present."""
    # Create a config that has some custom image settings already
    v10_config_with_custom = {
        "amazon_days": 3,
        "amazon_domain": "amazon.com",
        "amazon_fwds": ["fakeuser@fake.email", "fakeuser2@fake.email"],
        "allow_external": False,
        "custom_img": True,
        "custom_img_file": "images/custom_mail.gif",
        "amazon_custom_img": True,  # Already set
        "amazon_custom_img_file": "images/custom_amazon.jpg",  # Already set
        "folder": '"INBOX"',
        "generate_grid": False,
        "generate_mp4": False,
        "gif_duration": 5,
        "host": "imap.test.email",
        "image_name": "mail_today.gif",
        "image_path": "custom_components/mail_and_packages/images/",
        "image_security": True,
        "imap_security": "SSL",
        "imap_timeout": 30,
        "password": "suchfakemuchpassword",
        "port": 993,
        "resources": [
            "amazon_delivered",
            "amazon_packages",
            "ups_delivered",
            "ups_packages",
            "usps_delivered",
            "usps_packages",
        ],
        "scan_interval": 20,
        "storage": "custom_components/mail_and_packages/images/",
        "username": "user@fake.email",
        "verify_ssl": False,
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=v10_config_with_custom,
        version=10,  # Start with version 10
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert "Migration complete to version 11" in caplog.text

    # Verify existing custom image settings were preserved
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert entry.data[CONF_AMAZON_CUSTOM_IMG] is True  # Preserved
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_AMAZON_CUSTOM_IMG_FILE] == "images/custom_amazon.jpg"
    )  # Preserved

    # Verify UPS fields were added with defaults
    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert entry.data[CONF_UPS_CUSTOM_IMG] is False  # Default
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data
    assert (
        entry.data[CONF_UPS_CUSTOM_IMG_FILE]
        == "custom_components/mail_and_packages/no_deliveries_ups.jpg"
    )  # Default

    # Verify version was updated
    assert entry.version == 11


async def test_migration_with_minimal_config(hass, caplog):
    """Test migration with a minimal config that's missing many fields."""
    # Create a very minimal config that might exist from very old versions
    minimal_config = {
        "host": "imap.test.email",
        "port": 993,
        "username": "user@fake.email",
        "password": "suchfakemuchpassword",
        "folder": '"INBOX"',
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="imap.test.email",
        data=minimal_config,
        version=1,  # Very old version
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration occurred
    assert "Migration complete to version 11" in caplog.text

    # Verify all required fields were added
    assert "amazon_days" in entry.data
    assert "amazon_domain" in entry.data
    assert "imap_security" in entry.data
    assert "verify_ssl" in entry.data
    assert "storage" in entry.data
    assert CONF_AMAZON_CUSTOM_IMG in entry.data
    assert CONF_AMAZON_CUSTOM_IMG_FILE in entry.data
    assert CONF_UPS_CUSTOM_IMG in entry.data
    assert CONF_UPS_CUSTOM_IMG_FILE in entry.data

    # Verify version was updated
    assert entry.version == 11
