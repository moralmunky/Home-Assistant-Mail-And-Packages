"""Tests for the bpost shipper."""

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


@pytest.mark.asyncio
async def test_bpost_delivering_future_date_not_counted(hass):
    """Test bpost email without 'aujourd’hui' is not counted."""
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
