"""Tests for Post DE Briefankündigung shipper."""

import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    CONF_DURATION,
    CONF_FORWARDING_HEADER,
)
from custom_components.mail_and_packages.shippers.post_de import PostDEShipper
from custom_components.mail_and_packages.utils.cache import EmailCache


@pytest.mark.asyncio
async def test_post_de_shipper_basic(hass):
    """Test PostDEShipper basic initialization."""
    shipper = PostDEShipper(hass, {})
    assert shipper.name == "post_de"
    assert shipper.handles_sensor("post_de_mail") is True
    assert shipper.handles_sensor("other") is False


@pytest.mark.asyncio
async def test_post_de_no_mail(hass):
    """Test PostDEShipper when no Briefankündigung mail is found."""
    shipper = PostDEShipper(
        hass,
        {
            "image_path": "test/path/post_de/",
            "post_de_image": "post_de_deliveries.gif",
            "forwarded_emails": [],
        },
    )

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[None])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.post_de.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.post_de.shutil.copyfile"),
    ):
        result = await shipper.process(mock_account, "today", "post_de_mail")
        assert result["post_de_mail"] == 0


@pytest.mark.asyncio
async def test_post_de_search_error(hass):
    """Test PostDEShipper with search error."""
    shipper = PostDEShipper(hass, {})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="BAD", lines=[])

    result = await shipper.process(mock_account, "today", "post_de_mail")
    assert result["post_de_mail"] == 0


@pytest.mark.asyncio
async def test_post_de_mkdir_error(hass):
    """Test PostDEShipper with directory creation error."""
    shipper = PostDEShipper(hass, {"image_path": "/root/test"})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.is_dir",
            return_value=False,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.mkdir",
            side_effect=OSError("Permission denied"),
        ),
    ):
        result = await shipper.process(mock_account, "today", "post_de_mail")
        assert result["post_de_mail"] == 0


@pytest.mark.asyncio
async def test_post_de_with_valid_images(hass):
    """Test PostDEShipper when valid inline base64 images are found."""
    shipper = PostDEShipper(
        hass,
        {
            "image_path": "test/path/post_de/",
            "post_de_image": "post_de_deliveries.gif",
            CONF_DURATION: 5,
        },
    )

    # HTML with inline image: 1 large valid one (200x150) and 1 small logo (50x50)
    # The payload is base64 encoded png/jpeg.
    # We will mock Image.open to return custom size for each call
    html_content = """
    <html>
        <body>
            <img src="cid:image1.png">
            <img src="cid:image2.png">
        </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(html_content, "html"))

    # Part 1: large image (200x150)
    image1_part = MIMEText("", _subtype="png")
    image1_part.set_type("image/png")
    image1_part.set_payload("valid_large_image_data")
    msg.attach(image1_part)

    # Part 2: small logo (50x50)
    image2_part = MIMEText("", _subtype="png")
    image2_part.set_type("image/png")
    image2_part.set_payload("small_logo_data")
    msg.attach(image2_part)

    msg_bytes = msg.as_bytes()

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", msg_bytes]
    )

    # We want to mock Image.open size
    mock_image_large = MagicMock()
    mock_image_large.size = (200, 150)
    mock_image_small = MagicMock()
    mock_image_small.size = (50, 50)

    def mock_open_write(self, mode="r", *args, **kwargs):
        return io.BytesIO()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.post_de.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.Image.open",
            side_effect=[mock_image_large, mock_image_small],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.Path.open",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.random_filename",
            return_value="random.png",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.resize_images",
            return_value=["test/path/post_de/post_de/random.png"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.generate_delivery_gif",
        ),
    ):
        result = await shipper.process(mock_account, "today", "post_de_mail")
        # should only count the large image
        assert result["post_de_mail"] == 1


@pytest.mark.asyncio
async def test_post_de_resize_error(hass):
    """Test PostDEShipper GIF generation ValueError handling."""
    shipper = PostDEShipper(
        hass,
        {
            "image_path": "test/path/post_de/",
            "post_de_image": "post_de_deliveries.gif",
            CONF_DURATION: 5,
        },
    )

    msg = MIMEMultipart("alternative")
    image_part = MIMEText("", _subtype="png")
    image_part.set_type("image/png")
    image_part.set_payload("image_data")
    msg.attach(image_part)
    msg_bytes = msg.as_bytes()

    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", msg_bytes]
    )

    mock_image = MagicMock()
    mock_image.size = (200, 150)

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.post_de.cleanup_images"),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.Image.open",
            return_value=mock_image,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.Path.open",
            new_callable=MagicMock,
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.random_filename",
            return_value="random.png",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.resize_images",
            return_value=["test/path/post_de/post_de/random.png"],
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.generate_delivery_gif",
            side_effect=ValueError("GIF error"),
        ),
    ):
        result = await shipper.process(mock_account, "today", "post_de_mail")
        # should still count the mail piece even if GIF generation fails
        assert result["post_de_mail"] == 1


@pytest.mark.asyncio
async def test_post_de_forwarded_emails(hass):
    """Test PostDEShipper prepends forwarded emails correctly."""
    shipper = PostDEShipper(
        hass,
        {
            "forwarded_emails": ["forward@test.com"],
            "image_path": "test/",
        },
    )
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[])

    with patch(
        "custom_components.mail_and_packages.shippers.post_de.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "post_de_mail")
        search_addresses = mock_search.call_args[0][1]
        assert "forward@test.com" in search_addresses
        assert "ankuendigung@brief.deutschepost.de" in search_addresses


@pytest.mark.asyncio
async def test_post_de_forwarding_header_mode(hass):
    """Test PostDEShipper with forwarding header config (native search, pass header)."""
    shipper = PostDEShipper(
        hass,
        {
            CONF_FORWARDING_HEADER: "X-SimpleLogin-Original-From",
            "forwarded_emails": ["ignored@test.com"],
            "image_path": "test/",
        },
    )
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[])

    with patch(
        "custom_components.mail_and_packages.shippers.post_de.email_search",
        return_value=("OK", [None]),
    ) as mock_search:
        await shipper.process(mock_account, "today", "post_de_mail")
        search_addresses = mock_search.call_args[0][1]
        assert "ignored@test.com" not in search_addresses
        assert "ankuendigung@brief.deutschepost.de" in search_addresses
        assert mock_search.call_args[0][4] == "X-SimpleLogin-Original-From"


@pytest.mark.asyncio
async def test_post_de_ignores_since_date(hass):
    """Test PostDEShipper ignores since_date and uses current date for search."""
    shipper = PostDEShipper(hass, {"image_path": "test/"})
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[])

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.get_formatted_date",
            return_value="15-Jun-2026",
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.email_search",
            return_value=("OK", [None]),
        ) as mock_search,
    ):
        await shipper.process_batch(
            mock_account,
            "today",
            ["post_de_mail"],
            EmailCache(mock_account),
            since_date="01-Jun-2026",
        )
        # Search date should be current formatted date (15-Jun-2026), ignoring since_date
        assert mock_search.call_args[0][2] == "15-Jun-2026"


@pytest.mark.asyncio
async def test_post_de_generate_mp4_grid(hass):
    """Test PostDEShipper generates MP4 and grid images when enabled."""
    shipper = PostDEShipper(
        hass,
        {
            "image_path": "test/",
            "post_de_image": "post_de_deliveries.gif",
            "generate_mp4": True,
            "generate_grid": True,
        },
    )
    mock_account = AsyncMock()
    mock_account.search.return_value = MagicMock(result="OK", lines=[b"1"])
    mock_account.fetch.return_value = MagicMock(
        result="OK", lines=[b"RFC822", b"no mail"]
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.post_de.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.post_de.shutil.copyfile"),
        patch(
            "custom_components.mail_and_packages.shippers.post_de._generate_mp4",
        ) as mock_mp4,
        patch(
            "custom_components.mail_and_packages.shippers.post_de.generate_grid_img",
        ) as mock_grid,
    ):
        result = await shipper.process(mock_account, "today", "post_de_mail")
        mock_mp4.assert_called_once()
        mock_grid.assert_called_once()
        assert result["post_de_grid_image_name"] == "post_de_deliveries_grid.png"


@pytest.mark.asyncio
async def test_post_de_copy_nomail_image_os_error(hass, caplog):
    """Test PostDEShipper _copy_nomail_image logs error on OSError."""
    shipper = PostDEShipper(hass, {})
    with patch.object(hass, "async_add_executor_job", side_effect=OSError("Disk Full")):
        await shipper._copy_nomail_image("test/", "test.gif", None)
        assert "Error attempting to copy Post DE image" in caplog.text


@pytest.mark.asyncio
async def test_post_de_process_with_cache(hass):
    """Test PostDEShipper processing uses EmailCache."""
    shipper = PostDEShipper(
        hass,
        {
            "image_path": "test/path/",
            "post_de_image": "post_de_deliveries.gif",
        },
    )
    mock_account = AsyncMock()

    cache = EmailCache(mock_account)
    cache._cache_rfc822["1"] = (
        "OK",
        [b"RFC822", b"Subject: Briefankuendigung\n\nNo mail today"],
    )

    with (
        patch(
            "custom_components.mail_and_packages.shippers.post_de.email_search",
            new_callable=AsyncMock,
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.post_de.anyio.Path.is_dir",
            return_value=True,
        ),
        patch("custom_components.mail_and_packages.shippers.post_de.cleanup_images"),
        patch("custom_components.mail_and_packages.shippers.post_de.shutil.copyfile"),
    ):
        result = await shipper.process(
            mock_account, "today", "post_de_mail", cache=cache
        )
        assert result["post_de_mail"] == 0
