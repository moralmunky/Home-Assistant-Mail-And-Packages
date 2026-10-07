"""Tests for the bpost shipper."""

import datetime
import re
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mail_and_packages.const import (
    ATTR_COUNT,
    ATTR_TRACKING,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
)
from custom_components.mail_and_packages.shippers.generic import GenericShipper
from custom_components.mail_and_packages.shippers.generic.helpers import (
    _compile_patterns,
    _extract_email_text,
    _matches_date_or_body,
)

DELIVERING_SUBJECT = (
    "Nous livrerons votre colis BAD IDEA COMPANY LTD entre 09:00 et 10:30"
)
DELIVERED_SUBJECT = "Votre colis de DHL a été livré"
TRACKING_DELIVERING = "32321234567890"
TRACKING_DELIVERED = "CE123456789BE"
TEST_DATE = "08-Sep-2026"

EMAIL_DELIVERING_TODAY = f"""From: bpost <noreply@communication.bpost.be>
To: testuser@example.com
Subject: {DELIVERING_SUBJECT}
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: quoted-printable

<html>
<body>
    <p>Nous livrerons votre colis BAD IDEA COMPANY LTD entre 09:00 et 10:30</p>
    <p>Votre colis sera livr=C3=A9 aujourd=E2=80=99hui</p>
    <p>Bonjour Test User, Votre colis est en route et vous sera livr=C3=A9 aujourd=E2=80=99hui.</p>
    <p>Code-barres {TRACKING_DELIVERING}</p>
</body>
</html>
""".encode()

EMAIL_DELIVERING_FUTURE_DATE = f"""From: bpost <noreply@communication.bpost.be>
To: testuser@example.com
Subject: Nous livrerons votre colis le 15 octobre
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: quoted-printable

<html>
<body>
    <p>Nous livrerons votre colis BAD IDEA COMPANY LTD le 15 octobre</p>
    <p>Votre colis sera livr=C3=A9 le 15 octobre.</p>
    <p>Code-barres {TRACKING_DELIVERING}</p>
</body>
</html>
""".encode()

EMAIL_DELIVERED = f"""From: bpost <noreply@communication.bpost.be>
To: testuser@example.com
Subject: =?utf-8?Q?Votre_colis_de_DHL_a_=C3=A9t=C3=A9_livr=C3=A9?=
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: quoted-printable

<html>
<body>
    <p>Votre colis de DHL a =C3=A9t=C3=A9 livr=C3=A9</p>
    <p>Bonjour Test User, Votre colis de la part de DHL a =C3=A9t=C3=A9 livr=C3=A9 avec succ=C3=A8s.</p>
    <p>Code-barres {TRACKING_DELIVERED}</p>
</body>
</html>
""".encode()


def test_bpost_registration():
    """Verify bpost sensor and shipper registrations."""
    sensor_keys = {
        "bpost_delivered",
        "bpost_delivering",
        "bpost_packages",
    }

    assert sensor_keys <= SENSOR_DATA.keys()
    assert sensor_keys <= SENSOR_TYPES.keys()
    assert "bpost_tracking" in SENSOR_DATA
    assert "bpost" in SHIPPERS
    assert SENSOR_DATA["bpost_packages"] == {}


async def _process(hass, raw: bytes, subject_header: str, sensor_type: str) -> dict:
    """Run GenericShipper against synthetic email data."""
    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.search.email_search",
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.helpers.email_fetch",
            return_value=("OK", [raw]),
        ),
        patch(
            "custom_components.mail_and_packages.utils.email.email_fetch",
            return_value=("OK", [raw]),
        ),
        patch(
            "custom_components.mail_and_packages.utils.shipper.email_fetch",
            return_value=("OK", [raw]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.helpers.email_fetch_headers",
            return_value=("OK", [f"Subject: {subject_header}\r\n".encode()]),
        ),
    ):
        return await shipper.process(
            account=mock_account,
            date=TEST_DATE,
            sensor_type=sensor_type,
        )


@pytest.mark.asyncio
async def test_bpost_delivering(hass):
    """Test bpost delivering today email parsing."""
    result = await _process(
        hass,
        EMAIL_DELIVERING_TODAY,
        DELIVERING_SUBJECT,
        "bpost_delivering",
    )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [TRACKING_DELIVERING]


EMAIL_DELIVERING_EXPLICIT_DATE = f"""From: bpost <noreply@communication.bpost.be>
To: testuser@example.com
Subject: Nous livrerons votre colis BAD IDEA COMPANY LTD le 08-09-2026 entre 09:00 et 10:30
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8
Content-Transfer-Encoding: quoted-printable

<html>
<body>
    <p>Nous livrerons votre colis BAD IDEA COMPANY LTD le 08-09-2026 entre 09:00 et 10:30</p>
    <p>Code-barres {TRACKING_DELIVERING}</p>
</body>
</html>
""".encode()


@pytest.mark.asyncio
async def test_bpost_delivering_explicit_date_today(hass):
    """Test bpost email with delivery date matching today is counted."""
    with patch(
        "custom_components.mail_and_packages.shippers.generic.helpers.get_today",
        return_value=datetime.date(2026, 9, 8),
    ):
        result = await _process(
            hass,
            EMAIL_DELIVERING_EXPLICIT_DATE,
            "Nous livrerons votre colis BAD IDEA COMPANY LTD le 08-09-2026 entre 09:00 et 10:30",
            "bpost_delivering",
        )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [TRACKING_DELIVERING]


@pytest.mark.asyncio
async def test_bpost_delivering_future_date_not_counted(hass):
    """Test bpost email with future date is not counted."""
    with patch(
        "custom_components.mail_and_packages.shippers.generic.helpers.get_today",
        return_value=datetime.date(2026, 9, 8),
    ):
        result = await _process(
            hass,
            EMAIL_DELIVERING_FUTURE_DATE,
            "Nous livrerons votre colis le 15 octobre",
            "bpost_delivering",
        )

    assert result[ATTR_COUNT] == 0
    assert result[ATTR_TRACKING] == []


@pytest.mark.asyncio
async def test_bpost_delivered(hass):
    """Test bpost delivered email parsing."""
    result = await _process(
        hass,
        EMAIL_DELIVERED,
        DELIVERED_SUBJECT,
        "bpost_delivered",
    )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [TRACKING_DELIVERED]


@pytest.mark.asyncio
async def test_bpost_delivering_with_cache_and_multipart(hass):
    """Test bpost delivering email with email cache and non-text parts."""
    raw_multipart = (
        b"From: bpost <noreply@communication.bpost.be>\r\n"
        b"Subject: " + DELIVERING_SUBJECT.encode() + b"\r\n"
        b'Content-Type: multipart/mixed; boundary="boundary"\r\n\r\n'
        b"--boundary\r\n"
        b"Content-Type: image/png\r\n\r\n"
        b"fakeimagebytes\r\n"
        b"--boundary\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Votre colis sera livre aujourd\xe2\x80\x99hui\r\n"
        b"--boundary--"
    )

    async def _mock_fetch(eid, query, shipper=None):
        if "HEADER" in query:
            return ("OK", [f"Subject: {DELIVERING_SUBJECT}\r\n".encode()])
        return ("OK", ["not_bytes", raw_multipart])

    mock_cache = AsyncMock()
    mock_cache.fetch.side_effect = _mock_fetch

    shipper = GenericShipper(hass, {})
    mock_account = AsyncMock()

    with (
        patch(
            "custom_components.mail_and_packages.shippers.generic.search.email_search",
            return_value=("OK", [b"1"]),
        ),
        patch(
            "custom_components.mail_and_packages.shippers.generic.helpers.get_tracking",
            return_value=[TRACKING_DELIVERING],
        ),
    ):
        result = await shipper.process(
            account=mock_account,
            date=TEST_DATE,
            sensor_type="bpost_delivering",
            cache=mock_cache,
        )

    assert result[ATTR_COUNT] == 1
    assert result[ATTR_TRACKING] == [TRACKING_DELIVERING]


@pytest.mark.asyncio
async def test_bpost_delivering_pattern_variations(hass):
    """Test _compile_patterns with string, empty, and invalid types."""
    str_patterns = _compile_patterns(r"le\s+(\d{2}-\d{2}-\d{4})")
    assert len(str_patterns) == 1

    empty_patterns = _compile_patterns(None)
    assert empty_patterns == []

    # Test _matches_date_or_body with no match
    matched = _matches_date_or_body(
        "no match text",
        body_patterns=[],
        date_patterns=str_patterns,
        today_date=datetime.date(2026, 9, 8),
    )
    assert not matched

    # Test _matches_date_or_body with valid date pattern but unparsable date
    bad_date_pattern = [re.compile(r"date:\s*(\w+)", re.IGNORECASE)]
    matched_unparsable = _matches_date_or_body(
        "date: notadate",
        body_patterns=[],
        date_patterns=bad_date_pattern,
        today_date=datetime.date(2026, 9, 8),
    )
    assert not matched_unparsable

    # Test _extract_email_text when decoding payload raises exception
    with patch("email.message.Message.get_payload", side_effect=UnicodeError):
        raw_msg = b"From: test@example.com\r\nContent-Type: text/plain\r\n\r\ntest"
        extracted = _extract_email_text(raw_msg)
        assert extracted == ""
