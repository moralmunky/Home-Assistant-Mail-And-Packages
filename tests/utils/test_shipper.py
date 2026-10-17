"""Tests for shipper utilities."""

import base64
import io
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from custom_components.mail_and_packages.const import CAMERA_EXTRACTION_CONFIG
from custom_components.mail_and_packages.utils.cache import EmailCache
from custom_components.mail_and_packages.utils.shipper import (
    _image_subtypes,
    generic_delivery_image_extraction,
    get_tracking,
    save_image_data_to_disk,
)

SAVE_TARGET = (
    "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk"
)


def _synthetic_image(fmt: str) -> bytes:
    """Return a tiny generated image (no real photo or email content)."""
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buf, format=fmt)
    return buf.getvalue()


PNG_BYTES = _synthetic_image("PNG")
JPEG_BYTES = _synthetic_image("JPEG")
IMAGE_BY_SUBTYPE = {
    "png": PNG_BYTES,
    "jpeg": JPEG_BYTES,
    "jpg": JPEG_BYTES,
    "pjpeg": JPEG_BYTES,
}


def _cid_message(subtype: str, cid: str = "deliveryProofLabel") -> bytes:
    """Build a related message with one inline image of the given MIME subtype."""
    msg = MIMEMultipart("related")
    msg.attach(MIMEText(f'<html><body><img src="cid:{cid}"></body></html>', "html"))
    image = MIMEImage(IMAGE_BY_SUBTYPE[subtype], _subtype=subtype)
    image.add_header("Content-ID", f"<{cid}>")
    msg.attach(image)
    return msg.as_bytes()


def _attachment_message(subtype: str, filename: str) -> bytes:
    """Build a mixed message with one attached image."""
    msg = MIMEMultipart("mixed")
    msg.attach(MIMEText("Body", "plain"))
    image = MIMEImage(IMAGE_BY_SUBTYPE[subtype], _subtype=subtype)
    image.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(image)
    return msg.as_bytes()


def _html_message(subtype: str) -> bytes:
    """Build an HTML-only message with a base64 data URI image."""
    data = base64.b64encode(IMAGE_BY_SUBTYPE[subtype]).decode()
    html = f'<html><body><img src="data:image/{subtype};base64,{data}"></body></html>'
    return MIMEText(html, "html").as_bytes()


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
async def test_get_tracking_subject_mime_encoded():
    """Test get_tracking decodes a MIME-encoded subject before matching."""
    mock_acc = AsyncMock()
    raw = (
        b"Subject: =?UTF-8?q?USPS=C2=AE_Item_Delivered,_Front_Door/Porch_"
        b"9200000000000000001?=\n =?UTF-8?q?0000042?=\n\nBody"
    )

    with patch(
        "custom_components.mail_and_packages.utils.shipper.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", [raw])
        result = await get_tracking("1", mock_acc, r"9[2345]\d{15,26}")
        assert result == ["92000000000000000010000042"]


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


def test_save_image_data_to_disk_rejects_empty_data(caplog):
    """Empty image data must not be written to disk.

    Regression test: a bare `data:image/jpeg;base64,` URI in email HTML
    decodes to b"" — writing it produced a 0-byte "delivery photo" that the
    camera then served as a broken image (HTTP 500 pre-placeholder-fallback).
    """
    caplog.set_level("DEBUG")
    with patch("custom_components.mail_and_packages.utils.shipper.Path") as mock_path:
        assert save_image_data_to_disk("fedex", "/p/fedex/photo.jpg", b"") is False
        assert save_image_data_to_disk("fedex", "/p/fedex/photo.jpg", None) is False
        mock_path.return_value.open.assert_not_called()
        assert "No image data extracted" in caplog.text


def test_extract_from_html_skips_empty_base64_before_real_image():
    """An empty base64 data URI must not shadow a real photo after it.

    Regression test: matches[0] was taken blindly, so an email whose HTML
    contains a bare `data:image/jpeg;base64,` spacer BEFORE the actual
    delivery photo discarded the real image (save of b"" failed and the
    whole HTML pass returned False).
    """
    real_jpeg_b64 = "aGVsbG8="  # b"hello" — content is irrelevant, size isn't
    html = (
        '<img src="data:image/jpeg;base64," />'
        f'<img src="data:image/jpeg;base64,{real_jpeg_b64}" />'
    )
    sdata = f"Content-Type: text/html\n\n{html}".encode()

    with patch(
        "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk",
        return_value=True,
    ) as mock_save:
        result = generic_delivery_image_extraction(
            sdata,
            "/p/",
            "photo.jpg",
            "fedex",
            "jpeg",
        )

    assert result is True
    mock_save.assert_called_once()
    assert mock_save.call_args[0][2] == b"hello"


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
            sdata,
            "/p/",
            "i.jpg",
            "t",
            "jpeg",
            cid_name="bad",
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
            sdata,
            "/path/",
            "img.jpg",
            "test_shipper",
            "jpeg",
            cid_name="delivery_img",
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
            sdata,
            "/path/",
            "img.jpg",
            "test_shipper",
            "jpeg",
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


@pytest.mark.asyncio
async def test_get_tracking_non_bytes():
    """Test get_tracking skips non-bytes response parts (Line 35)."""
    mock_acc = AsyncMock()
    # mock_fetch returns (status, lines)
    with patch(
        "custom_components.mail_and_packages.utils.shipper.email_fetch",
        new_callable=AsyncMock,
    ) as mock_fetch:
        mock_fetch.return_value = ("OK", ["not bytes"])
        result = await get_tracking("1", mock_acc, r"(\d+)")
        assert result == []


@pytest.mark.asyncio
async def test_extract_from_html_decode_error(caplog):
    """Test _extract_from_html error handling (Line 225-229)."""
    caplog.set_level("ERROR")
    # Well-formed base64 charset so the (non-empty) match reaches b64decode,
    # which is mocked to raise — exercising the error-handling branch.
    sdata = b'Content-Type: text/html\n\n<html><body><img src="data:image/jpeg;base64,YWJjZA=="></body></html>'
    with patch("base64.b64decode", side_effect=TypeError("Mocked error")):
        result = generic_delivery_image_extraction(sdata, "/p/", "i.jpg", "t", "jpeg")
        assert result is False
        assert "Error saving t delivery photo from base64" in caplog.text


@pytest.mark.asyncio
async def test_extract_from_attachments_no_filename():
    """Test _extract_from_attachments skips part with no filename (Line 247)."""
    sdata = b"Content-Type: image/jpeg\n\nimgdata"
    result = generic_delivery_image_extraction(
        sdata,
        "/p/",
        "i.jpg",
        "t",
        "jpeg",
        attachment_filename_pattern="test",
    )
    assert result is False


@pytest.mark.asyncio
async def test_extract_from_attachments_pattern_mismatch():
    """Test _extract_from_attachments skips part with pattern mismatch (Line 249)."""
    sdata = (
        b"Content-Type: image/jpeg\n"
        b'Content-Disposition: attachment; filename="wrong.jpg"\n\n'
        b"imgdata"
    )
    result = generic_delivery_image_extraction(
        sdata,
        "/p/",
        "i.jpg",
        "t",
        "jpeg",
        attachment_filename_pattern="right",
    )
    assert result is False


@pytest.mark.asyncio
async def test_extract_from_attachments_error(caplog):
    """Test _extract_from_attachments error handling (Line 255-262)."""
    caplog.set_level("ERROR")
    sdata = (
        b"Content-Type: image/jpeg\n"
        b'Content-Disposition: attachment; filename="right.jpg"\n\n'
        b"imgdata"
    )
    with patch(
        "custom_components.mail_and_packages.utils.shipper.save_image_data_to_disk",
        side_effect=OSError("Mocked error"),
    ):
        result = generic_delivery_image_extraction(
            sdata,
            "/p/",
            "i.jpg",
            "t",
            "jpeg",
            attachment_filename_pattern="right",
        )
        assert result is False
        assert "Error saving t delivery photo to" in caplog.text


@pytest.mark.asyncio
async def test_get_tracking_with_cache():
    """Test get_tracking with EmailCache (Line 38)."""
    mock_acc = AsyncMock()
    cache = EmailCache(mock_acc)
    # Populate cache
    cache._cache_rfc822["1"] = (
        "OK",
        [b"Subject: UPS: 1Z1234567890123456\n\nBody"],
    )

    result = await get_tracking("1", mock_acc, "1Z?[0-9A-Z]{16}", cache=cache)
    assert result == ["1Z1234567890123456"]


@pytest.mark.parametrize(
    ("image_type", "expected"),
    [
        ("png", ("png",)),
        ("jpeg", ("jpeg", "jpg", "pjpeg")),
        ("jpg", ("jpeg", "jpg", "pjpeg")),
        ("JPEG", ("jpeg", "jpg", "pjpeg")),
        (["png", "jpeg"], ("png", "jpeg", "jpg", "pjpeg")),
        (("png", "jpg"), ("png", "jpeg", "jpg", "pjpeg")),
        (["png", "png"], ("png",)),
    ],
)
def test_image_subtypes_normalizes_str_and_sequences(image_type, expected):
    """A string or a list of types normalizes to the accepted MIME subtypes."""
    assert _image_subtypes(image_type) == expected


@pytest.mark.parametrize("subtype", ["png", "jpeg", "jpg", "pjpeg"])
def test_extraction_cid_accepts_png_and_jpeg(subtype):
    """CID pass saves the inline image whichever accepted type it carries."""
    sdata = _cid_message(subtype)
    expected = IMAGE_BY_SUBTYPE[subtype]
    with patch(SAVE_TARGET, return_value=True) as mock_save:
        result = generic_delivery_image_extraction(
            sdata,
            "/p/",
            "i.jpg",
            "walmart",
            ["png", "jpeg"],
            cid_name="deliveryProofLabel",
        )
    assert result is True
    assert mock_save.call_args[0][2] == expected


@pytest.mark.parametrize("subtype", ["png", "jpeg", "jpg", "pjpeg"])
def test_extraction_base64_accepts_png_and_jpeg(subtype):
    """Base64 pass decodes a data URI of any accepted type."""
    sdata = _html_message(subtype)
    expected = IMAGE_BY_SUBTYPE[subtype]
    with patch(SAVE_TARGET, return_value=True) as mock_save:
        result = generic_delivery_image_extraction(
            sdata, "/p/", "i.jpg", "walmart", ["png", "jpeg"]
        )
    assert result is True
    assert mock_save.call_args[0][2] == expected


@pytest.mark.parametrize("subtype", ["png", "jpeg", "jpg", "pjpeg"])
def test_extraction_attachment_accepts_png_and_jpeg(subtype):
    """Attachment pass saves a matching attachment of any accepted type."""
    sdata = _attachment_message(subtype, "delivery_photo.bin")
    expected = IMAGE_BY_SUBTYPE[subtype]
    with patch(SAVE_TARGET, return_value=True) as mock_save:
        result = generic_delivery_image_extraction(
            sdata,
            "/p/",
            "i.jpg",
            "walmart",
            ["png", "jpeg"],
            attachment_filename_pattern="delivery",
        )
    assert result is True
    assert mock_save.call_args[0][2] == expected


@pytest.mark.parametrize("subtype", ["png", "jpeg"])
def test_extraction_cid_wrong_content_id_returns_false(subtype):
    """A non-matching Content-ID is not extracted, whatever the image type."""
    sdata = _cid_message(subtype, cid="somethingElse")
    with patch(SAVE_TARGET, return_value=True) as mock_save:
        result = generic_delivery_image_extraction(
            sdata,
            "/p/",
            "i.jpg",
            "walmart",
            ["png", "jpeg"],
            cid_name="deliveryProofLabel",
        )
    assert result is False
    mock_save.assert_not_called()


@pytest.mark.parametrize(
    ("config_type", "part_subtype", "expected"),
    [
        ("jpeg", "jpeg", True),
        ("jpeg", "png", False),
        ("png", "png", True),
        ("png", "jpeg", False),
    ],
)
def test_extraction_string_image_type_stays_strict(config_type, part_subtype, expected):
    """A plain string config (UPS, FedEx, ButcherBox) still accepts only its own type."""
    sdata = _cid_message(part_subtype, cid="deliveryPhoto")
    with patch(SAVE_TARGET, return_value=True):
        result = generic_delivery_image_extraction(
            sdata, "/p/", "i.jpg", "ups", config_type, cid_name="deliveryPhoto"
        )
    assert result is expected


@pytest.mark.parametrize("subtype", ["png", "jpeg"])
def test_walmart_config_extracts_photo_of_either_type(subtype):
    """The shipped Walmart config extracts the photo whether it is PNG or JPEG."""
    walmart = CAMERA_EXTRACTION_CONFIG["walmart"]
    sdata = _cid_message(subtype, cid=walmart["cid_name"])
    with patch(SAVE_TARGET, return_value=True) as mock_save:
        result = generic_delivery_image_extraction(
            sdata,
            "/p/",
            "i.jpg",
            "walmart",
            walmart["image_type"],
            cid_name=walmart["cid_name"],
        )
    assert result is True
    assert mock_save.call_args[0][2] == IMAGE_BY_SUBTYPE[subtype]


def test_other_shippers_keep_string_image_types():
    """UPS, FedEx and ButcherBox configs are unchanged plain strings."""
    for shipper in ("ups", "fedex", "butcherbox"):
        assert CAMERA_EXTRACTION_CONFIG[shipper]["image_type"] == "jpeg"
