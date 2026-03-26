"""Tests for helpers module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    CONF_ALLOW_EXTERNAL,
)
from custom_components.mail_and_packages.coordinator import MailDataUpdateCoordinator
from custom_components.mail_and_packages.helpers import (
    get_count,
    get_items,
    get_mails,
    get_resources,
)
from tests.const import (
    FAKE_CONFIG_DATA,
    FAKE_UPDATE_DATA,
)


async def process_emails(hass, config):
    """Bridge for tests."""
    coord = MailDataUpdateCoordinator(hass, config)
    return await coord.process_emails(hass, config)


def load_test_email(email_file):
    """Load test email file."""
    return Path(email_file).read_text(encoding="utf-8")


MAIL_IMAGE_URL_ENTITY = "sensor.mail_image_url"
MAIL_IMAGE_SYSTEM_PATH = "sensor.mail_image_system_path"
MAIL_IMAGE_GRID_IMAGE_PATH = "sensor.mail_grid_image_path"


@pytest.mark.asyncio
async def test_process_emails(
    hass,
    mock_imap_no_email,
    mock_update,
):
    """Test the main email processing loop asynchronously."""
    config = FAKE_CONFIG_DATA
    result = await process_emails(hass, config)
    assert result == FAKE_UPDATE_DATA


#     assert mock_copytree.call_args.kwargs == {"dirs_exist_ok": True}
#     # Check that both Amazon and UPS files are being cleaned up
#     amazon_removed = False
#     ups_removed = False

#     mock_file_amazon = MagicMock()
#     mock_file_amazon.name = "anotherfakefile.mp4"
#     mock_file_amazon.exists.return_value = True

#     mock_file_ups = MagicMock()
#     mock_file_ups.name = "anotherfakefile.mp4"
#     mock_file_ups.exists.return_value = True

#     with (
#         patch("pathlib.Path.is_dir", return_value=True),
#         patch("pathlib.Path.exists", return_value=True),
#         patch("pathlib.Path.iterdir", return_value=[mock_file_amazon, mock_file_ups], autospec=True),
#         patch("pathlib.Path.unlink", autospec=True) as mock_remove,
#         patch("pathlib.Path")
#     ):

#         assert mock_remove.call_count == 2

#         for remove_call in mock_remove.call_args_list:
#             if "www/mail_and_packages/amazon/anotherfakefile.mp4" in str(remove_call):
#                 amazon_removed = True
#             if "www/mail_and_packages/ups/anotherfakefile.mp4" in str(remove_call):
#                 ups_removed = True

#         assert amazon_removed
#         assert ups_removed


@pytest.mark.asyncio
async def test_process_emails_external_error(
    hass,
    mock_imap_no_email,
    caplog,
):
    """Test error handling during external email processing."""
    config = FAKE_CONFIG_DATA.copy()
    config[CONF_ALLOW_EXTERNAL] = True
    with patch(
        "custom_components.mail_and_packages.helpers.copy_images",
        side_effect=OSError("Mocked file system error"),
    ):
        await process_emails(hass, config)
        assert "Error attempting to copy image" in caplog.text


@pytest.mark.asyncio
async def test_get_resources(hass):
    """Test get_resources."""
    result = get_resources(hass)
    assert "amazon_packages" in result
    assert "fedex_delivered" in result
    assert "ups_delivered" in result
    assert "usps_mail" in result


@pytest.mark.asyncio
async def test_get_mails(hass, mock_imap_no_email):
    """Test get_mails."""
    config = FAKE_CONFIG_DATA
    account = mock_imap_no_email
    # Mock the response parts to avoid UnboundLocalError
    account.fetch.return_value = MagicMock(result="OK", lines=[])
    result = await get_mails(account, ["test@gmail.com"], hass, config)
    assert result == 0


@pytest.mark.asyncio
async def test_get_count(hass, mock_imap_no_email):
    """Test get_count."""
    account = mock_imap_no_email
    result = await get_count(account, "amazon_packages", False, "test_path", hass)
    assert result == {ATTR_COUNT: 0, ATTR_TRACKING: []}


@pytest.mark.asyncio
async def test_get_items(hass, mock_imap_no_email):
    """Test get_items."""
    config = FAKE_CONFIG_DATA
    account = mock_imap_no_email
    result = await get_items(hass, config, account, "amazon_packages")
    assert result == {ATTR_COUNT: 0, ATTR_TRACKING: []}
