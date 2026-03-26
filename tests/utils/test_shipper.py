"""Tests for shipper utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mail_and_packages.utils.shipper import (
    generic_delivery_image_extraction,
    get_tracking,
    save_image_data_to_disk,
)


@pytest.mark.asyncio
async def test_get_tracking_subject():
    """Test get_tracking finds number in subject."""
    mock_acc = AsyncMock()
    sdata = "1"
    the_format = r"(1Z?[0-9A-Z]{16})"

    # Mock email fetch returning a message with tracking in subject
    mock_res = MagicMock()
    mock_res.result = "OK"
    # email_fetch returns (status, lines) where lines contains the email bytes
    mock_res.lines = [b"Subject: UPS: 1Z1234567890123456\n\nBody"]
    mock_acc.fetch.return_value = mock_res

    with patch(
        "custom_components.mail_and_packages.utils.shipper.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", [b"Subject: UPS: 1Z1234567890123456\n\nBody"])
        result = await get_tracking(sdata, mock_acc, the_format)
        assert result == ["1Z1234567890123456"]


@pytest.mark.asyncio
async def test_get_tracking_body_ups():
    """Test get_tracking finds UPS number in body (simplified logic)."""
    mock_acc = AsyncMock()
    sdata = "1"
    the_format = "1Z?[0-9A-Z]{16}"

    with patch(
        "custom_components.mail_and_packages.utils.shipper.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = (
            "OK",
            [b"Subject: Test\n\nYour UPS tracking is 1Z1234567890123456 here."],
        )
        result = await get_tracking(sdata, mock_acc, the_format)
        assert result == ["1Z1234567890123456"]


@pytest.mark.asyncio
async def test_get_tracking_body_generic():
    """Test get_tracking finds number in body for non-UPS."""
    mock_acc = AsyncMock()
    sdata = "1"
    the_format = r"(\d{10})"  # simple 10 digit

    # Needs to be a multipart message to trigger msg.walk() logic
    email_content = (
        b"Subject: Test\n"
        b"Content-Type: multipart/alternative; boundary=bound\n\n"
        b"--bound\n"
        b"Content-Type: text/plain\n\n"
        b"Number: 1234567890\n"
        b"--bound--"
    )

    with patch(
        "custom_components.mail_and_packages.utils.shipper.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", [email_content])
        result = await get_tracking(sdata, mock_acc, the_format)
        assert result == ["1234567890"]


@pytest.mark.asyncio
async def test_get_tracking_dhl():
    """Test get_tracking finds number with DHL special handling."""
    mock_acc = AsyncMock()
    sdata = "1"
    # the_format needs to have a space to trigger the split logic
    # and a capture group if used with findall in a way that split is needed
    the_format = r"(DHL \d{10})"
    email_content = b"Content-Type: text/plain\n\nYour DHL 1234567890 is here"
    with patch(
        "custom_components.mail_and_packages.utils.shipper.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", [email_content])
        result = await get_tracking(sdata, mock_acc, the_format)
        assert result == ["1234567890"]


def test_save_image_data_to_disk_errors(caplog):
    """Test save_image_data_to_disk error paths."""
    caplog.set_level("ERROR")
    # File write error
    with patch("custom_components.mail_and_packages.utils.shipper.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.parent.is_dir.return_value = True
        mock_path_obj.open.side_effect = OSError("Write failed")
        mock_path.return_value = mock_path_obj

        assert save_image_data_to_disk("test", "/p", b"d") is False
        assert "Error saving test delivery photo" in caplog.text


@pytest.mark.asyncio
async def test_generic_image_extraction_errors(caplog):
    """Test generic_delivery_image_extraction error paths."""
    caplog.set_level("ERROR")
    sdata = b'Content-Type: text/html\n\n<html><body><img src="cid:bad"></body></html>'
    # CID exists but saving fails
    with (
        patch(
            "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk",
            return_value=False,
        ),
        patch("email.message_from_bytes") as mock_msg_from_bytes,
    ):
        mock_msg = MagicMock()
        mock_parts = [MagicMock(), MagicMock()]
        mock_parts[0].get_content_type.return_value = "image/jpeg"
        mock_parts[0].get.return_value = "<bad>"
        mock_parts[0].get_payload.return_value = b"imgdata"

        mock_parts[1].get_content_type.return_value = "text/html"
        # part_content decoding:
        mock_parts[
            1
        ].get_payload.return_value = b'<html><body><img src="cid:bad"></body></html>'

        mock_msg.walk.return_value = mock_parts
        mock_msg_from_bytes.return_value = mock_msg

        result = generic_delivery_image_extraction(
            sdata, "/p/", "i.jpg", "t", "jpeg", cid_name="bad"
        )
        assert result is False


@pytest.mark.asyncio
async def test_get_tracking_unicode_error(caplog):
    """Test get_tracking unicode error branch."""
    mock_acc = AsyncMock()
    sdata = "1"
    the_format = "1Z?[0-9A-Z]{16}"  # UPS format triggers specific branch
    caplog.set_level("DEBUG")

    with (
        patch(
            "custom_components.mail_and_packages.utils.shipper.email_fetch",
            new_callable=AsyncMock,
        ) as mock_fetch,
        patch(
            "custom_components.mail_and_packages.utils.shipper.str",
            side_effect=TypeError("Mocked error"),
        ),
    ):
        mock_fetch.return_value = ("OK", [b"some data"])

        result = await get_tracking(sdata, mock_acc, the_format)
        assert result == []
        assert any(
            "Error processing email content" in r.message for r in caplog.records
        )


def test_save_image_data_to_disk_mkdir_error(caplog):
    """Test save_image_data_to_disk mkdir error."""
    caplog.set_level("ERROR")
    with patch("custom_components.mail_and_packages.utils.shipper.Path") as mock_path:
        mock_parent = MagicMock()
        mock_parent.is_dir.return_value = False
        mock_parent.mkdir.side_effect = OSError("Mkdir failed")

        mock_path_obj = MagicMock()
        mock_path_obj.parent = mock_parent
        mock_path.return_value = mock_path_obj

        assert save_image_data_to_disk("test", "/p", b"d") is False
        assert any("Error creating directory" in r.message for r in caplog.records)


def test_save_image_data_to_disk_not_exists(caplog):
    """Test save_image_data_to_disk reports success but file missing."""
    caplog.set_level("ERROR")
    with patch("custom_components.mail_and_packages.utils.shipper.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.parent.is_dir.return_value = True
        mock_path_obj.exists.return_value = False
        mock_path.return_value = mock_path_obj

        assert save_image_data_to_disk("test", "/p", b"d") is False
        assert "File write reported success but file doesn't exist" in caplog.text


@pytest.mark.asyncio
async def test_generic_image_extraction_str_data():
    """Test generic_delivery_image_extraction with string data."""
    sdata = "From: test@test.com\n\nBody"
    with patch("email.message_from_string") as mock_msg_from_string:
        mock_msg = MagicMock()
        mock_msg.walk.return_value = []
        mock_msg_from_string.return_value = mock_msg
        result = generic_delivery_image_extraction(sdata, "/p/", "i.jpg", "t", "jpeg")
        assert result is False
        assert mock_msg_from_string.called


def test_save_image_data_to_disk_success():
    """Test save_image_data_to_disk success path."""
    with patch("custom_components.mail_and_packages.utils.shipper.Path") as mock_path:
        mock_path_obj = MagicMock()
        mock_path_obj.parent.is_dir.return_value = True
        mock_path_obj.exists.return_value = True
        mock_path.return_value = mock_path_obj

        result = save_image_data_to_disk("test_shipper", "/path/to/img.jpg", b"data")
        assert result is True
        assert mock_path_obj.open.called


def test_save_image_data_to_disk_mkdir():
    """Test save_image_data_to_disk creates directory."""
    with patch("custom_components.mail_and_packages.utils.shipper.Path") as mock_path:
        mock_parent = MagicMock()
        mock_parent.is_dir.return_value = False

        mock_path_obj = MagicMock()
        mock_path_obj.parent = mock_parent
        mock_path_obj.exists.return_value = True
        mock_path.return_value = mock_path_obj

        result = save_image_data_to_disk("test_shipper", "/path/to/img.jpg", b"data")
        assert result is True
        assert mock_parent.mkdir.called


@pytest.mark.asyncio
async def test_generic_image_extraction_cid():
    """Test image extraction from CID."""
    # Simple email with CID
    sdata = (
        b"Content-Type: multipart/related; boundary=bound\n\n"
        b"--bound\n"
        b"Content-Type: text/html\n\n"
        b'<html><body><img src="cid:delivery_img"></body></html>\n'
        b"--bound\n"
        b"Content-Type: image/jpeg\n"
        b"Content-ID: <delivery_img>\n\n"
        b"fake_image_data\n"
        b"--bound--"
    )

    with patch(
        "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk",
        return_value=True,
    ) as mock_save:
        result = generic_delivery_image_extraction(
            sdata, "/path/", "img.jpg", "test_shipper", "jpeg", cid_name="delivery_img"
        )
        assert result is True
        assert mock_save.called


@pytest.mark.asyncio
async def test_generic_image_extraction_base64():
    """Test image extraction from base64 HTML."""
    sdata = (
        b"Content-Type: text/html\n\n"
        b'<html><body><img src="data:image/jpeg;base64,ZmFrZV9kYXRh"></body></html>'
    )

    with patch(
        "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk",
        return_value=True,
    ) as mock_save:
        result = generic_delivery_image_extraction(
            sdata, "/path/", "img.jpg", "test_shipper", "jpeg"
        )
        assert result is True
        assert mock_save.called
        # Check that we decoded "fake_data" (base64 of ZmFrZV9kYXRh)
        args = mock_save.call_args
        assert args[0][2] == b"fake_data"


@pytest.mark.asyncio
async def test_generic_image_extraction_attachment():
    """Test image extraction from attachment."""
    sdata = (
        b"Content-Type: multipart/mixed; boundary=bound\n\n"
        b"--bound\n"
        b"Content-Type: text/plain\n\nBody\n"
        b"--bound\n"
        b"Content-Type: image/jpeg\n"
        b'Content-Disposition: attachment; filename="delivery.jpg"\n\n'
        b"attachment_data\n"
        b"--bound--"
    )

    with patch(
        "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk",
        return_value=True,
    ) as mock_save:
        result = generic_delivery_image_extraction(
            sdata,
            "/path/",
            "img.jpg",
            "test_shipper",
            "jpeg",
            attachment_filename_pattern="delivery",
        )
        assert result is True
        assert mock_save.called
