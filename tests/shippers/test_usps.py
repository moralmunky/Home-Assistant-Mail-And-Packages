"""Tests for USPS shipper utilities."""

import base64
from datetime import date
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_GRID_IMAGE_NAME,
    ATTR_HAS_MAIL_IMAGES,
    ATTR_IMAGE_PATH,
    ATTR_SCANNED_IMAGES,
    ATTR_UNSCANNED_PIECES,
    ATTR_USPS_IMAGE,
    CONF_DURATION,
    CONF_FORWARDING_HEADER,
    SENSOR_DATA,
)
from custom_components.mail_and_packages.shippers.usps import (
    USPSShipper,
    extract_digest_target_date,
    is_email_from_prior_day,
)
from custom_components.mail_and_packages.shippers.usps.image import (
    extract_jpeg_attachment,
)
from custom_components.mail_and_packages.utils.cache import EmailCache


@pytest.mark.asyncio
async def test_usps_shipper_basic(hass):
    """Test USPSShipper basic initialization."""
    shipper = USPSShipper(hass, {})
    assert shipper.name == "usps"
    assert shipper.handles_sensor("usps_mail") is True
    assert shipper.handles_sensor("other") is False


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
            "usps_image": "mail_today.gif",
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
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(
            mock_imap_usps_informed_digest,
            "today",
            "usps_mail",
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
            "usps_image": "mail_today.gif",
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
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(
            mock_imap_usps_new_informed_digest,
            "today",
            "usps_mail",
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
            "usps_image": "mail_today.gif",
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
            mock_imap_usps_informed_digest_no_mail,
            "today",
            "usps_mail",
        )
        assert result[ATTR_COUNT] == 0
        assert result[ATTR_USPS_IMAGE] == "mail_today.gif"
        assert result[ATTR_IMAGE_PATH] == "test/path/usps/"
        assert result[ATTR_GRID_IMAGE_NAME] == "mail_today_grid.png"


@pytest.mark.asyncio
async def test_informed_delivery_with_images_class(hass):
    """Test USPS Informed Delivery with embedded images."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
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
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.random_filename",
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
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Body containing the placeholder text
    msg_bytes = b"Some content with image-no-mailpieces700.jpg placeholder"

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK",
        lines=[b"RFC822", msg_bytes],
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
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        # should find 1 placeholder
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_SCANNED_IMAGES] == 0
        assert result[ATTR_UNSCANNED_PIECES] == 1
        assert result[ATTR_HAS_MAIL_IMAGES] is False


@pytest.mark.asyncio
async def test_informed_delivery_placeholder_image_new_format(hass):
    """Test USPS Informed Delivery with new-format mailpiece-with-no-image-id div."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # New USPS email format: no image reference, instead a div with a specific id
    html_content = (
        "<!-- START MAILPIECE WITH NO IMAGE -->"
        '<div id="mailpiece-with-no-image-id">'
        "<p>There is one or more mailpieces for which we do not currently"
        " have an image that is included in today's mail.</p>"
        "</div>"
        "<!-- END MAILPIECE WITH NO IMAGE -->"
    )
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html_content, "html"))
    msg_bytes = msg.as_bytes()

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK",
        lines=[b"RFC822", msg_bytes],
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
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        assert result[ATTR_COUNT] == 1
        assert result[ATTR_SCANNED_IMAGES] == 0
        assert result[ATTR_UNSCANNED_PIECES] == 1
        assert result[ATTR_HAS_MAIL_IMAGES] is False


@pytest.mark.asyncio
async def test_informed_delivery_mixed_scanned_and_multiple_unscanned(hass):
    """Test USPS Informed Delivery with both scanned images and multiple unscanned pieces."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
            "usps_placeholder": False,
        },
    )

    html_content = (
        "<html><body>"
        '<img id="mailpiece-image-src-id" src="data:image/jpeg;base64,VEVTVF9JTUFHRQ==">'
        '<div id="mailpiece-with-no-image-id"><p>Piece 1</p></div>'
        '<div id="mailpiece-with-no-image-id"><p>Piece 2</p></div>'
        "</body></html>"
    )
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html_content, "html"))
    msg_bytes = msg.as_bytes()

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK",
        lines=[b"RFC822", msg_bytes],
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
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.random_filename",
            return_value="test/path/usps/mailpiece1.jpg",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/mailpiece1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ) as mock_gif,
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        assert result[ATTR_COUNT] == 3
        assert result[ATTR_SCANNED_IMAGES] == 1
        assert result[ATTR_UNSCANNED_PIECES] == 2
        assert result[ATTR_HAS_MAIL_IMAGES] is True
        mock_gif.assert_called_once()
        # Ensure placeholder was not included in camera media
        called_images = mock_gif.call_args[0][0]
        assert "image-no-mailpieces700.jpg" not in str(called_images)


@pytest.mark.asyncio
async def test_informed_delivery_announcement_filtering(hass):
    """Test USPS Informed Delivery announcement filtering."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
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
        result="OK",
        lines=[b"RFC822", msg_bytes],
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
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.random_filename",
            side_effect=filenames,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            side_effect=lambda imgs, w, h: imgs,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
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

    with (
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.shutil.copyfile"
        ) as mock_copy,
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        assert result[ATTR_COUNT] == 0
        assert result[ATTR_USPS_IMAGE] == "usps_deliveries.gif"
        assert result[ATTR_IMAGE_PATH] == "custom_components/mail_and_packages/images/"
        mock_copy.assert_called_once()


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
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Body containing the placeholder text
    msg_bytes = b"Some content with image-no-mailpieces700.jpg placeholder"

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK",
        lines=[b"RFC822", msg_bytes],
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


@pytest.mark.asyncio
async def test_informed_delivery_forwarded_emails(hass):
    """Test USPS Informed Delivery with forwarded emails (Line 211)."""
    shipper = USPSShipper(hass, {"forwarded_emails": ["forward@test.com"]})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[])

    with patch(
        "custom_components.mail_and_packages.shippers.usps.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "usps_mail")
        assert "forward@test.com" in mock_search.call_args.kwargs["address"]


@pytest.mark.asyncio
async def test_informed_delivery_forwarded_emails_string(hass):
    """Test that a legacy string value for forwarded_emails is normalized to a list."""
    shipper = USPSShipper(
        hass, {"forwarded_emails": "forward@test.com, other@test.com"}
    )
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[])

    with patch(
        "custom_components.mail_and_packages.shippers.usps.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "usps_mail")
        search_addresses = mock_search.call_args.kwargs["address"]
        assert "forward@test.com" in search_addresses
        assert "other@test.com" in search_addresses


@pytest.mark.asyncio
async def test_informed_delivery_forwarding_header_mode(hass):
    """Test USPS Informed Delivery in header mode: uses native addresses, passes header kwarg."""
    shipper = USPSShipper(
        hass,
        {
            CONF_FORWARDING_HEADER: "X-SimpleLogin-Original-From",
            "forwarded_emails": ["should-not-appear@example.com"],
        },
    )
    mock_account = AsyncMock()
    native_addresses = SENSOR_DATA["usps_mail"]["email"]

    with patch(
        "custom_components.mail_and_packages.shippers.usps.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "usps_mail")
        search_addresses = mock_search.call_args.kwargs["address"]
        assert "should-not-appear@example.com" not in search_addresses
        for addr in native_addresses:
            assert addr in search_addresses
        assert mock_search.call_args.kwargs["header"] == "X-SimpleLogin-Original-From"


@pytest.mark.asyncio
async def test_informed_delivery_gen_mp4_grid(hass):
    """Test USPS Informed Delivery with MP4 and grid generation (Lines 106, 110)."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/",
            "usps_image": "test.gif",
            "generate_mp4": True,
            "generate_grid": True,
        },
    )
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK",
        lines=[b"RFC822", b"no mail"],
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
            "custom_components.mail_and_packages.shippers.usps._generate_mp4",
        ) as mock_mp4,
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_grid_img",
        ) as mock_grid,
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        mock_mp4.assert_called_once()
        mock_grid.assert_called_once()
        assert result[ATTR_GRID_IMAGE_NAME] == "test_grid.png"


@pytest.mark.asyncio
async def test_informed_delivery_extract_images_error(hass):
    """Test USPS Informed Delivery extraction error (Lines 294-295)."""
    shipper = USPSShipper(hass, {"image_path": "test/"})

    # Mocking BeautifulSoup to trigger an error during extraction
    html_content = '<html><body><img id="mailpiece-image-src-id" src="data:image/jpeg;base64,invalid"></body></html>'
    part = MagicMock()
    part.get_payload.return_value = html_content.encode()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            side_effect=TypeError("Expected bytes"),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.random_filename",
            return_value="test.jpg",
        ),
    ):
        count, images = await shipper._extract_usps_images(part, "test/", 0, [])
        assert count == 0
        assert len(images) == 0


@pytest.mark.asyncio
async def test_extract_jpeg_attachment_no_filename(hass):
    """Test _extract_jpeg_attachment with missing filename (Line 311)."""
    shipper = USPSShipper(hass, {})
    part = MagicMock()
    part.get_filename.return_value = None

    count, images = await shipper._extract_jpeg_attachment(part, "test/", 0, [])
    assert count == 0
    assert len(images) == 0


@pytest.mark.asyncio
async def test_extract_jpeg_attachment_os_error(hass):
    """Test _extract_jpeg_attachment with OSError (Lines 324-325)."""
    shipper = USPSShipper(hass, {})
    part = MagicMock()
    part.get_filename.return_value = "informed_delivery.jpg"
    part.get_payload.return_value = b"data"

    with patch(
        "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
        side_effect=OSError("Permission denied"),
    ):
        count, images = await shipper._extract_jpeg_attachment(part, "test/", 0, [])
        assert count == 0


@pytest.mark.asyncio
async def test_extract_jpeg_attachment_path_traversal_prevention(hass, tmp_path):
    """Test that extract_jpeg_attachment uses random_filename and prevents path traversal."""
    output_dir = tmp_path / "images"
    output_dir.mkdir()

    part = MagicMock()
    # Malicious filenames attempting absolute path and relative directory traversal
    part.get_filename.return_value = "../../evil.py"
    part.get_payload.return_value = b"malicious content"

    with patch(
        "custom_components.mail_and_packages.shippers.usps.image.random_filename",
        return_value="safe_random.jpg",
    ):
        count, images = await extract_jpeg_attachment(
            hass, part, str(output_dir), 0, []
        )

    assert count == 1
    assert len(images) == 1
    saved_path = Path(images[0])
    # Ensure saved file stays within output directory and doesn't use the traversal name
    assert saved_path.parent.resolve() == output_dir.resolve()
    assert saved_path.name == "safe_random.jpg"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attachment_name", "include_attachment"),
    [
        ("ra_0.jpg", False),
        ("prefix_ra_0.jpg", False),
        ("Mail Attachment.txt", False),
        ("mailerProvidedImage.jpg", False),
        ("content.jpg", False),
        ("package.jpg", False),
        ("image002.jpg", True),
        ("../../scan.jpg", True),
        ("/untrusted/scan.jpg", True),
        (None, False),
    ],
)
async def test_process_usps_email_filters_attachment_names_before_randomizing(
    hass, tmp_path, attachment_name, include_attachment
):
    """Known announcement names stay excluded after safe output names replace them."""
    msg = EmailMessage()
    msg["Subject"] = "Your Daily Digest for Mon, Oct 19"
    msg["Date"] = "Mon, 19 Oct 2026 09:00:00 -0400"
    msg.set_content("Synthetic digest")
    msg.add_alternative(
        '<img id="mailpiece-image-src-id" src="cid:scan">'
        '<img id="campaign-ridealong-image-src-id" src="cid:extra">',
        subtype="html",
    )
    html_part = msg.get_payload()[1]
    html_part.add_related(
        b"synthetic scan",
        maintype="image",
        subtype="jpeg",
        cid="<scan>",
        filename="scan.jpg",
    )
    options = {"filename": attachment_name} if attachment_name else {}
    html_part.add_related(
        b"synthetic attachment",
        maintype="image",
        subtype="jpeg",
        cid="<extra>",
        **options,
    )
    account = AsyncMock()
    cache = EmailCache(account)
    cache.store("1", "(RFC822)", ("OK", [msg.as_bytes()]))
    shipper = USPSShipper(hass, {})

    count, images, content = await shipper._process_usps_email(
        account, "1", str(tmp_path), 0, [], cache, date(2026, 10, 19)
    )
    filtered = await shipper._process_usps_images(content, images)

    expected_count = 2 if include_attachment else 1
    assert count == expected_count
    assert len(filtered) == expected_count
    assert set(tmp_path.iterdir()) == {Path(image) for image in filtered}
    saved_payloads = set()
    for image in filtered:
        saved_path = Path(image)
        assert saved_path.parent == tmp_path
        assert saved_path.name not in ("scan.jpg", attachment_name)
        saved_payloads.add(await hass.async_add_executor_job(saved_path.read_bytes))
    expected_payloads = {b"synthetic scan"}
    if include_attachment:
        expected_payloads.add(b"synthetic attachment")
    assert saved_payloads == expected_payloads
    account.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_copy_nomail_image_mkdir(hass):
    """Test _copy_nomail_image with mkdir (Line 179)."""
    shipper = USPSShipper(hass, {})
    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.exists",
            side_effect=[False, True],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.mkdir",
        ) as mock_mkdir,
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.is_file",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.shutil.copyfile"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.cleanup_images"
        ) as mock_cleanup,
    ):
        await shipper._copy_nomail_image("test/", "test.gif", None)
        mock_mkdir.assert_called_once()
        mock_cleanup.assert_called_with("test/", "test.gif")


@pytest.mark.asyncio
async def test_usps_announcement_removal(hass):
    """Test _remove_announcement_images (Lines 140, 142)."""

    shipper = USPSShipper(hass, {})
    images = [
        "normal.jpg",
        "mailerProvidedImage_1.jpg",
        "ra_0.jpg",
        "Mail Attachment.txt",
    ]
    result = shipper._remove_announcement_images(images)
    assert result == ["normal.jpg"]


@pytest.mark.asyncio
async def test_usps_process_error(hass):
    """Test process method with search error (Lines 215-220)."""

    shipper = USPSShipper(hass, {})
    mock_acc = AsyncMock()
    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.email_search",
            side_effect=Exception("Search Error"),
        ),
        pytest.raises(Exception, match="Search Error"),
    ):
        await shipper.process(mock_acc, "today", "usps_mail")


@pytest.mark.asyncio
async def test_generate_mail_image_call(hass):
    """Test _generate_mail_image (Line 149)."""

    shipper = USPSShipper(hass, {})
    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.Path") as mock_path,
    ):
        mock_path.return_value.__truediv__.return_value = "/path/img1.jpg"
        await shipper._generate_mail_image(
            ["img1.jpg"],
            "/path",
            "name",
            5,
            ["img1.jpg"],
        )


@pytest.mark.asyncio
async def test_copy_nomail_image_os_error(hass):
    """Test _copy_nomail_image with OSError (Line 215)."""
    shipper = USPSShipper(hass, {})
    with patch.object(hass, "async_add_executor_job", side_effect=OSError("Disk Full")):
        await shipper._copy_nomail_image("test/", "test.gif", None)


@pytest.mark.asyncio
async def test_process_batch(hass):
    """Test process_batch for USPS shipper."""
    shipper = USPSShipper(hass, {})
    mock_account = AsyncMock()
    mock_cache = MagicMock()

    with patch.object(shipper, "process", new_callable=AsyncMock) as mock_process:
        # Mock process to return a result that requires the "sensor not in res" logic
        async def _mock_process(account, date, sensor, cache):
            if sensor == "usps_mail":
                # Trigger the "sensor not in res" and "ATTR_COUNT in res" branch
                return {ATTR_COUNT: 5}
            return {sensor: 0}

        mock_process.side_effect = _mock_process

        sensors = ["usps_mail"]
        result = await shipper.process_batch(mock_account, "today", sensors, mock_cache)

        assert result["usps_mail"] == 5


@pytest.mark.asyncio
async def test_process_with_cache(hass):
    """Test USPS shipper processing with EmailCache."""
    shipper = USPSShipper(
        hass, {"image_path": "test/path/", "usps_image": "mail_today.gif"}
    )
    mock_account = AsyncMock()

    cache = EmailCache(mock_account)

    # Populate cache for _search_for_emails (Line 302)
    cache._cache_rfc822["1"] = (
        "OK",
        [b"RFC822", b"Subject: USPS Informed Delivery\n\nNo mail today"],
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch("custom_components.mail_and_packages.shippers.usps.shutil.copyfile"),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail", cache=cache)
        assert result[ATTR_COUNT] == 0  # "No mail today"


@pytest.mark.asyncio
async def test_usps_placeholder_disabled(hass, mock_imap_usps_informed_digest_missing):
    """Test USPS shipper processing when usps_placeholder option is disabled."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
            "forwarded_emails": [],
            "usps_placeholder": False,
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
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ) as mock_generate_gif,
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="25-Sep-2020",
        ),
    ):
        result = await shipper.process(
            mock_imap_usps_informed_digest_missing,
            "today",
            "usps_mail",
        )
        # Total count should still be 5 (scanned + unscanned placeholder)
        assert result[ATTR_COUNT] == 5

        # But the generated GIF images should NOT include the placeholder
        called_images = mock_generate_gif.call_args[0][0]
        assert not any("image-no-mailpieces700.jpg" in img for img in called_images)


@pytest.mark.asyncio
async def test_copy_nomail_image_relative_path(hass):
    """Test _copy_nomail_image resolves relative path relative to config directory."""
    shipper = USPSShipper(hass, {})
    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.exists",
            return_value=True,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.Path.is_file",
            return_value=False,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.shutil.copyfile"
        ) as mock_copyfile,
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
    ):
        relative_path = "custom_components/mail_and_packages/mail_none.gif"
        expected_resolved_path = hass.config.path(relative_path)

        await shipper._copy_nomail_image("test/", "test.gif", relative_path)
        mock_copyfile.assert_called_once_with(expected_resolved_path, "test/test.gif")


@pytest.mark.asyncio
async def test_informed_delivery_filters_prior_day_emails(hass):
    """Test that USPS Informed Delivery ignores digest emails from prior days (fixes #1485)."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Email 1: Yesterday's email (2 mailpieces)
    html_yesterday = """
    <html><body>
        <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,dGVzdDE=">
        <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,dGVzdDI=">
    </body></html>
    """
    msg_yesterday = MIMEMultipart("alternative")
    msg_yesterday["Subject"] = "Your Daily Digest for Wed, Oct 7"
    msg_yesterday["Date"] = "Wed, 07 Oct 2026 07:50:00 -0400"
    msg_yesterday.attach(MIMEText(html_yesterday, "html"))

    # Email 2: Today's email (1 mailpiece)
    html_today = """
    <html><body>
        <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,dGVzdDE=">
    </body></html>
    """
    msg_today = MIMEMultipart("alternative")
    msg_today["Subject"] = "Your Daily Digest for Thu, Oct 8"
    msg_today["Date"] = "Thu, 08 Oct 2026 07:41:00 -0400"
    msg_today.attach(MIMEText(html_today, "html"))

    mock_account = AsyncMock()
    # Search returned both IDs
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"294062 294101"])

    def _fetch_side_effect(num, parts):
        if str(num) == "294062":
            return MagicMock(result="OK", lines=[b"RFC822", msg_yesterday.as_bytes()])
        return MagicMock(result="OK", lines=[b"RFC822", msg_today.as_bytes()])

    mock_account.fetch.side_effect = _fetch_side_effect

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.io_save_file",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.resize_images",
            return_value=["test/path/usps/img1.jpg"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.generate_delivery_gif",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="08-Oct-2026",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_today",
            return_value=date(2026, 10, 8),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.image.random_filename",
            return_value="random.jpg",
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        # Only today's 1 mailpiece should be counted
        assert result[ATTR_COUNT] == 1


@pytest.mark.asyncio
async def test_informed_delivery_only_prior_day_emails(hass):
    """Test that when only prior day emails are returned, no mail is counted."""
    shipper = USPSShipper(
        hass,
        {
            "image_path": "test/path/usps/",
            "usps_image": "mail_today.gif",
            CONF_DURATION: 5,
        },
    )

    # Only yesterday's email was returned
    html_yesterday = """
    <html><body>
        <img id="mailpiece-image-src-id" src="data:image/jpeg;base64,dGVzdDE=">
    </body></html>
    """
    msg_yesterday = MIMEMultipart("alternative")
    msg_yesterday["Subject"] = "Your Daily Digest for Wed, Oct 7"
    msg_yesterday["Date"] = "Wed, 07 Oct 2026 07:50:00 -0400"
    msg_yesterday.attach(MIMEText(html_yesterday, "html"))

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"294062"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", msg_yesterday.as_bytes()]
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.usps.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.usps.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.usps.copy_overlays"),
        patch.object(
            shipper,
            "_copy_nomail_image",
            new_callable=AsyncMock,
        ) as mock_nomail,
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_formatted_date",
            return_value="08-Oct-2026",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.get_today",
            return_value=date(2026, 10, 8),
        ),
    ):
        result = await shipper.process(mock_account, "today", "usps_mail")
        assert result[ATTR_COUNT] == 0
        mock_nomail.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("use_cache", [False, True], ids=["imap", "cache"])
@pytest.mark.parametrize("encoding", ["plain", "quoted", "base64", "folded"])
@pytest.mark.parametrize(
    ("digest_date", "date_header", "expected_count"),
    [
        ("Wed, Oct 7", "08 Oct 2026 12:00:00", 0),
        ("Thu, Oct 8", "07 Oct 2026 12:00:00", 1),
        ("Wed, Oct 7", None, 0),
        ("Thu, Oct 8", None, 1),
    ],
    ids=[
        "old-subject-new-header",
        "new-subject-old-header",
        "old-no-header",
        "new-no-header",
    ],
)
async def test_process_usps_email_encoded_digest_date(
    hass, tmp_path, use_cache, encoding, digest_date, date_header, expected_count
):
    """Equivalent encoded subjects must preserve which digest images are saved."""
    subject = f"Your Daily Digest for {digest_date}"
    if encoding == "quoted":
        subject = f"=?UTF-8?Q?{subject.replace(' ', '_')}?="
    elif encoding == "base64":
        subject = f"=?UTF-8?B?{base64.b64encode(subject.encode()).decode()}?="
    elif encoding == "folded":
        # Split across the phrase/date boundary, with different declared charsets.
        subject = (
            "=?UTF-8?Q?Your_Daily_Digest_for_?=\r\n "
            f"=?ISO-8859-1?Q?{digest_date.replace(' ', '_')}?="
        )

    image_data = f"mailpiece for {digest_date}".encode()
    headers = f"Subject: {subject}\r\n"
    if date_header:
        headers += f"Date: {date_header}\r\n"
    raw_email = (
        headers
        + 'Content-Type: text/html; charset="utf-8"\r\n\r\n'
        + '<img id="mailpiece-image-src-id" src="data:image/jpeg;base64,'
        + base64.b64encode(image_data).decode()
        + '">'
    ).encode()
    account = AsyncMock()
    cache = EmailCache(account) if use_cache else None
    if cache:
        cache.store("1", "(RFC822)", ("OK", [raw_email]))

    shipper = USPSShipper(hass, {})
    with patch(
        "custom_components.mail_and_packages.shippers.usps.email_fetch",
        return_value=("OK", [raw_email]),
    ) as mock_fetch:
        count, images, content = await shipper._process_usps_email(
            account, "1", str(tmp_path), 0, [], cache, date(2026, 10, 8)
        )

    assert count == expected_count
    assert len(images) == expected_count
    assert set(tmp_path.iterdir()) == {Path(image) for image in images}
    if expected_count:
        assert (
            await hass.async_add_executor_job(Path(images[0]).read_bytes) == image_data
        )
        assert content == raw_email.decode()
    else:
        assert content == ""
    if use_cache:
        mock_fetch.assert_not_awaited()
    else:
        mock_fetch.assert_awaited_once_with(account, "1", "(RFC822)")
    account.fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        None,
        "",
        "USPS Notification",
        "=?unknown-charset?Q?Your_Daily_Digest_for_Thu,_Oct_8?=",
        "=?utf-8?B?/w==?=",
        "=?utf-8?B?A?=",
    ],
    ids=[
        "missing",
        "empty",
        "no-date",
        "unknown-charset",
        "invalid-utf8",
        "invalid-base64",
    ],
)
@pytest.mark.parametrize(
    ("date_header", "expected_content"),
    [("07 Oct 2026 12:00:00", False), ("Invalid Date", True), (None, True)],
    ids=["old-header", "invalid-header", "no-header"],
)
async def test_process_usps_email_subject_fallback(
    hass, tmp_path, subject, date_header, expected_content
):
    """Undecodable or missing subjects retain the existing date fallback policy."""
    headers = ""
    if subject is not None:
        headers += f"Subject: {subject}\r\n"
    if date_header is not None:
        headers += f"Date: {date_header}\r\n"
    raw_email = (headers + "\r\nSynthetic body").encode()

    shipper = USPSShipper(hass, {})
    with patch(
        "custom_components.mail_and_packages.shippers.usps.email_fetch",
        return_value=("OK", [raw_email]),
    ):
        count, images, content = await shipper._process_usps_email(
            AsyncMock(), "1", str(tmp_path), 0, [], target_date=date(2026, 10, 8)
        )

    assert count == 0
    assert images == []
    assert content == (raw_email.decode() if expected_content else "")


def test_extract_digest_target_date():
    """Test extract_digest_target_date under various subject formats and edge cases."""
    today = date(2026, 10, 8)

    # Empty / None
    assert extract_digest_target_date(None, today) is None
    assert extract_digest_target_date("", today) is None

    # Standard format: Your Daily Digest for Day, Month Day
    assert extract_digest_target_date(
        "Your Daily Digest for Wed, Oct 7", today
    ) == date(2026, 10, 7)
    assert extract_digest_target_date(
        "Your Daily Digest for Sat, Nov 21", today
    ) == date(2026, 11, 21)

    # Slash format: Your Daily Digest for Day, M/D
    assert extract_digest_target_date(
        "Your Daily Digest for Thu, 5/1 is ready to view", today
    ) == date(2026, 5, 1)
    assert extract_digest_target_date("Your Daily Digest for Thu, 10/8", today) == date(
        2026, 10, 8
    )

    # Invalid / unparsable formats
    assert extract_digest_target_date("Delivery notification", today) is None
    assert extract_digest_target_date("Your Daily Digest for Foo, 99/99", today) is None
    assert (
        extract_digest_target_date("Your Daily Digest for Foo, Invalid 99", today)
        is None
    )


def test_is_email_from_prior_day():
    """Test is_email_from_prior_day under various subjects and date headers."""
    today = date(2026, 10, 8)

    # Subject date takes precedence
    assert (
        is_email_from_prior_day(
            "Your Daily Digest for Wed, Oct 7",
            "Thu, 08 Oct 2026 07:00:00 -0400",
            today,
        )
        is True
    )
    assert (
        is_email_from_prior_day(
            "Your Daily Digest for Thu, Oct 8",
            "Wed, 07 Oct 2026 07:00:00 -0400",
            today,
        )
        is False
    )

    # Subject without date - fallback to Date header
    assert (
        is_email_from_prior_day(
            "USPS Notification",
            "Wed, 07 Oct 2026 07:00:00 -0400",
            today,
        )
        is True
    )
    assert (
        is_email_from_prior_day(
            "USPS Notification",
            "Thu, 08 Oct 2026 07:00:00 -0400",
            today,
        )
        is False
    )

    # Date header with naive timezone / no tz
    assert (
        is_email_from_prior_day(
            None,
            "07 Oct 2026 07:00:00",
            today,
        )
        is True
    )
    assert (
        is_email_from_prior_day(
            None,
            "08 Oct 2026 07:00:00",
            today,
        )
        is False
    )

    # Invalid / missing Date header and no subject date
    assert (
        is_email_from_prior_day("USPS Notification", "Invalid Date Header", today)
        is False
    )
    assert is_email_from_prior_day(None, None, today) is False
