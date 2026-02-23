"""Helper functions for Mail and Packages."""

import datetime
import email
import hashlib
import imaplib
import json
import locale
import logging
import os
import quopri
import re
import subprocess  # nosec
import uuid
from datetime import timezone
from email.header import decode_header
from shutil import copyfile, copytree, which
from typing import Any, List, Optional, Type, Union

import aiohttp
import imageio as io
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from PIL import Image
from resizeimage import resizeimage

from .const import (
    AMAZON_DELIVERED,
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_DOMAINS,
    AMAZON_EMAIL,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_ORDER,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_HUB,
    AMAZON_HUB_BODY,
    AMAZON_HUB_CODE,
    AMAZON_HUB_EMAIL,
    AMAZON_HUB_SUBJECT,
    AMAZON_HUB_SUBJECT_SEARCH,
    AMAZON_IMG_PATTERN,
    AMAZON_LANGS,
    AMAZON_ORDER,
    AMAZON_PACKAGES,
    AMAZON_PATTERN,
    AMAZON_SHIPMENT_TRACKING,
    AMAZON_TIME_PATTERN,
    ATTR_17TRACK_FORWARDED,
    ATTR_AMAZON_COOKIE_TRACKING,
    ATTR_AMAZON_IMAGE,
    ATTR_BODY,
    ATTR_CODE,
    ATTR_COUNT,
    ATTR_EMAIL,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_LLM_ANALYZED,
    ATTR_ORDER,
    ATTR_PATTERN,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    ATTR_UNIVERSAL_TRACKING,
    ATTR_USPS_MAIL,
    CONF_17TRACK_ENABLED,
    CONF_17TRACK_ENTRY_ID,
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_COOKIES,
    CONF_AMAZON_COOKIES_ENABLED,
    CONF_AMAZON_COOKIE_DOMAIN,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_MP4,
    CONF_LLM_API_KEY,
    CONF_LLM_ENABLED,
    CONF_LLM_ENDPOINT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_PATH,
    CONF_SCAN_ALL_EMAILS,
    CONF_TRACKING_FORWARD_ENABLED,
    CONF_TRACKING_SERVICE,
    CONF_TRACKING_SERVICE_ENTRY_ID,
    DEFAULT_AMAZON_DAYS,
    OVERLAY,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
    TRACKING_SERVICES,
    UNIVERSAL_TRACKING_PATTERNS,
)

_LOGGER = logging.getLogger(__name__)

# Config Flow Helpers


def get_resources() -> dict:
    """Resource selection schema.

    Returns dict of user selected sensors
    """
    known_available_resources = {
        sensor_id: sensor.name for sensor_id, sensor in SENSOR_TYPES.items()
    }

    return known_available_resources


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is installed.

    Returns True if ffmpeg is found, False otherwise.
    """
    return which("ffmpeg") is not None


def _test_login_sync(host: str, port: int, user: str, pwd: str) -> bool:
    """Test IMAP login to specified server (blocking).

    Returns success boolean
    """
    # Attempt to catch invalid mail server hosts
    try:
        account = imaplib.IMAP4_SSL(host, port)
    except Exception as err:
        _LOGGER.error("Error connecting into IMAP Server: %s", str(err))
        return False
    # Validate we can login to mail server
    try:
        account.login(user, pwd)
        account.logout()
        return True
    except Exception as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
        try:
            account.logout()
        except Exception:
            pass
        return False


async def _test_login(hass: HomeAssistant, host: str, port: int, user: str, pwd: str) -> bool:
    """Test IMAP login to specified server without blocking the event loop.

    Returns success boolean
    """
    return await hass.async_add_executor_job(_test_login_sync, host, port, user, pwd)


# Email Data helpers


def default_image_path(
    hass: HomeAssistant, config_entry: ConfigEntry  # pylint: disable=unused-argument
) -> str:
    """Return value of the default image path.

    Returns the default path based on logic (placeholder for future code)
    """
    # Return the default
    return "custom_components/mail_and_packages/images/"


def process_emails(hass: HomeAssistant, config: ConfigEntry) -> dict:
    """Process emails and return value.

    Returns dict containing sensor data
    """
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    user = config.get(CONF_USERNAME)
    pwd = config.get(CONF_PASSWORD)
    folder = config.get(CONF_FOLDER)
    resources = config.get(CONF_RESOURCES)

    # Create the dict container
    data = {}

    # Login to email server and select the folder
    account = login(host, port, user, pwd)

    # Do not process if account returns false
    if not account:
        return data

    try:
        return _process_emails_inner(hass, config, account, folder, resources, data)
    finally:
        try:
            account.logout()
        except Exception:
            pass


def _process_emails_inner(
    hass: HomeAssistant,
    config: ConfigEntry,
    account: Any,
    folder: str,
    resources: list,
    data: dict,
) -> dict:
    """Inner email processing logic (called within IMAP session).

    Returns dict containing sensor data
    """
    if not selectfolder(account, folder):
        # Bail out on error
        return data

    # Create image file name dict container
    _image = {}

    # USPS Mail Image name
    image_name = image_file_name(hass, config)
    _LOGGER.debug("Image name: %s", image_name)
    _image[ATTR_IMAGE_NAME] = image_name

    # Amazon delivery image name
    image_name = image_file_name(hass, config, True)
    _LOGGER.debug("Amazon Image Name: %s", image_name)
    _image[ATTR_AMAZON_IMAGE] = image_name

    image_path = config.get(CONF_PATH)
    _LOGGER.debug("Image path: %s", image_path)
    _image[ATTR_IMAGE_PATH] = image_path
    data.update(_image)

    # Only update sensors we're intrested in
    for sensor in resources:
        try:
            fetch(hass, config, account, data, sensor)
        except Exception as err:
            _LOGGER.error(
                "Error processing sensor %s: %s: %s",
                sensor,
                type(err).__name__,
                err,
            )
            data[sensor] = 0

    # --- Advanced Tracking Features (all opt-in) ---

    # Collect all known tracking numbers from carrier-specific sensors
    known_tracking = _collect_known_tracking(data)

    # Universal email scanning (opt-in, local-only)
    if config.get(CONF_SCAN_ALL_EMAILS, False):
        try:
            _LOGGER.debug("Universal email scanning enabled")
            universal_result = scan_all_emails_for_tracking(account, known_tracking)
            data["email_tracking_numbers"] = universal_result[ATTR_COUNT]
            data[ATTR_UNIVERSAL_TRACKING] = universal_result[ATTR_TRACKING]
            data["universal_carrier_map"] = universal_result.get("carrier_map", {})

            # Add universal findings to known tracking for dedup downstream
            known_tracking.extend(universal_result[ATTR_TRACKING])
        except Exception as err:
            _LOGGER.error(
                "Error in universal email scanning: %s: %s",
                type(err).__name__,
                err,
            )
            data["email_tracking_numbers"] = 0

    # Tracking service forwarding (opt-in, supports 17track/AfterShip/AliExpress)
    # Also supports legacy CONF_17TRACK_ENABLED for backward compat
    forward_enabled = config.get(
        CONF_TRACKING_FORWARD_ENABLED,
        config.get(CONF_17TRACK_ENABLED, False),
    )
    if forward_enabled:
        try:
            service_key = config.get(CONF_TRACKING_SERVICE, "seventeentrack")
            entry_id = config.get(
                CONF_TRACKING_SERVICE_ENTRY_ID,
                config.get(CONF_17TRACK_ENTRY_ID, ""),
            )

            # Gather all tracking numbers to forward
            all_to_forward = list(data.get(ATTR_UNIVERSAL_TRACKING, []))
            carrier_map = data.get("universal_carrier_map", {})

            # Also include carrier-specific tracking numbers
            for key, value in data.items():
                if key.endswith("_tracking") and isinstance(value, list):
                    for num in value:
                        if num not in all_to_forward:
                            all_to_forward.append(num)
                            carrier_prefix = key.replace("_tracking", "")
                            if num not in carrier_map:
                                carrier_map[num] = carrier_prefix.upper()

            # Get previously forwarded (stored in hass.data)
            already_forwarded = _get_forwarded_set(hass, config)

            data["tracking_service_forwarded"] = len(all_to_forward)
            data[ATTR_17TRACK_FORWARDED] = all_to_forward
            data["_tracking_service_key"] = service_key
            data["_tracking_entry_id"] = entry_id
            data["_tracking_carrier_map"] = carrier_map
            data["_tracking_already_forwarded"] = already_forwarded
        except Exception as err:
            _LOGGER.error(
                "Error in tracking service forwarding: %s: %s",
                type(err).__name__,
                err,
            )
            data["tracking_service_forwarded"] = 0

    # LLM analysis is handled async in the coordinator (see __init__.py)
    # We store the config flags so the coordinator can pick them up
    if config.get(CONF_LLM_ENABLED, False):
        data["_llm_config"] = {
            "provider": config.get(CONF_LLM_PROVIDER, "ollama"),
            "endpoint": config.get(CONF_LLM_ENDPOINT, ""),
            "api_key": config.get(CONF_LLM_API_KEY, ""),
            "model": config.get(CONF_LLM_MODEL, ""),
            "known_tracking": known_tracking,
        }

    # Amazon cookie scraping is handled async in the coordinator
    if config.get(CONF_AMAZON_COOKIES_ENABLED, False):
        data["_amazon_cookie_config"] = {
            "cookies": config.get(CONF_AMAZON_COOKIES, ""),
            "domain": config.get(CONF_AMAZON_COOKIE_DOMAIN, "amazon.com"),
        }

    # Copy image file to www directory if enabled
    if config.get(CONF_ALLOW_EXTERNAL):
        copy_images(hass, config)

    return data


def _collect_known_tracking(data: dict) -> list:
    """Collect all tracking numbers already found by carrier-specific sensors.

    Returns flat list of all known tracking numbers.
    """
    known = []
    for key, value in data.items():
        if key.endswith("_tracking") and isinstance(value, list):
            known.extend(value)
    return known


def _get_forwarded_set(hass: HomeAssistant, config: ConfigEntry) -> set:
    """Get the set of tracking numbers already forwarded to a tracking service.

    Stored in hass.data to persist across updates within a session.
    Returns set of tracking number strings.
    """
    from .const import DOMAIN  # avoid circular at module level

    domain_data = hass.data.get(DOMAIN, {})
    forwarded_key = "_tracking_forwarded_set"
    if forwarded_key not in domain_data:
        domain_data[forwarded_key] = set()
    return domain_data[forwarded_key]


def copy_images(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Copy images to www directory if enabled."""
    paths = []
    src = f"{hass.config.path()}/{config.get(CONF_PATH)}"
    dst = f"{hass.config.path()}/www/mail_and_packages/"

    # Setup paths list
    paths.append(dst)
    paths.append(dst + "amazon/")

    # Clean up the destination directory
    for path in paths:
        # Path check
        path_check = os.path.exists(path)
        if not path_check:
            try:
                os.makedirs(path)
            except OSError as err:
                _LOGGER.error("Problem creating: %s, error returned: %s", path, err)
                return
        cleanup_images(path)

    try:
        copytree(src, dst, dirs_exist_ok=True)
    except Exception as err:
        _LOGGER.error(
            "Problem copying files from %s to %s error returned: %s", src, dst, err
        )
        return


def image_file_name(
    hass: HomeAssistant, config: ConfigEntry, amazon: bool = False
) -> str:
    """Determine if filename is to be changed or not.

    Returns filename
    """
    mail_none = None
    path = None
    image_name = None

    if amazon:
        mail_none = f"{os.path.dirname(__file__)}/no_deliveries.jpg"
        image_name = "no_deliveries.jpg"
        path = f"{hass.config.path()}/{config.get(CONF_PATH)}amazon"
    else:
        path = f"{hass.config.path()}/{config.get(CONF_PATH)}"
        if config.get(CONF_CUSTOM_IMG):
            mail_none = config.get(CONF_CUSTOM_IMG_FILE)
        else:
            mail_none = f"{os.path.dirname(__file__)}/mail_none.gif"
        image_name = os.path.split(mail_none)[1]

    # Path check
    path_check = os.path.exists(path)
    if not path_check:
        try:
            os.makedirs(path)
        except OSError as err:
            _LOGGER.error("Problem creating: %s, error returned: %s", path, err)
            return image_name

    # SHA1 file hash check
    try:
        sha1 = hash_file(mail_none)
    except OSError as err:
        _LOGGER.error("Problem accessing file: %s, error returned: %s", mail_none, err)
        return image_name

    ext = None
    ext = ".jpg" if amazon else ".gif"

    for file in os.listdir(path):
        if file.endswith(".gif") or (file.endswith(".jpg") and amazon):
            try:
                created = datetime.datetime.fromtimestamp(
                    os.path.getctime(os.path.join(path, file))
                ).strftime("%d-%b-%Y")
            except OSError as err:
                _LOGGER.error(
                    "Problem accessing file: %s, error returned: %s", file, err
                )
                return image_name
            today = get_formatted_date()
            _LOGGER.debug("Created: %s, Today: %s", created, today)
            # If image isn't mail_none and not created today,
            # return a new filename
            if sha1 != hash_file(os.path.join(path, file)) and today != created:
                image_name = f"{str(uuid.uuid4())}{ext}"
            else:
                image_name = file

    # If we find no images in the image directory generate a new filename
    if image_name in mail_none:
        image_name = f"{str(uuid.uuid4())}{ext}"
    _LOGGER.debug("Image Name: %s", image_name)

    # Insert place holder image
    _LOGGER.debug("Copying %s to %s", mail_none, os.path.join(path, image_name))

    copyfile(mail_none, os.path.join(path, image_name))

    return image_name


def hash_file(filename: str) -> str:
    """Return the SHA-1 hash of the file passed into it.

    Returns hash of file as string
    """
    # make a hash object
    the_hash = hashlib.sha1()  # nosec

    # open file for reading in binary mode
    with open(filename, "rb") as file:

        # loop till the end of the file
        chunk = 0
        while chunk != b"":
            # read only 1024 bytes at a time
            chunk = file.read(1024)
            the_hash.update(chunk)

    # return the hex representation of digest
    return the_hash.hexdigest()


def fetch(
    hass: HomeAssistant, config: ConfigEntry, account: Any, data: dict, sensor: str
) -> int:
    """Fetch data for a single sensor, including any sensors it depends on.

    Returns integer of sensor passed to it
    """
    img_out_path = f"{hass.config.path()}/{config.get(CONF_PATH)}"
    gif_duration = config.get(CONF_DURATION)
    generate_mp4 = config.get(CONF_GENERATE_MP4)
    amazon_fwds = config.get(CONF_AMAZON_FWDS)
    image_name = data[ATTR_IMAGE_NAME]
    amazon_image_name = data[ATTR_AMAZON_IMAGE]
    amazon_days = config.get(CONF_AMAZON_DAYS)

    if config.get(CONF_CUSTOM_IMG):
        nomail = config.get(CONF_CUSTOM_IMG_FILE)
    else:
        nomail = None

    if sensor in data:
        return data[sensor]

    count = {}

    if sensor == "usps_mail":
        count[sensor] = get_mails(
            account,
            img_out_path,
            gif_duration,
            image_name,
            generate_mp4,
            nomail,
        )
    elif sensor == AMAZON_PACKAGES:
        count[sensor] = get_items(
            account=account,
            param=ATTR_COUNT,
            fwds=amazon_fwds,
            days=amazon_days,
        )
        count[AMAZON_ORDER] = get_items(
            account=account,
            param=ATTR_ORDER,
            fwds=amazon_fwds,
            days=amazon_days,
        )
    elif sensor == AMAZON_HUB:
        value = amazon_hub(account, amazon_fwds)
        count[sensor] = value[ATTR_COUNT]
        count[AMAZON_HUB_CODE] = value[ATTR_CODE]
    elif sensor == AMAZON_EXCEPTION:
        info = amazon_exception(account, amazon_fwds)
        count[sensor] = info[ATTR_COUNT]
        count[AMAZON_EXCEPTION_ORDER] = info[ATTR_ORDER]
    elif sensor == "amazon_cookie_packages":
        # Handled async in coordinator, just return existing value
        if sensor in data:
            return data[sensor]
        count[sensor] = 0
    elif "_packages" in sensor:
        prefix = sensor.replace("_packages", "")
        delivering = fetch(hass, config, account, data, f"{prefix}_delivering")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        count[sensor] = delivering + delivered
    elif "_delivering" in sensor:
        prefix = sensor.replace("_delivering", "")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        info = get_count(account, sensor, True)
        count[sensor] = max(0, info[ATTR_COUNT] - delivered)
        count[f"{prefix}_tracking"] = info[ATTR_TRACKING]
    elif sensor == "zpackages_delivered":
        count[sensor] = 0  # initialize the variable
        for shipper in SHIPPERS:
            delivered = f"{shipper}_delivered"
            if delivered in data and delivered != sensor:
                count[sensor] += fetch(hass, config, account, data, delivered)
    elif sensor == "zpackages_transit":
        total = 0
        for shipper in SHIPPERS:
            delivering = f"{shipper}_delivering"
            if delivering in data and delivering != sensor:
                total += fetch(hass, config, account, data, delivering)
        count[sensor] = max(0, total)
    elif sensor == "email_tracking_numbers":
        # Handled in process_emails, just return existing value
        if sensor in data:
            return data[sensor]
        count[sensor] = 0
    elif sensor == "tracking_service_forwarded":
        # Handled in process_emails, just return existing value
        if sensor in data:
            return data[sensor]
        count[sensor] = 0
    elif sensor == "mail_updated":
        count[sensor] = update_time()
    else:
        count[sensor] = get_count(
            account, sensor, False, img_out_path, hass, amazon_image_name
        )[ATTR_COUNT]

    data.update(count)
    _LOGGER.debug("Sensor: %s Count: %s", sensor, str(count[sensor]))
    return count[sensor]


class IMAPAuthError(Exception):
    """Raised when IMAP authentication fails."""


def login(
    host: str, port: int, user: str, pwd: str
) -> Union[bool, Type[imaplib.IMAP4_SSL]]:
    """Login to IMAP server.

    Returns account object or False on network error.
    Raises IMAPAuthError on authentication failure.
    """
    # Catch invalid mail server / host names
    try:
        account = imaplib.IMAP4_SSL(host, port)

    except Exception as err:
        _LOGGER.error("Network error while connecting to server: %s", str(err))
        return False

    # If login fails, raise auth error for credential issues
    try:
        account.login(user, pwd)
    except imaplib.IMAP4.error as err:
        _LOGGER.error("IMAP authentication failed: %s", str(err))
        raise IMAPAuthError(f"Authentication failed: {err}") from err
    except Exception as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
        return False

    return account


def selectfolder(account: Type[imaplib.IMAP4_SSL], folder: str) -> bool:
    """Select folder inside the mailbox."""
    try:
        account.list()
    except Exception as err:
        _LOGGER.error("Error listing folders: %s", str(err))
        return False
    try:
        account.select(folder)
    except Exception as err:
        _LOGGER.error("Error selecting folder: %s", str(err))
        return False
    return True


def get_formatted_date() -> str:
    """Return today in specific format.

    Returns current timestamp as string
    """
    today = datetime.datetime.today().strftime("%d-%b-%Y")
    #
    # for testing
    # today = "11-Jan-2021"
    #
    return today


def update_time() -> Any:
    """Get update time.

    Returns current timestamp as string
    """
    # updated = datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")
    # updated = datetime.datetime.now(timezone.utc).isoformat(timespec="minutes")
    updated = datetime.datetime.now(timezone.utc)

    return updated


def build_search(address: list, date: str, subject: str = None) -> tuple:
    """Build IMAP search query.

    Return tuple of utf8 flag and search query.
    """
    the_date = f"SINCE {date}"
    imap_search = None
    utf8_flag = False
    prefix_list = None
    email_list = None

    if isinstance(address, list):
        if len(address) == 1:
            email_list = address[0]
        else:
            email_list = '" FROM "'.join(address)
            prefix_list = " ".join(["OR"] * (len(address) - 1))
    else:
        email_list = address

    _LOGGER.debug("DEBUG subject: %s", subject)

    if subject is not None:
        if not subject.isascii():
            utf8_flag = True
            # if prefix_list is not None:
            #     imap_search = f"CHARSET UTF-8 {prefix_list}"
            #     imap_search = f'{imap_search} FROM "{email_list} {the_date} SUBJECT'
            # else:
            #     imap_search = (
            #         f"CHARSET UTF-8 FROM {email_list} {the_date} SUBJECT"
            #     )
            imap_search = f"{the_date} SUBJECT"
        else:
            if prefix_list is not None:
                imap_search = f'({prefix_list} FROM "{email_list}" SUBJECT "{subject}" {the_date})'
            else:
                imap_search = f'(FROM "{email_list}" SUBJECT "{subject}" {the_date})'
    else:
        if prefix_list is not None:
            imap_search = f'({prefix_list} FROM "{email_list}" {the_date})'
        else:
            imap_search = f'(FROM "{email_list}" {the_date})'

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    return (utf8_flag, imap_search)


def email_search(
    account: Type[imaplib.IMAP4_SSL], address: list, date: str, subject: str = None
) -> tuple:
    """Search emails with from, subject, senton date.

    Returns a tuple
    """
    utf8_flag, search = build_search(address, date, subject)

    if utf8_flag:
        subject = subject.encode("utf-8")
        account.literal = subject
        try:
            value = account.uid("SEARCH", "CHARSET", "UTF-8", search)
        except Exception as err:
            _LOGGER.warning(
                "Error searching emails with unicode characters: %s", str(err)
            )
            value = "BAD", err.args[0]
    else:
        try:
            value = account.search(None, search)
        except Exception as err:
            _LOGGER.error("Error searching emails: %s", str(err))
            value = "BAD", err.args[0]

    _LOGGER.debug("DEBUG email_search value: %s", value)

    (check, new_value) = value
    if new_value[0] is None:
        _LOGGER.warning("DEBUG email_search value was invalid: None")
        value = (check, [b""])

    return value


def email_fetch(
    account: Type[imaplib.IMAP4_SSL], num: int, parts: str = "(RFC822)"
) -> tuple:
    """Download specified email for parsing.

    Returns tuple
    """
    try:
        value = account.fetch(num, parts)
    except Exception as err:
        _LOGGER.error("Error fetching emails: %s", str(err))
        value = "BAD", err.args[0]

    return value


def get_mails(
    account: Type[imaplib.IMAP4_SSL],
    image_output_path: str,
    gif_duration: int,
    image_name: str,
    gen_mp4: bool = False,
    custom_img: str = None,
) -> int:
    """Create GIF image based on the attachments in the inbox."""
    image_count = 0
    images = []
    images_delete = []
    msg = ""

    _LOGGER.debug("Attempting to find Informed Delivery mail")
    _LOGGER.debug("Informed delivery search date: %s", get_formatted_date())

    (server_response, data) = email_search(
        account,
        SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL],
        get_formatted_date(),
        SENSOR_DATA[ATTR_USPS_MAIL][ATTR_SUBJECT][0],
    )

    # Bail out on error
    if server_response != "OK" or data[0] is None:
        return image_count

    # Check to see if the path exists, if not make it
    if not os.path.isdir(image_output_path):
        try:
            os.makedirs(image_output_path)
        except Exception as err:
            _LOGGER.critical("Error creating directory: %s", str(err))

    # Clean up image directory
    _LOGGER.debug("Cleaning up image directory: %s", str(image_output_path))
    cleanup_images(image_output_path)

    # Copy overlays to image directory
    _LOGGER.debug("Checking for overlay files in: %s", str(image_output_path))
    copy_overlays(image_output_path)

    if server_response == "OK":
        _LOGGER.debug("Informed Delivery email found processing...")
        for num in data[0].split():
            msg = email.message_from_string(
                email_fetch(account, num, "(RFC822)")[1][0][1].decode("utf-8", "ignore")
            )

            # walking through the email parts to find images
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                _LOGGER.debug("Extracting image from email")

                # Sanitize filename to prevent path traversal attacks
                raw_filename = part.get_filename()
                if not raw_filename:
                    continue
                # Strip directory components - only keep the basename
                safe_filename = os.path.basename(raw_filename)
                if not safe_filename:
                    continue
                filepath = os.path.join(image_output_path, safe_filename)
                # Verify the resolved path is within the output directory
                if not os.path.realpath(filepath).startswith(
                    os.path.realpath(image_output_path)
                ):
                    _LOGGER.warning(
                        "Skipping attachment with suspicious filename: %s",
                        raw_filename,
                    )
                    continue

                # Log error message if we are unable to open the filepath for
                # some reason
                try:
                    with open(filepath, "wb") as the_file:
                        the_file.write(part.get_payload(decode=True))
                        images.append(filepath)
                        image_count = image_count + 1
                except Exception as err:
                    _LOGGER.critical("Error opening filepath: %s", str(err))
                    return image_count

        # Remove duplicate images
        _LOGGER.debug("Removing duplicate images.")
        images = list(dict.fromkeys(images))

        # Create copy of image list for deleting temporary images
        images_delete = images[:]

        # Look for mail pieces without images image
        if re.compile(r"\bimage-no-mailpieces?700\.jpg\b").search(str(msg)) is not None:
            images.append(os.path.dirname(__file__) + "/image-no-mailpieces700.jpg")
            image_count = image_count + 1
            _LOGGER.debug("Placeholder image found using: image-no-mailpieces700.jpg.")

        # Remove USPS announcement images
        _LOGGER.debug("Removing USPS announcement images.")
        images = [
            el
            for el in images
            if not any(
                ignore in el
                for ignore in ["mailerProvidedImage", "ra_0", "Mail Attachment.txt"]
            )
        ]
        image_count = len(images)
        _LOGGER.debug("Image Count: %s", str(image_count))

        if image_count > 0:
            all_images = []

            _LOGGER.debug("Resizing images to 724x320...")
            # Resize images to 724x320
            all_images = resize_images(images, 724, 320)

            # Create copy of image list for deleting temporary images
            for image in all_images:
                images_delete.append(image)

            # Create numpy array of images
            _LOGGER.debug("Creating array of image files...")
            all_images = [io.imread(image) for image in all_images]

            try:
                _LOGGER.debug("Generating animated GIF")
                # Use ImageIO to create mail images
                io.mimwrite(
                    os.path.join(image_output_path, image_name),
                    all_images,
                    duration=gif_duration,
                )
                _LOGGER.info("Mail image generated.")
            except Exception as err:
                _LOGGER.error("Error attempting to generate image: %s", str(err))
            for image in images_delete:
                cleanup_images(f"{os.path.split(image)[0]}/", os.path.split(image)[1])

        elif image_count == 0:
            _LOGGER.info("No mail found.")
            if os.path.isfile(image_output_path + image_name):
                _LOGGER.debug("Removing " + image_output_path + image_name)
                cleanup_images(image_output_path, image_name)

            try:
                _LOGGER.debug("Copying nomail gif")
                if custom_img is not None:
                    nomail = custom_img
                else:
                    nomail = os.path.dirname(__file__) + "/mail_none.gif"
                copyfile(nomail, image_output_path + image_name)
            except Exception as err:
                _LOGGER.error("Error attempting to copy image: %s", str(err))

        if gen_mp4:
            _generate_mp4(image_output_path, image_name)

    return image_count


def _generate_mp4(path: str, image_file: str) -> None:
    """Generate mp4 from gif.

    use a subprocess so we don't lock up the thread
    comamnd: ffmpeg -f gif -i infile.gif outfile.mp4
    """
    gif_image = os.path.join(path, image_file)
    mp4_file = os.path.join(path, image_file.replace(".gif", ".mp4"))
    filecheck = os.path.isfile(mp4_file)
    _LOGGER.debug("Generating mp4: %s", mp4_file)
    if filecheck:
        cleanup_images(*os.path.split(mp4_file))
        _LOGGER.debug("Removing old mp4: %s", mp4_file)

    try:
        subprocess.call(
            [
                "ffmpeg",
                "-f",
                "gif",
                "-i",
                gif_image,
                "-pix_fmt",
                "yuv420p",
                "-filter:v",
                "crop='floor(in_w/2)*2:floor(in_h/2)*2'",
                mp4_file,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        _LOGGER.warning("ffmpeg MP4 generation timed out after 120 seconds")


def resize_images(images: list, width: int, height: int) -> list:
    """Resize images.

    This should keep the aspect ratio of the images
    Returns list of images
    """
    all_images = []
    for image in images:
        try:
            with open(image, "rb") as fd_img:
                try:
                    img = Image.open(fd_img)
                    img = resizeimage.resize_contain(img, [width, height])
                    pre = os.path.splitext(image)[0]
                    image = pre + ".gif"
                    img.save(image, img.format)
                    fd_img.close()
                    all_images.append(image)
                except Exception as err:
                    _LOGGER.error(
                        "Error attempting to read image %s: %s", str(image), str(err)
                    )
                    continue
        except Exception as err:
            _LOGGER.error("Error attempting to open image %s: %s", str(image), str(err))
            continue

    return all_images


def copy_overlays(path: str) -> None:
    """Copy overlay images to image output path."""
    overlays = OVERLAY
    existing_files = os.listdir(path) if os.path.isdir(path) else []
    check = all(item in existing_files for item in overlays)

    # Copy files if they are missing
    if not check:
        for file in overlays:
            _LOGGER.debug("Copying file to: %s", str(path + file))
            copyfile(
                os.path.dirname(__file__) + "/" + file,
                path + file,
            )


def cleanup_images(path: str, image: Optional[str] = None) -> None:
    """Clean up image storage directory.

    Only supose to delete .gif, .mp4, and .jpg files
    """
    if image is not None:
        try:
            os.remove(path + image)
        except Exception as err:
            _LOGGER.error("Error attempting to remove image: %s", str(err))
        return

    for file in os.listdir(path):
        if file.endswith(".gif") or file.endswith(".mp4") or file.endswith(".jpg"):
            try:
                os.remove(path + file)
            except Exception as err:
                _LOGGER.error("Error attempting to remove found image: %s", str(err))


def get_count(
    account: Type[imaplib.IMAP4_SSL],
    sensor_type: str,
    get_tracking_num: bool = False,
    image_path: Optional[str] = None,
    hass: Optional[HomeAssistant] = None,
    amazon_image_name: Optional[str] = None,
) -> dict:
    """Get Package Count.

    Returns dict of sensor data
    """
    count = 0
    tracking = []
    result = {}
    today = get_formatted_date()
    track = None
    found = []

    # Return Amazon delivered info
    if sensor_type == AMAZON_DELIVERED:
        result[ATTR_COUNT] = amazon_search(account, image_path, hass, amazon_image_name)
        result[ATTR_TRACKING] = ""
        return result

    # Bail out if unknown sensor type
    if sensor_type not in SENSOR_DATA:
        _LOGGER.warning("Sensor type not found in SENSOR_DATA: %s", sensor_type)
        result[ATTR_COUNT] = count
        result[ATTR_TRACKING] = ""
        return result
    if ATTR_EMAIL not in SENSOR_DATA[sensor_type]:
        _LOGGER.debug("No email config for sensor type: %s", sensor_type)
        result[ATTR_COUNT] = count
        result[ATTR_TRACKING] = ""
        return result

    subjects = SENSOR_DATA[sensor_type][ATTR_SUBJECT]
    for subject in subjects:

        _LOGGER.debug(
            "Attempting to find mail from (%s) with subject (%s)",
            SENSOR_DATA[sensor_type][ATTR_EMAIL],
            subject,
        )

        (server_response, data) = email_search(
            account, SENSOR_DATA[sensor_type][ATTR_EMAIL], today, subject
        )
        if server_response == "OK" and data[0] is not None:
            if ATTR_BODY in SENSOR_DATA[sensor_type].keys():
                count += find_text(
                    data, account, SENSOR_DATA[sensor_type][ATTR_BODY][0]
                )
            else:
                count += len(data[0].split())

            _LOGGER.debug(
                "Search for (%s) with subject (%s) results: %s count: %s",
                SENSOR_DATA[sensor_type][ATTR_EMAIL],
                subject,
                data[0],
                count,
            )
            found.append(data[0])

    if (
        ATTR_PATTERN
        in SENSOR_DATA[f"{'_'.join(sensor_type.split('_')[:-1])}_tracking"].keys()
    ):
        track = SENSOR_DATA[f"{'_'.join(sensor_type.split('_')[:-1])}_tracking"][
            ATTR_PATTERN
        ][0]

    if track is not None and get_tracking_num and count > 0:
        for sdata in found:
            tracking.extend(get_tracking(sdata, account, track))
        tracking = list(dict.fromkeys(tracking))

    if len(tracking) > 0:
        # Use tracking numbers found for count (more accurate)
        count = len(tracking)

    result[ATTR_TRACKING] = tracking

    result[ATTR_COUNT] = count
    return result


def get_tracking(
    sdata: Any, account: Type[imaplib.IMAP4_SSL], the_format: Optional[str] = None
) -> list:
    """Parse tracking numbers from email.

    Returns list of tracking numbers
    """
    tracking = []
    pattern = None
    mail_list = sdata.split()
    _LOGGER.debug("Searching for tracking numbers in %s messages...", len(mail_list))

    pattern = re.compile(rf"{the_format}")
    for i in mail_list:
        data = email_fetch(account, i, "(RFC822)")[1]
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                _LOGGER.debug("Checking message subject...")

                # Search subject for a tracking number
                email_subject = msg["subject"]
                if (found := pattern.findall(email_subject)) and len(found) > 0:
                    _LOGGER.debug(
                        "Found tracking number in email subject: (%s)",
                        found[0],
                    )
                    if found[0] not in tracking:
                        tracking.append(found[0])
                    continue

                # Search in email body for tracking number
                _LOGGER.debug("Checking message body using %s ...", the_format)
                for part in msg.walk():
                    _LOGGER.debug("Content type: %s", part.get_content_type())
                    if part.get_content_type() not in ["text/html", "text/plain"]:
                        continue
                    email_msg = part.get_payload(decode=True)
                    email_msg = email_msg.decode("utf-8", "ignore")
                    if (found := pattern.findall(email_msg)) and len(found) > 0:
                        # DHL is special
                        if " " in the_format:
                            found[0] = found[0].split(" ")[1]

                        _LOGGER.debug(
                            "Found tracking number in email body: %s", found[0]
                        )
                        if found[0] not in tracking:
                            tracking.append(found[0])
                        continue

    if len(tracking) == 0:
        _LOGGER.debug("No tracking numbers found")

    return tracking


def find_text(sdata: Any, account: Type[imaplib.IMAP4_SSL], search: str) -> int:
    """Filter for specific words in email.

    Return count of items found as integer
    """
    _LOGGER.debug("Searching for (%s) in (%s) emails", search, len(sdata))
    mail_list = sdata[0].split()
    count = 0
    found = None

    for i in mail_list:
        data = email_fetch(account, i, "(RFC822)")[1]
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                for part in msg.walk():
                    _LOGGER.debug("Content type: %s", part.get_content_type())
                    if part.get_content_type() not in ["text/html", "text/plain"]:
                        continue
                    email_msg = part.get_payload(decode=True)
                    email_msg = email_msg.decode("utf-8", "ignore")
                    pattern = re.compile(rf"{search}")
                    if (found := pattern.findall(email_msg)) and len(found) > 0:
                        _LOGGER.debug(
                            "Found (%s) in email %s times.", search, str(len(found))
                        )
                        count += len(found)

    _LOGGER.debug("Search for (%s) count results: %s", search, count)
    return count


def amazon_search(
    account: Type[imaplib.IMAP4_SSL],
    image_path: str,
    hass: HomeAssistant,
    amazon_image_name: str,
) -> int:
    """Find Amazon Delivered email.

    Returns email found count as integer
    """
    _LOGGER.debug("Searching for Amazon delivered email(s)...")

    subjects = AMAZON_DELIVERED_SUBJECT
    today = get_formatted_date()
    count = 0

    for domain in AMAZON_DOMAINS:
        for subject in subjects:
            email_address = AMAZON_EMAIL + domain
            _LOGGER.debug("Amazon email search address: %s", str(email_address))

            (server_response, data) = email_search(
                account, email_address, today, subject
            )

            if server_response == "OK" and data[0] is not None:
                count += len(data[0].split())
                _LOGGER.debug("Amazon delivered email(s) found: %s", count)
                get_amazon_image(data[0], account, image_path, hass, amazon_image_name)

    return count


def get_amazon_image(
    sdata: Any,
    account: Type[imaplib.IMAP4_SSL],
    image_path: str,
    hass: HomeAssistant,
    image_name: str,
) -> None:
    """Find Amazon delivery image."""
    _LOGGER.debug("Searching for Amazon image in emails...")

    img_url = None
    mail_list = sdata.split()
    _LOGGER.debug("HTML Amazon emails found: %s", len(mail_list))

    for i in mail_list:
        data = email_fetch(account, i, "(RFC822)")[1]
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                _LOGGER.debug("Email Multipart: %s", str(msg.is_multipart()))
                _LOGGER.debug("Content Type: %s", str(msg.get_content_type()))

                for part in msg.walk():
                    if part.get_content_type() != "text/html":
                        continue
                    _LOGGER.debug("Processing HTML email...")
                    part = part.get_payload(decode=True)
                    part = part.decode("utf-8", "ignore")
                    pattern = re.compile(rf"{AMAZON_IMG_PATTERN}")
                    found = pattern.findall(part)
                    for url in found:
                        if url[1] != "us-prod-temp.s3.amazonaws.com":
                            continue
                        img_url = url[0] + url[1] + url[2]
                        _LOGGER.debug("Amazon img URL: %s", img_url)
                        break

    if img_url is not None:
        # Download the image we found
        hass.async_create_task(download_img(img_url, image_path, image_name))


async def download_img(img_url: str, img_path: str, img_name: str) -> None:
    """Download image from url."""
    img_path = f"{img_path}amazon/"
    filepath = f"{img_path}{img_name}"

    async with aiohttp.ClientSession() as session:
        async with session.get(img_url.replace("&amp;", "&")) as resp:
            if resp.status != 200:
                _LOGGER.error("Problem downloading file http error: %s", resp.status)
                return
            content_type = resp.headers["content-type"]
            _LOGGER.debug("URL content-type: %s", content_type)
            if "image" in content_type:
                data = await resp.read()
                _LOGGER.debug("Downloading image to: %s", filepath)
                with open(filepath, "wb") as the_file:
                    the_file.write(data)
                    _LOGGER.debug("Amazon image downloaded")


def _process_amazon_forwards(email_list: Union[List[str], None]) -> list:
    """Process amazon forward emails.

    Returns list of email addresses
    """
    result = []
    if email_list:
        for fwd in email_list:
            if fwd and fwd != '""' and fwd not in result:
                result.append(fwd)

    return result


def amazon_hub(account: Type[imaplib.IMAP4_SSL], fwds: Optional[str] = None) -> dict:
    """Find Amazon Hub info emails.

    Returns dict of sensor data
    """
    email_addresses = _process_amazon_forwards(fwds)
    body_regex = AMAZON_HUB_BODY
    subject_regex = AMAZON_HUB_SUBJECT_SEARCH
    info = {}
    today = get_formatted_date()

    email_addresses.extend(AMAZON_HUB_EMAIL)
    _LOGGER.debug("[Hub] Amazon email list: %s", str(email_addresses))

    for address in email_addresses:
        (server_response, sdata) = email_search(
            account, address, today, subject=AMAZON_HUB_SUBJECT
        )

        # Bail out on error
        if server_response != "OK" or sdata[0] is None:
            return info

        if len(sdata) == 0:
            info[ATTR_COUNT] = 0
            info[ATTR_CODE] = []
            return info

        found = []
        id_list = sdata[0].split()
        _LOGGER.debug("Amazon hub emails found: %s", str(len(id_list)))
        for i in id_list:
            data = email_fetch(account, i, "(RFC822)")[1]
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Get combo number from subject line
                    email_subject = msg["subject"]
                    pattern = re.compile(rf"{subject_regex}")
                    search = pattern.search(email_subject)
                    if search is not None:
                        if len(search.groups()) > 1:
                            found.append(search.group(3))
                            continue

                    # Get combo number from message body
                    try:
                        email_msg = quopri.decodestring(
                            str(msg.get_payload(0))
                        )  # msg.get_payload(0).encode('utf-8')
                    except Exception as err:
                        _LOGGER.debug("Problem decoding email message: %s", str(err))
                        continue
                    email_msg = email_msg.decode("utf-8", "ignore")
                    pattern = re.compile(rf"{body_regex}")
                    search = pattern.search(email_msg)
                    if search is not None:
                        if len(search.groups()) > 1:
                            found.append(search.group(2))

    info[ATTR_COUNT] = len(found)
    info[ATTR_CODE] = found

    return info


def amazon_exception(
    account: Type[imaplib.IMAP4_SSL], fwds: Optional[str] = None
) -> dict:
    """Find Amazon exception emails.

    Returns dict of sensor data
    """
    order_number = []
    tfmt = get_formatted_date()
    count = 0
    info = {}
    domains = list(AMAZON_DOMAINS)  # Copy to avoid mutating module-level list
    if isinstance(fwds, list):
        for fwd in fwds:
            if fwd and fwd != '""' and fwd not in domains:
                domains.append(fwd)
                _LOGGER.debug("Amazon email adding %s to list", str(fwd))

    _LOGGER.debug("Amazon domains to be checked: %s", str(domains))

    for domain in domains:
        if "@" in domain:
            email_address = domain.strip('"')
            _LOGGER.debug("Amazon email search address: %s", str(email_address))
        else:
            email_address = []
            email_address.append(f"{AMAZON_EMAIL}{domain}")
            _LOGGER.debug("Amazon email search address: %s", str(email_address))

        (server_response, sdata) = email_search(
            account, email_address, tfmt, AMAZON_EXCEPTION_SUBJECT
        )

        if server_response == "OK":
            count += len(sdata[0].split())
            _LOGGER.debug("Found %s Amazon exceptions", count)
            order_numbers = get_tracking(sdata[0], account, AMAZON_PATTERN)
            for order in order_numbers:
                order_number.append(order)

    info[ATTR_COUNT] = count
    info[ATTR_ORDER] = order_number

    return info


def get_items(
    account: Type[imaplib.IMAP4_SSL],
    param: str = None,
    fwds: Optional[str] = None,
    days: int = DEFAULT_AMAZON_DAYS,
) -> Union[List[str], int]:
    """Parse Amazon emails for delivery date and order number.

    Returns list of order numbers or email count as integer
    """
    _LOGGER.debug("Attempting to find Amazon email with item list ...")

    # Limit to past 3 days (plan to make this configurable)
    past_date = datetime.date.today() - datetime.timedelta(days=days)
    tfmt = past_date.strftime("%d-%b-%Y")
    deliveries_today = []
    order_number = []
    domains = _process_amazon_forwards(fwds)

    for main_domain in AMAZON_DOMAINS:
        domains.append(main_domain)

    _LOGGER.debug("Amazon email list: %s", str(domains))

    for domain in domains:
        if "@" in domain:
            email_address = domain.strip('"')
            _LOGGER.debug("Amazon email search address: %s", str(email_address))
        else:
            email_address = []
            addresses = AMAZON_SHIPMENT_TRACKING
            for address in addresses:
                email_address.append(f"{address}@{domain}")
            _LOGGER.debug("Amazon email search address: %s", str(email_address))

        (server_response, sdata) = email_search(account, email_address, tfmt)

        if server_response == "OK":
            mail_ids = sdata[0]
            id_list = mail_ids.split()
            _LOGGER.debug("Amazon emails found: %s", str(len(id_list)))
            for i in id_list:
                data = email_fetch(account, i, "(RFC822)")[1]
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        _LOGGER.debug("Email Multipart: %s", str(msg.is_multipart()))
                        _LOGGER.debug("Content Type: %s", str(msg.get_content_type()))

                        # Get order number from subject line
                        encoding = decode_header(msg["subject"])[0][1]
                        if encoding is not None:
                            email_subject = decode_header(msg["subject"])[0][0].decode(
                                encoding, "ignore"
                            )
                        else:
                            email_subject = decode_header(msg["subject"])[0][0]
                        _LOGGER.debug("Amazon Subject: %s", str(email_subject))
                        pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

                        # Don't add the same order number twice
                        if (
                            (found := pattern.findall(email_subject))
                            and len(found) > 0
                            and found[0] not in order_number
                        ):
                            order_number.append(found[0])

                        try:
                            email_msg = quopri.decodestring(str(msg.get_payload(0)))
                        except Exception as err:
                            _LOGGER.debug(
                                "Problem decoding email message: %s", str(err)
                            )
                            continue
                        email_msg = email_msg.decode("utf-8", "ignore")

                        _LOGGER.debug("RAW EMAIL: %s", email_msg)

                        # Check message body for order number
                        if (
                            (found := pattern.findall(email_msg))
                            and len(found) > 0
                            and found[0] not in order_number
                        ):
                            order_number.append(found[0])

                        for search in AMAZON_TIME_PATTERN:
                            _LOGGER.debug("Looking for: %s", search)
                            if search not in email_msg:
                                continue

                            start = email_msg.find(search) + len(search)
                            end = -1
                            if email_msg.find("Previously expected:") != -1:
                                end = email_msg.find("Previously expected:")
                            elif email_msg.find("Track your") != -1:
                                end = email_msg.find("Track your")
                            elif email_msg.find("Per tracciare il tuo pacco") != -1:
                                end = email_msg.find("Per tracciare il tuo pacco")
                            elif email_msg.find("View or manage order") != -1:
                                end = email_msg.find("View or manage order")

                            arrive_date = email_msg[start:end].replace(">", "").strip()
                            _LOGGER.debug("First pass: %s", arrive_date)
                            arrive_date = arrive_date.split(" ")
                            arrive_date = arrive_date[0:3]
                            # arrive_date[2] = arrive_date[2][:3]
                            arrive_date = " ".join(arrive_date).strip()
                            time_format = None
                            new_arrive_date = None

                            # Save and restore locale to avoid affecting other threads
                            saved_locale = locale.getlocale(locale.LC_TIME)
                            for lang in AMAZON_LANGS:
                                try:
                                    locale.setlocale(locale.LC_TIME, lang)
                                except Exception as err:
                                    _LOGGER.info("Locale error: %s (%s)", err, lang)
                                    continue

                                _LOGGER.debug("Arrive Date: %s", arrive_date)

                                if "today" in arrive_date or "tomorrow" in arrive_date:
                                    new_arrive_date = arrive_date.split(",")[1].strip()
                                    time_format = "%B %d"
                                elif arrive_date.endswith(","):
                                    new_arrive_date = arrive_date.rstrip(",")
                                    time_format = "%A, %B %d"
                                elif "," not in arrive_date:
                                    new_arrive_date = arrive_date
                                    time_format = "%A %d %B"
                                else:
                                    new_arrive_date = arrive_date
                                    time_format = "%A, %B %d"

                                try:
                                    dateobj = datetime.datetime.strptime(
                                        new_arrive_date, time_format
                                    )
                                except ValueError as err:
                                    _LOGGER.info(
                                        "International dates not supported. (%s)", err
                                    )
                                    continue

                                if (
                                    dateobj.day == datetime.date.today().day
                                    and dateobj.month == datetime.date.today().month
                                ):
                                    deliveries_today.append("Amazon Order")

                            # Restore original locale
                            try:
                                locale.setlocale(locale.LC_TIME, saved_locale)
                            except Exception:
                                pass

    value = None
    if param == "count":
        _LOGGER.debug("Amazon Count: %s", str(len(deliveries_today)))
        if len(deliveries_today) > len(order_number):
            value = len(order_number)
        else:
            value = len(deliveries_today)
    else:
        _LOGGER.debug("Amazon order: %s", str(order_number))
        value = order_number

    return value


# =============================================================================
# Advanced Tracking: Universal Email Scanner
# =============================================================================


def scan_all_emails_for_tracking(
    account: Type[imaplib.IMAP4_SSL],
    known_tracking: list,
) -> dict:
    """Scan all emails in folder for tracking numbers not found by carrier sensors.

    This searches ALL emails from today using known carrier tracking number
    regex patterns. It deduplicates against tracking numbers already found
    by the standard carrier-specific sensors.

    All processing is local. No data is sent externally.

    Returns dict with count, tracking list, and carrier mapping.
    """
    _LOGGER.debug("Starting universal email tracking scan")
    today = get_formatted_date()
    all_found = {}  # {tracking_number: carrier_name}

    # Search for ALL emails from today
    try:
        result = account.search(None, f"(SINCE {today})")
    except Exception as err:
        _LOGGER.error("Error searching all emails: %s", str(err))
        return {ATTR_COUNT: 0, ATTR_TRACKING: [], "carrier_map": {}}

    if result[0] != "OK" or result[1][0] is None:
        return {ATTR_COUNT: 0, ATTR_TRACKING: [], "carrier_map": {}}

    mail_ids = result[1][0].split()
    _LOGGER.debug("Universal scan: found %s emails to scan", len(mail_ids))

    # Compile all tracking patterns once
    compiled_patterns = {}
    for carrier, info in UNIVERSAL_TRACKING_PATTERNS.items():
        try:
            compiled_patterns[carrier] = {
                "regex": re.compile(info["pattern"]),
                "name": info["name"],
            }
        except re.error as err:
            _LOGGER.warning("Invalid pattern for %s: %s", carrier, err)

    for mail_id in mail_ids:
        try:
            data = email_fetch(account, mail_id, "(RFC822)")[1]
        except Exception as err:
            _LOGGER.debug("Error fetching email %s: %s", mail_id, err)
            continue

        for response_part in data:
            if not isinstance(response_part, tuple):
                continue

            try:
                msg = email.message_from_bytes(response_part[1])
            except Exception as err:
                _LOGGER.debug("Error parsing email: %s", err)
                continue

            # Collect text from subject and body
            text_parts = []
            subject = msg.get("subject", "")
            if subject:
                text_parts.append(subject)

            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type not in ["text/html", "text/plain"]:
                    continue
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        text_parts.append(payload.decode("utf-8", "ignore"))
                except Exception:
                    continue

            full_text = "\n".join(text_parts)

            # Apply each carrier pattern
            for carrier, pinfo in compiled_patterns.items():
                matches = pinfo["regex"].findall(full_text)
                for match in matches:
                    if match and match not in all_found:
                        all_found[match] = pinfo["name"]

    # Deduplicate: remove tracking numbers already found by carrier sensors
    known_set = set(known_tracking) if known_tracking else set()
    new_tracking = {
        num: carrier for num, carrier in all_found.items() if num not in known_set
    }

    tracking_list = list(new_tracking.keys())
    _LOGGER.debug(
        "Universal scan complete: %s new tracking numbers found (after dedup)",
        len(tracking_list),
    )

    return {
        ATTR_COUNT: len(tracking_list),
        ATTR_TRACKING: tracking_list,
        "carrier_map": new_tracking,
    }


# =============================================================================
# Advanced Tracking: Tracking Service Forwarding
# Supports: 17track (seventeentrack), AfterShip, AliExpress Package Tracker
# =============================================================================


async def forward_to_tracking_service(
    hass: Any,
    service_key: str,
    entry_id: str,
    tracking_numbers: list,
    carrier_map: dict,
    already_forwarded: set,
) -> list:
    """Forward new tracking numbers to a tracking service via HA service call.

    Supports multiple backends defined in TRACKING_SERVICES (const.py):
    - seventeentrack (17track) - core HA integration
    - aftership (AfterShip) - core HA integration, 490+ carriers
    - aliexpress_package_tracker - HACS integration

    Only forwards tracking numbers not previously sent. The user must have
    the chosen tracking integration already configured in Home Assistant.

    Returns list of newly forwarded tracking numbers.
    """
    service_def = TRACKING_SERVICES.get(service_key)
    if not service_def:
        _LOGGER.error("Unknown tracking service: %s", service_key)
        return []

    domain = service_def["domain"]
    service = service_def["service"]
    params_def = service_def["params"]
    service_name = service_def["name"]
    newly_forwarded = []

    for number in tracking_numbers:
        if number in already_forwarded:
            continue

        carrier_name = carrier_map.get(number, "Unknown")
        friendly_name = f"Mail & Packages: {carrier_name} - {number[:8]}..."

        # Build service call data based on the service's parameter schema
        service_data = {
            params_def["tracking_key"]: number,
        }
        if "name_key" in params_def:
            service_data[params_def["name_key"]] = friendly_name
        if "entry_id_key" in params_def and entry_id:
            service_data[params_def["entry_id_key"]] = entry_id

        try:
            await hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=True,
            )
            newly_forwarded.append(number)
            _LOGGER.info(
                "Forwarded tracking %s to %s", number, service_name
            )
        except Exception as err:
            _LOGGER.warning(
                "Failed to forward %s to %s: %s", number, service_name, err
            )

    return newly_forwarded


# =============================================================================
# Advanced Tracking: LLM Analysis (privacy-first, opt-in only)
# =============================================================================


async def analyze_email_with_llm(
    email_text: str,
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
) -> list:
    """Send email text to LLM to extract tracking numbers.

    PRIVACY WARNING: This function sends email content to an external service.
    It must ONLY be called when the user has explicitly opted in and is fully
    informed about data leaving their system.

    For 'ollama': sends to local instance (no internet required).
    For 'anthropic'/'openai': sends to cloud API (requires internet).

    Returns list of extracted tracking numbers.
    """
    prompt = (
        "Extract any package tracking numbers from this email. "
        "Return ONLY a JSON array of tracking numbers found. "
        "If no tracking numbers are found, return an empty array []. "
        "Do not include any other text, just the JSON array.\n\n"
        f"Email content:\n{email_text[:4000]}"
    )

    try:
        if provider == "ollama":
            return await _llm_ollama(endpoint, model, prompt)
        elif provider == "anthropic":
            return await _llm_anthropic(api_key, model, prompt)
        elif provider == "openai":
            return await _llm_openai(endpoint, api_key, model, prompt)
    except Exception as err:
        _LOGGER.error("LLM analysis error (%s): %s", provider, err)

    return []


def _validate_llm_endpoint(endpoint: str) -> bool:
    """Validate LLM endpoint URL to prevent SSRF attacks.

    Only allows http/https schemes and rejects obviously internal targets.
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(endpoint)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    # Block metadata endpoints and common internal services
    blocked_hosts = {
        "metadata.google.internal",
        "169.254.169.254",
        "metadata.azure.com",
    }
    hostname = parsed.hostname or ""
    if hostname in blocked_hosts:
        return False

    return True


async def _llm_ollama(endpoint: str, model: str, prompt: str) -> list:
    """Query local Ollama instance for tracking numbers.

    Ollama runs locally - no data leaves the user's network.
    """
    if not _validate_llm_endpoint(endpoint):
        _LOGGER.error("Invalid Ollama endpoint URL: %s", endpoint)
        return []
    url = f"{endpoint.rstrip('/')}/api/generate"
    payload = {
        "model": model or "llama3.2",
        "prompt": prompt,
        "stream": False,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("Ollama returned status %s", resp.status)
                return []
            result = await resp.json()
            response_text = result.get("response", "[]")
            return _parse_llm_tracking_response(response_text)


async def _llm_anthropic(api_key: str, model: str, prompt: str) -> list:
    """Query Anthropic API for tracking numbers.

    WARNING: Sends data to Anthropic's cloud API.
    """
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model or "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("Anthropic API returned status %s", resp.status)
                return []
            result = await resp.json()
            text = result.get("content", [{}])[0].get("text", "[]")
            return _parse_llm_tracking_response(text)


async def _llm_openai(
    endpoint: str, api_key: str, model: str, prompt: str
) -> list:
    """Query OpenAI-compatible API for tracking numbers.

    WARNING: Sends data to OpenAI's cloud API (or compatible endpoint).
    """
    if endpoint:
        if not _validate_llm_endpoint(endpoint):
            _LOGGER.error("Invalid OpenAI endpoint URL: %s", endpoint)
            return []
        url = f"{endpoint.rstrip('/')}/v1/chat/completions"
    else:
        url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                _LOGGER.error("OpenAI API returned status %s", resp.status)
                return []
            result = await resp.json()
            text = result["choices"][0]["message"]["content"]
            return _parse_llm_tracking_response(text)


def _parse_llm_tracking_response(text: str) -> list:
    """Parse LLM response to extract tracking number array.

    Returns list of tracking numbers.
    """
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, list):
                return [str(item) for item in result if item]
        except json.JSONDecodeError:
            pass

    _LOGGER.debug(
        "Could not parse LLM response as tracking numbers: %s", text[:200]
    )
    return []


async def llm_scan_emails(
    account: Type[imaplib.IMAP4_SSL],
    known_tracking: list,
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
) -> dict:
    """Scan emails with LLM for tracking numbers not found by regex.

    PRIVACY: Only called when user has explicitly opted in.
    Sends email content to the configured LLM provider.

    Returns dict with count and tracking numbers found.
    """
    _LOGGER.debug("Starting LLM email analysis (provider: %s)", provider)
    today = get_formatted_date()
    llm_found = []

    try:
        result = account.search(None, f"(SINCE {today})")
    except Exception as err:
        _LOGGER.error("Error searching emails for LLM analysis: %s", err)
        return {ATTR_COUNT: 0, ATTR_TRACKING: []}

    if result[0] != "OK" or result[1][0] is None:
        return {ATTR_COUNT: 0, ATTR_TRACKING: []}

    mail_ids = result[1][0].split()
    known_set = set(known_tracking) if known_tracking else set()

    for mail_id in mail_ids:
        try:
            data = email_fetch(account, mail_id, "(RFC822)")[1]
        except Exception:
            continue

        for response_part in data:
            if not isinstance(response_part, tuple):
                continue

            try:
                msg = email.message_from_bytes(response_part[1])
            except Exception:
                continue

            # Collect email text
            text_parts = []
            subject = msg.get("subject", "")
            if subject:
                text_parts.append(f"Subject: {subject}")

            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            text_parts.append(
                                payload.decode("utf-8", "ignore")
                            )
                    except Exception:
                        continue

            if not text_parts:
                continue

            email_text = "\n".join(text_parts)

            # Skip very short emails unlikely to contain tracking info
            if len(email_text) < 50:
                continue

            found = await analyze_email_with_llm(
                email_text, provider, endpoint, api_key, model
            )
            for num in found:
                if num not in known_set and num not in llm_found:
                    llm_found.append(num)

    _LOGGER.debug("LLM analysis found %s new tracking numbers", len(llm_found))
    return {ATTR_COUNT: len(llm_found), ATTR_TRACKING: llm_found}


# =============================================================================
# Advanced Tracking: Amazon Cookie Scraping
# =============================================================================


async def scrape_amazon_tracking(
    cookies_str: str,
    domain: str,
) -> dict:
    """Scrape Amazon order pages for tracking numbers using stored cookies.

    This uses undocumented Amazon web endpoints with the user's own
    session cookies. The user must provide their Amazon cookies and
    explicitly opt in to this feature.

    All data retrieved is processed locally.

    Returns dict with count and tracking info.
    """
    _LOGGER.debug("Starting Amazon cookie-based tracking scrape")
    tracking_info = []

    # Validate Amazon domain to prevent SSRF
    import re as _re

    if not _re.match(r"^amazon\.[a-z.]{2,10}$", domain):
        _LOGGER.error("Invalid Amazon domain: %s", domain)
        return {ATTR_COUNT: 0, ATTR_TRACKING: [], "orders": []}

    cookie_jar = _parse_cookies(cookies_str, domain)
    if not cookie_jar:
        _LOGGER.warning("No valid cookies provided for Amazon scraping")
        return {ATTR_COUNT: 0, ATTR_TRACKING: [], "orders": []}

    base_url = f"https://www.{domain}"
    orders_url = f"{base_url}/gp/your-account/order-history?orderFilter=last30"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        async with aiohttp.ClientSession(
            cookies=cookie_jar,
            headers=headers,
        ) as session:
            async with session.get(
                orders_url,
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Amazon order page returned status %s", resp.status
                    )
                    return {ATTR_COUNT: 0, ATTR_TRACKING: [], "orders": []}

                html = await resp.text()

            # Redirected to sign-in means cookies are expired
            if "ap/signin" in str(resp.url) or "sign-in" in html[:1000].lower():
                _LOGGER.warning(
                    "Amazon cookies appear expired - redirected to sign-in"
                )
                return {ATTR_COUNT: 0, ATTR_TRACKING: [], "orders": []}

            # Extract order IDs
            order_pattern = re.compile(r"(\d{3}-\d{7}-\d{7})")
            order_ids = list(set(order_pattern.findall(html)))
            _LOGGER.debug("Found %s Amazon order IDs", len(order_ids))

            for order_id in order_ids[:20]:
                tracking = await _get_amazon_order_tracking(
                    session, base_url, order_id
                )
                if tracking:
                    tracking_info.extend(tracking)

    except aiohttp.ClientError as err:
        _LOGGER.error("Network error during Amazon scraping: %s", err)
    except Exception as err:
        _LOGGER.error("Error during Amazon scraping: %s", err)

    _LOGGER.debug(
        "Amazon cookie scrape found %s tracking entries", len(tracking_info)
    )
    return {
        ATTR_COUNT: len(tracking_info),
        ATTR_TRACKING: [t["number"] for t in tracking_info],
        "orders": tracking_info,
    }


async def _get_amazon_order_tracking(
    session: aiohttp.ClientSession,
    base_url: str,
    order_id: str,
) -> list:
    """Get tracking info for a specific Amazon order.

    Returns list of dicts with tracking number and carrier.
    """
    tracking_url = f"{base_url}/gp/your-account/ship-track?orderId={order_id}"

    try:
        async with session.get(
            tracking_url,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True,
        ) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()
    except Exception as err:
        _LOGGER.debug(
            "Error fetching tracking for order %s: %s", order_id, err
        )
        return []

    results = []

    tracking_patterns = [
        re.compile(
            r"(?:tracking\s*(?:id|number|#)\s*[:\s]*)([\w\d]{8,30})",
            re.IGNORECASE,
        ),
        re.compile(r"(1Z[0-9A-Z]{16})"),  # UPS
        re.compile(r"(\b9[2345]\d{15,26}\b)"),  # USPS
        re.compile(r"(?:fedex|FedEx).*?(\d{12,20})"),  # FedEx
    ]

    carrier = "Unknown"
    carrier_patterns = [
        (
            re.compile(
                r"(?:shipped\s+with|carrier[:\s]+)([\w\s]+)", re.IGNORECASE
            ),
            1,
        ),
        (
            re.compile(
                r"(USPS|UPS|FedEx|DHL|AMZL|Amazon Logistics)", re.IGNORECASE
            ),
            1,
        ),
    ]

    for cp, group in carrier_patterns:
        match = cp.search(html)
        if match:
            carrier = match.group(group).strip()
            break

    for pattern in tracking_patterns:
        matches = pattern.findall(html)
        for match in matches:
            if match and len(match) >= 8:
                results.append(
                    {
                        "number": match,
                        "carrier": carrier,
                        "order_id": order_id,
                    }
                )

    return results


def _parse_cookies(cookies_str: str, domain: str) -> dict:
    """Parse cookie string into dict for aiohttp.

    Accepts cookies in 'key=value; key2=value2' format (from browser).

    Returns dict of cookies.
    """
    cookies = {}
    if not cookies_str:
        return cookies

    try:
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies[key.strip()] = value.strip()
    except Exception as err:
        _LOGGER.error("Error parsing Amazon cookies: %s", err)

    return cookies
