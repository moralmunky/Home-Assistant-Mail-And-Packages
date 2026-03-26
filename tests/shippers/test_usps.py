"""Tests for USPS shipper utilities."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    CONF_DURATION,
)
from custom_components.mail_and_packages.shippers.usps import USPSShipper


@pytest.mark.asyncio
async def test_usps_shipper_basic(hass):
    """Test USPSShipper basic initialization."""
    shipper = USPSShipper(hass, {})
    assert shipper.name == "usps"


@pytest.mark.asyncio
async def test_informed_delivery_emails_class(
    hass,
    mock_imap_usps_informed_digest,
):
    """Test parsing of USPS Informed Delivery emails via USPSShipper class."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            CONF_DURATION: 5,
            "forwarded_emails": [],
        },
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif"
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(
            mock_imap_usps_informed_digest, "today", "usps_mail"
        )
        assert result[ATTR_COUNT] == 3


@pytest.mark.asyncio
async def test_new_informed_delivery_emails_class(
    hass,
    mock_imap_usps_new_informed_digest,
):
    """Test parsing of new format USPS Informed Delivery emails via USPSShipper class."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            CONF_DURATION: 5,
            "forwarded_emails": [],
        },
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif"
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(
            mock_imap_usps_new_informed_digest, "today", "usps_mail"
        )
        assert result[ATTR_COUNT] == 4


@pytest.mark.asyncio
async def test_informed_digest_no_mail_class(
    hass,
    mock_imap_usps_informed_digest_no_mail,
):
    """Test USPSShipper when no mail is found."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            "forwarded_emails": [],
        },
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch("custom_components.mail_and_packages.shippers.usps.shutil.copyfile"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(
            mock_imap_usps_informed_digest_no_mail, "today", "usps_mail"
        )
        assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_informed_delivery_with_images_class(hass):
    """Test USPS Informed Delivery with embedded images."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Create a mock email with HTML content containing a mailpiece image
    html_content = """
    <html>
        <body>
            <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,VEVTVF9JTUFHRV9EQVRB">
        </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html_content, "html"))
    msg_bytes = msg.as_bytes()

    mock_account = AsyncMock()
    # email_search calls account.search and expects an object with .result and .lines
    mock_search_res = MagicMock(result="OK", lines=[b"1"])
    mock_account.search.return_value = mock_search_res

    # email_fetch calls account.fetch and expects an object with .result and .lines
    mock_fetch_res = MagicMock(result="OK", lines=[b"RFC822", msg_bytes])
    mock_account.fetch.return_value = mock_fetch_res

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif"
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.random_filename",
            return_value="random.jpg",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        assert result[ATTR_COUNT] == 1


@pytest.mark.asyncio
async def test_informed_delivery_placeholder_image(hass):
    """Test USPS Informed Delivery with placeholder image."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Body containing the placeholder text
    msg_bytes = b"Some content with image-no-mailpieces700.jpg placeholder"

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", msg_bytes]
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif"
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        # should find 1 placeholder
        assert result[ATTR_COUNT] == 1


@pytest.mark.asyncio
async def test_informed_delivery_announcement_filtering(hass):
    """Test USPS Informed Delivery announcement filtering."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # HTML with one real image and one announcement image
    html_content = """
    <html>
        <body>
            <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,VEVTVF9JTUFHRV9EQVRB">
            <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,QU5OT1VOQ0VNRU5UX0RBVEE=">
        </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html_content, "html"))
    msg_bytes = msg.as_bytes()

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", msg_bytes]
    )

    # We want to mock random_filename to return one normal and one to-be-ignored filename
    filenames = ["real_image.jpg", "mailerProvidedImage.jpg"]

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.random_filename",
            side_effect=filenames,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            side_effect=lambda imgs, w, h: imgs,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif"
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        # 2 found in HTML, but 1 filtered out by announcement logic
        assert result[ATTR_COUNT] == 1


@pytest.mark.asyncio
async def test_informed_delivery_search_error(hass):
    """Test USPS Informed Delivery with search error."""
    shipper = USPSShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="BAD", lines=[])

    result = await shipper.process(mock_account, "today", "usps_mail")
    assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_informed_delivery_mkdir_error(hass):
    """Test USPS Informed Delivery with directory creation error."""
    shipper = USPSShipper(hass, {"image_path": "/root/test"})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=False,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.mkdir",
            side_effect=OSError("Permission denied"),
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        assert result[ATTR_COUNT] == 0


@pytest.mark.asyncio
async def test_informed_delivery_resize_error(hass):
    """Test USPS Informed Delivery with resize error."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "image_name": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Body containing the placeholder text
    msg_bytes = b"Some content with image-no-mailpieces700.jpg placeholder"

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", msg_bytes]
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
            side_effect=ValueError("Invalid image"),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        # should still return count even if GIF generation fails
        assert result[ATTR_COUNT] == 1
