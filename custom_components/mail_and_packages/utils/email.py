"""Email parsing and validation utilities for Mail and Packages."""

import email
import logging
import re
from typing import Any

from aioimaplib import IMAP4_SSL
from voluptuous import Email, MultipleInvalid, Schema

from custom_components.mail_and_packages.const import SENSOR_DATA

from .imap import email_fetch

_LOGGER = logging.getLogger(__name__)


def validate_email_address(email_address: str) -> bool:
    """Validate the format of an email address.

    Args:
        email_address (str): The email address to validate.

    Returns:
        bool: `True` if the email address is valid, `False` otherwise.

    """
    try:
        schema = Schema(Email())  # pylint: disable=no-value-for-parameter
        schema(email_address)
    except MultipleInvalid:
        _LOGGER.error("'%s' does not look like a valid email address", email_address)
        return False

    _LOGGER.debug("%s is a valid email address", email_address)

    return True


def generate_service_email_domains(amazon_fwds: list) -> set[str]:
    """Generate a set of service email domains from amazon domains and SENSOR_DATA.

    Returns:
        set[str]: A set of unique email domains.

    """
    domains = {fwd.split("@")[1] for fwd in amazon_fwds if "@" in fwd}
    for sensor in SENSOR_DATA.values():
        for address in sensor.get("email", []):
            if "@" not in address:
                continue
            domains.add(address.split("@")[1])
    return domains


def _match_patterns(
    text: str, patterns: list[re.Pattern], body_count: bool
) -> tuple[int, int | None]:
    """Apply patterns to text and return occurrence count and extracted value.

    Returns:
        tuple[int, int | None]: (count_of_matches, extracted_value)

    """
    local_count = 0
    extracted_value = None

    for pattern in patterns:
        if body_count:
            if (found := pattern.search(text)) and len(found.groups()) > 0:
                _LOGGER.debug(
                    "Found (%s) in email result: %s",
                    pattern.pattern,
                    found.groups(),
                )
                extracted_value = int(found.group(1))
        elif (found := pattern.findall(text)) and len(found) > 0:
            _LOGGER.debug(
                "Found (%s) in email %s times.",
                pattern.pattern,
                len(found),
            )
            local_count += len(found)

    return local_count, extracted_value


async def _scan_email_for_text(
    account: type[IMAP4_SSL],
    email_id: str,
    patterns: list[re.Pattern],
    body_count: bool,
) -> tuple[int, int | None]:
    """Scan a single email for terms.

    Returns:
        tuple[int, int | None]: (total_matches, last_extracted_value)

    """
    total_matches = 0
    last_value = None

    data = (await email_fetch(account, email_id, "(RFC822)"))[1]
    for response_part in data:
        if not isinstance(response_part, (bytes, bytearray)):
            continue

        msg = email.message_from_bytes(response_part)

        for part in msg.walk():
            if part.get_content_type() not in ["text/html", "text/plain"]:
                continue

            email_msg = part.get_payload(decode=True)
            try:
                email_msg = email_msg.decode("utf-8", "ignore")
            except (AttributeError, UnicodeError):
                continue

            matches, value = _match_patterns(email_msg, patterns, body_count)
            total_matches += matches
            if value is not None:
                last_value = value

    return total_matches, last_value


async def find_text(
    sdata: Any,
    account: type[IMAP4_SSL],
    search_terms: list,
    body_count: bool,
) -> int:
    """Filter for specific words in email."""
    _LOGGER.debug("Searching for (%s) in (%s) emails", search_terms, len(sdata))
    mail_list = sdata[0].split()
    count = 0

    # Pre-compile regex patterns once
    patterns = [re.compile(rf"{term}") for term in search_terms]

    for i in mail_list:
        matches, value = await _scan_email_for_text(account, i, patterns, body_count)

        if body_count:
            # If extracting a value, "last found value wins" (updates count)
            if value is not None:
                count = value
        else:
            # If counting occurrences, accumulate
            count += matches

    return count
