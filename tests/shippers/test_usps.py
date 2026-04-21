"""Tests for USPS shipper utilities."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_GRID_IMAGE_NAME,
    CONF_DURATION,
)
from custom_components.mail_and_packages.shippers.usps import USPSShipper
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
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
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
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
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
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
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
        assert "forward@test.com" in mock_search.call_args[0][1]


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
        search_addresses = mock_search.call_args[0][1]
        assert "forward@test.com" in search_addresses
        assert "other@test.com" in search_addresses


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
            "custom_components.mail_and_packages.shippers.usps.io_save_file",
            side_effect=TypeError("Expected bytes"),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.usps.random_filename",
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
        "custom_components.mail_and_packages.shippers.usps.io_save_file",
        side_effect=OSError("Permission denied"),
    ):
        count, images = await shipper._extract_jpeg_attachment(part, "test/", 0, [])
        assert count == 0


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
