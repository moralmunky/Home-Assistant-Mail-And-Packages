"""Helper functions for Mail and Packages."""

from __future__ import annotations

import base64
import datetime
import email
import hashlib
import imaplib
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
import dateparser
import homeassistant.helpers.config_validation as cv
from bs4 import BeautifulSoup
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import ssl
from PIL import Image, ImageOps

from .const import (
    AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
    AMAZON_DELIVERED,
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_ORDER,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_HUB,
    AMAZON_HUB_BODY,
    AMAZON_HUB_CODE,
    AMAZON_HUB_EMAIL,
    AMAZON_HUB_SUBJECT,
    AMAZON_HUB_SUBJECT_SEARCH,
    AMAZON_IMG_PATTERN,
    AMAZON_ORDER,
    AMAZON_OTP,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    AMAZON_PACKAGES,
    AMAZON_PATTERN,
    AMAZON_SHIPMENT_TRACKING,
    AMAZON_TIME_PATTERN,
    AMAZON_TIME_PATTERN_END,
    AMAZON_TIME_PATTERN_REGEX,
    ATTR_AMAZON_IMAGE,
    ATTR_BODY,
    ATTR_BODY_COUNT,
    ATTR_CODE,
    ATTR_COUNT,
    ATTR_EMAIL,
    ATTR_GRID_IMAGE_NAME,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_PATTERN,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    ATTR_UPS_IMAGE,
    ATTR_USPS_MAIL,
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_GRID,
    CONF_GENERATE_MP4,
    CONF_IMAP_SECURITY,
    CONF_STORAGE,
    CONF_VERIFY_SSL,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    OVERLAY,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
)

NO_SSL = "Email will be accessed without encryption using this method and is not recommended."
_LOGGER = logging.getLogger(__name__)

# Config Flow Helpers


def get_resources() -> dict:
    """Resource selection schema.

    Returns dict of user selected sensors
    """
    known_available_resources = {
        sensor_id: sensor.name for sensor_id, sensor in SENSOR_TYPES.items()
    }

    # append binary sensors that have selectable set to true
    additional_resources = {"usps_mail_delivered": "USPS Mail Delivered"}

    known_available_resources.update(additional_resources)

    return dict(sorted(known_available_resources.items()))


async def _check_ffmpeg() -> bool:
    """Check if ffmpeg is installed.

    Returns boolean
    """
    return which("ffmpeg")


async def _test_login(
    host: str, port: int, user: str, pwd: str, security: str, verify: bool
) -> bool:
    """Test IMAP login to specified server.

    Returns success boolean
    """
    # Catch invalid mail server / host names
    try:
        ssl_context = (
            ssl.create_client_context()
            if verify
            else ssl.create_no_verify_ssl_context()
        )
        if security == "SSL":
            account = imaplib.IMAP4_SSL(host=host, port=port, ssl_context=ssl_context)
        elif security == "startTLS":
            account = imaplib.IMAP4(host=host, port=port)
            account.starttls(ssl_context)
        else:
            _LOGGER.warning(NO_SSL)
            account = imaplib.IMAP4(host=host, port=port)
    except Exception as err:
        _LOGGER.error("Error connecting into IMAP Server: %s", str(err))
        return False
    # Validate we can login to mail server
    try:
        account.login(user, pwd)
        return True
    except Exception as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
        return False


# Email Data helpers


def default_image_path(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config_entry: ConfigEntry,
) -> str:
    """Return value of the default image path.

    Returns the default path based on logic
    """
    storage = None
    try:
        storage = config_entry.get(CONF_STORAGE)
    except AttributeError:
        storage = config_entry.data[CONF_STORAGE]

    if storage:
        return storage
    return "custom_components/mail_and_packages/images/"


def process_emails(hass: HomeAssistant, config: ConfigEntry) -> dict:
    """Process emails and return value.

    Returns dict containing sensor data
    """
    _LOGGER.debug("Starting process_emails function")
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    user = config.get(CONF_USERNAME)
    pwd = config.get(CONF_PASSWORD)
    folder = config.get(CONF_FOLDER)
    resources = config.get(CONF_RESOURCES)
    imap_security = config.get(CONF_IMAP_SECURITY)
    verify_ssl = config.get(CONF_VERIFY_SSL)
    generate_grid = config.get(CONF_GENERATE_GRID)

    # Create the dict container
    data = {}

    # Login to email server and select the folder
    account = login(host, port, user, pwd, imap_security, verify_ssl)

    # Do not process if account returns false
    if not account:
        return data

    if not selectfolder(account, folder):
        # Bail out on error
        return data

    # Create image file name dict container
    _image = {}

    # USPS Mail Image name
    image_name = image_file_name(hass, config)
    _LOGGER.debug("Image name: %s", image_name)
    _image[ATTR_IMAGE_NAME] = image_name

    if generate_grid:
        png_file = image_name.replace(".gif", "_grid.png")
        _LOGGER.debug("Grid image name: %s", png_file)
        _image[ATTR_GRID_IMAGE_NAME] = png_file

    # Amazon delivery image name
    image_name = image_file_name(hass, config, True)
    _LOGGER.debug("Amazon Image Name: %s", image_name)
    _image[ATTR_AMAZON_IMAGE] = image_name

    # UPS delivery image name
    _LOGGER.debug("Generating UPS image name...")
    ups_image_name = image_file_name(hass, config, ups=True)
    _LOGGER.debug("UPS Image Name: %s", ups_image_name)
    _image[ATTR_UPS_IMAGE] = ups_image_name
    _LOGGER.debug("Set ATTR_UPS_IMAGE in coordinator data: %s", ups_image_name)

    # Ensure UPS directory exists and has a default image
    ups_path = f"{hass.config.path()}/{default_image_path(hass, config)}ups/"
    if not os.path.isdir(ups_path):
        try:
            os.makedirs(ups_path)
            _LOGGER.debug("Created UPS directory: %s", ups_path)
        except Exception as err:
            _LOGGER.error("Error creating UPS directory: %s", str(err))

    # Check if UPS image file exists
    ups_image_path = f"{ups_path}{ups_image_name}"
    if not os.path.exists(ups_image_path):
        _LOGGER.debug(
            "UPS image file does not exist, creating default: %s", ups_image_path
        )
        try:
            nomail = f"{os.path.dirname(__file__)}/no_deliveries_ups.jpg"
            copyfile(nomail, ups_image_path)
            _LOGGER.debug("Created default UPS image: %s", ups_image_path)
        except Exception as err:
            _LOGGER.error("Error creating default UPS image: %s", str(err))
    else:
        _LOGGER.debug("UPS image file exists: %s", ups_image_path)

    image_path = default_image_path(hass, config)
    _LOGGER.debug("Image path: %s", image_path)
    _image[ATTR_IMAGE_PATH] = image_path
    data.update(_image)

    # Only update sensors we're intrested in
    for sensor in resources:
        try:
            fetch(hass, config, account, data, sensor)
        except Exception as err:
            _LOGGER.error("Error updating sensor: %s reason: %s", sensor, err)

    # Copy image file to www directory if enabled
    if config.get(CONF_ALLOW_EXTERNAL):
        copy_images(hass, config)

    return data


def copy_images(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Copy images to www directory if enabled."""
    paths = []
    src = f"{hass.config.path()}/{default_image_path(hass, config)}"
    dst = f"{hass.config.path()}/www/mail_and_packages/"

    # Setup paths list
    paths.append(dst)
    paths.append(dst + "amazon/")
    paths.append(dst + "ups/")

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
    hass: HomeAssistant,
    config: ConfigEntry,
    amazon: bool = False,
    ups: bool = False,
) -> str:
    """Determine if filename is to be changed or not.

    Returns filename
    """
    _LOGGER.debug("image_file_name called - amazon: %s, ups: %s", amazon, ups)
    mail_none = None
    path = None
    image_name = None

    if amazon:
        if config.get(CONF_AMAZON_CUSTOM_IMG):
            mail_none = (
                config.get(CONF_AMAZON_CUSTOM_IMG_FILE)
                or DEFAULT_AMAZON_CUSTOM_IMG_FILE
            )
        else:
            mail_none = f"{os.path.dirname(__file__)}/no_deliveries_amazon.jpg"
        image_name = os.path.split(mail_none)[1]
        path = f"{hass.config.path()}/{default_image_path(hass, config)}amazon"
    elif ups:
        _LOGGER.debug("Processing UPS image file name")
        if config.get(CONF_UPS_CUSTOM_IMG):
            mail_none = (
                config.get(CONF_UPS_CUSTOM_IMG_FILE) or DEFAULT_UPS_CUSTOM_IMG_FILE
            )
            _LOGGER.debug("Using custom UPS image: %s", mail_none)
        else:
            mail_none = f"{os.path.dirname(__file__)}/no_deliveries_ups.jpg"
            _LOGGER.debug("Using default UPS image: %s", mail_none)
        image_name = os.path.split(mail_none)[1]
        path = f"{hass.config.path()}/{default_image_path(hass, config)}ups"
        _LOGGER.debug("UPS path: %s", path)
    else:
        path = f"{hass.config.path()}/{default_image_path(hass, config)}"
        if config.get(CONF_CUSTOM_IMG):
            mail_none = config.get(CONF_CUSTOM_IMG_FILE) or DEFAULT_CUSTOM_IMG_FILE
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
    ext = ".jpg" if amazon or ups else ".gif"

    for file in os.listdir(path):
        if file.endswith(".gif") or (file.endswith(".jpg") and (amazon or ups)):
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
    target_path = os.path.join(path, image_name)
    _LOGGER.debug("Copying %s to %s", mail_none, target_path)
    _LOGGER.debug("Source file exists: %s", os.path.exists(mail_none))
    _LOGGER.debug("Target directory exists: %s", os.path.exists(path))

    try:
        copyfile(mail_none, target_path)
        _LOGGER.debug("Successfully copied image to %s", target_path)
        _LOGGER.debug("Target file exists after copy: %s", os.path.exists(target_path))
    except Exception as err:
        _LOGGER.error("Error copying image: %s", str(err))
        # Return a fallback filename if copy fails
        return f"no_deliveries{ext}"

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
    if sensor in data:
        return data[sensor]

    img_out_path = f"{hass.config.path()}/{default_image_path(hass, config)}"
    gif_duration = config.get(CONF_DURATION)
    generate_mp4 = config.get(CONF_GENERATE_MP4)
    generate_grid = config.get(CONF_GENERATE_GRID)
    amazon_fwds = cv.ensure_list_csv(config.get(CONF_AMAZON_FWDS))
    image_name = data[ATTR_IMAGE_NAME]
    amazon_image_name = data[ATTR_AMAZON_IMAGE]
    amazon_days = config.get(CONF_AMAZON_DAYS)

    # Conditional variables
    nomail = (
        config.get(CONF_CUSTOM_IMG_FILE) if config.get(CONF_CUSTOM_IMG_FILE) else None
    )
    amazon_domain = (
        config.get(CONF_AMAZON_DOMAIN) if config.get(CONF_AMAZON_DOMAIN) else None
    )

    count = {}

    # Initialize shared variable ONCE
    data.setdefault("amazon_delivered_by_others", 0)

    if sensor == "usps_mail":
        count[sensor] = get_mails(
            account,
            img_out_path,
            gif_duration,
            image_name,
            generate_mp4,
            nomail,
            generate_grid,
        )
    elif sensor == AMAZON_PACKAGES:
        count[sensor] = get_items(
            account,
            ATTR_COUNT,
            amazon_fwds,
            amazon_days,
            amazon_domain,
        )
        count[AMAZON_ORDER] = get_items(
            account,
            ATTR_ORDER,
            amazon_fwds,
            amazon_days,
            amazon_domain,
        )
    elif sensor == AMAZON_HUB:
        value = amazon_hub(account, amazon_fwds)
        count[sensor] = value[ATTR_COUNT]
        count[AMAZON_HUB_CODE] = value[ATTR_CODE]
    elif sensor == AMAZON_EXCEPTION:
        info = amazon_exception(account, amazon_fwds, amazon_domain)
        count[sensor] = info[ATTR_COUNT]
        count[AMAZON_EXCEPTION_ORDER] = info[ATTR_ORDER]
    elif sensor == AMAZON_OTP:
        count[sensor] = amazon_otp(account, amazon_fwds)
    elif "_packages" in sensor:
        prefix = sensor.replace("_packages", "")
        delivering = fetch(hass, config, account, data, f"{prefix}_delivering")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        count[sensor] = delivering + delivered
    elif "_delivering" in sensor:
        prefix = sensor.replace("_delivering", "")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        info = get_count(
            account, sensor, True, amazon_domain=amazon_domain, data=data, config=config
        )
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
            # There is no delivering for amazon packages because they ship themselves
            # or use other shippers
            if shipper == "amazon":
                continue
            delivering = f"{shipper}_delivering"
            if delivering in data and delivering != sensor:
                total += fetch(hass, config, account, data, delivering)

        # We are going to best guess for in transit as amazon doesn't reveal who the
        # shipper is in email.
        if "amazon_packages" in data and "amazon_packages" != sensor:
            amazon_packages = max(
                0, fetch(hass, config, account, data, "amazon_packages")
            )

            # We know if we are expecting packages from amazon, and in tranit is lower
            # than the amazon package count, we can best guess amazon is delivering the
            # package. This will fail though if say there are 2 packages being delivered,
            # 1 from amazon and another from another shipper. This would report 1 less
            # in this example in transit.
            total = max(total, amazon_packages)

            # Now if a different shipper than amazon delivers the amazon package, the
            # amazon package count will still be counted as in transit when it was
            # delivered. However, some shippers state they delivered the package on
            # behalf of amazon. We use that to information to properly decrease in
            # transit. But not all shippers tell us.
            # Subtract Amazon packages we believe were delivered by other shippers
            total -= data.get("amazon_delivered_by_others", 0)

        count[sensor] = max(0, total)
    elif sensor == "mail_updated":
        count[sensor] = update_time()
    else:
        _LOGGER.debug("if statement sensor: %s", sensor)
        count[sensor] = get_count(
            account,
            sensor,
            False,
            img_out_path,
            hass,
            amazon_image_name,
            amazon_domain,
            amazon_fwds,
            data=data,
            config=config,
        )[ATTR_COUNT]

    data.update(count)
    _LOGGER.debug("Sensor: %s Count: %s", sensor, str(count[sensor]))
    return count[sensor]


def login(
    host: str, port: int, user: str, pwd: str, security: str, verify: bool = True
) -> Union[bool, Type[imaplib.IMAP4_SSL]]:
    """Login to IMAP server.

    Returns account object
    """
    try:
        ssl_context = (
            ssl.create_client_context()
            if verify
            else ssl.create_no_verify_ssl_context()
        )
        if security == "SSL":
            account = imaplib.IMAP4_SSL(host=host, port=port, ssl_context=ssl_context)
        elif security == "startTLS":
            account = imaplib.IMAP4(host=host, port=port)
            account.starttls(ssl_context)
        else:
            account = imaplib.IMAP4(host=host, port=port)

    except Exception as err:
        _LOGGER.error("Network error while connecting to server: %s", str(err))
        return False

    # If login fails give error message
    try:
        account.login(user, pwd)
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
        account.select(folder, readonly=True)
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
            if prefix_list is not None:
                imap_search = f'{prefix_list} FROM "{email_list}" {the_date} SUBJECT'
            else:
                imap_search = f'FROM "{email_list}" {the_date} SUBJECT'
            # imap_search = f"{the_date} SUBJECT"
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
    value = ("", [""])

    if utf8_flag:
        subject = subject.encode("utf-8")
        account.literal = subject
        try:
            value = account.search("utf-8", search)
        except Exception as err:
            _LOGGER.debug(
                "Error searching emails with unicode characters: %s", str(err)
            )
            value = "BAD", err.args[0]
    else:
        try:
            value = account.search(None, search)
        except Exception as err:
            _LOGGER.error("Error searching emails: %s", str(err))
            value = "BAD", err.args[0]

    _LOGGER.debug("email_search value: %s", value)

    (check, new_value) = value
    if new_value[0] is None:
        _LOGGER.debug("email_search value was invalid: None")
        value = (check, [b""])

    return value


def email_fetch(
    account: Type[imaplib.IMAP4_SSL], num: int, parts: str = "(RFC822)"
) -> tuple:
    """Download specified email for parsing.

    Returns tuple
    """
    # iCloud doesn't support RFC822 so override the 'message parts'
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

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
    gen_grid: bool = False,
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
            msg = email_fetch(account, num, "(RFC822)")[1]
            for response_part in msg:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    _LOGGER.debug("msg: %s", msg)

                    # walking through the email parts to find images
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            _LOGGER.debug("Found html email processing...")
                            part = part.get_payload(decode=True)
                            part = part.decode("utf-8", "ignore")
                            soup = BeautifulSoup(part, "html.parser")
                            found_images = soup.find_all(id="mailpiece-image-src-id")
                            if not found_images:
                                continue
                            if "data:image/jpeg;base64" not in part:
                                _LOGGER.debug("Unexpected html format found.")
                                continue
                            _LOGGER.debug("Found images: %s", bool(found_images))

                            # Convert all the images to binary data
                            for image in found_images:
                                filename = random_filename()
                                data = str(image["src"]).split(",")[1]
                                try:
                                    with open(
                                        image_output_path + filename, "wb"
                                    ) as the_file:
                                        the_file.write(base64.b64decode(data))
                                        images.append(image_output_path + filename)
                                        image_count = image_count + 1
                                except Exception as err:
                                    _LOGGER.critical(
                                        "Error opening filepath: %s", str(err)
                                    )
                                    return image_count

                        # Log error message if we are unable to open the filepath for
                        # some reason
                        elif part.get_content_type() == "image/jpeg":
                            _LOGGER.debug("Extracting image from email")
                            filename = part.get_filename()
                            junkmail = ["mailer", "content", "package"]
                            if any(junk in filename for junk in junkmail):
                                _LOGGER.debug("Discarding junk mail.")
                                continue
                            try:
                                with open(
                                    image_output_path + filename, "wb"
                                ) as the_file:
                                    the_file.write(part.get_payload(decode=True))
                                    images.append(image_output_path + filename)
                                    image_count = image_count + 1
                            except Exception as err:
                                _LOGGER.critical("Error opening filepath: %s", str(err))
                                return image_count

                        elif part.get_content_type() == "multipart":
                            continue

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
            img, *imgs = [Image.open(file) for file in all_images]

            try:
                _LOGGER.debug("Generating animated GIF")
                # Use Pillow to create mail images
                img.save(
                    fp=os.path.join(image_output_path, image_name),
                    format="GIF",
                    append_images=imgs,
                    save_all=True,
                    duration=gif_duration * 1000,
                    loop=0,
                )
                _LOGGER.debug("Mail image generated.")
            except Exception as err:
                _LOGGER.error("Error attempting to generate image: %s", str(err))
            for image in images_delete:
                cleanup_images(f"{os.path.split(image)[0]}/", os.path.split(image)[1])

        elif image_count == 0:
            _LOGGER.debug("No mail found.")
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
        if gen_grid:
            generate_grid_img(image_output_path, image_name, image_count)

    return image_count


def random_filename(ext: str = ".jpg") -> str:
    """Generate random filename."""
    return f"{str(uuid.uuid4())}{ext}"


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
        cleanup_images(os.path.split(mp4_file))
        _LOGGER.debug("Removing old mp4: %s", mp4_file)

    # TODO: find a way to call ffmpeg the right way from HA
    subprocess.call(
        [
            "ffmpeg",
            "-i",
            gif_image,
            "-pix_fmt",
            "yuv420p",
            mp4_file,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def generate_grid_img(path: str, image_file: str, count: int) -> None:
    """Generate png grid from gif.

    use a subprocess so we don't lock up the thread
    comamnd: ffmpeg -f gif -i infile.gif outfile.mp4
    """
    count = max(count, 1)
    if count % 2 == 0:
        length = int(count / 2)
    else:
        length = int(count / 2) + count % 2

    gif_image = os.path.join(path, image_file)
    png_file = os.path.join(path, image_file.replace(".gif", "_grid.png"))
    filecheck = os.path.isfile(png_file)
    _LOGGER.debug("Generating png image grid: %s", png_file)
    if filecheck:
        cleanup_images(os.path.split(png_file))
        _LOGGER.debug("Removing old png grid: %s", png_file)

    # TODO: find a way to call ffmpeg the right way from HA
    subprocess.call(
        [
            "ffmpeg",
            "-i",
            gif_image,
            "-r",
            "0.20",
            "-filter_complex",
            f"tile=2x{length}:padding=10:color=black",
            png_file,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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
                    img.thumbnail((width, height), resample=Image.Resampling.LANCZOS)

                    # Add padding as needed
                    img = ImageOps.pad(
                        img, (width, height), method=Image.Resampling.LANCZOS
                    )
                    # Crop to size
                    img = img.crop((0, 0, width, height))

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
    check = all(item in overlays for item in os.listdir(path))

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
    if isinstance(path, tuple):
        path = path[0]
        image = path[1]
    if image is not None:
        try:
            os.remove(path + image)
        except Exception as err:
            _LOGGER.error("Error attempting to remove image: %s", str(err))
        return

    for file in os.listdir(path):
        if (
            file.endswith(".gif")
            or file.endswith(".mp4")
            or file.endswith(".jpg")
            or file.endswith(".png")
        ):
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
    amazon_domain: Optional[str] = None,
    amazon_fwds: Optional[str] = None,
    data: Optional[dict] = None,
    config: Optional[ConfigEntry] = None,
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
        _LOGGER.debug("=== PROCESSING AMAZON DELIVERED SENSOR ===")
        result[ATTR_COUNT] = amazon_search(
            account,
            image_path,
            hass,
            amazon_image_name,
            amazon_domain,
            amazon_fwds,
            data,
        )
        result[ATTR_TRACKING] = ""
        return result

    # Return UPS delivered info
    if sensor_type == "ups_delivered":
        ups_image_name = (
            data.get(ATTR_UPS_IMAGE, "ups_delivery.jpg") if data else "ups_delivery.jpg"
        )
        result[ATTR_COUNT] = ups_search(
            account, image_path, hass, ups_image_name, config, data
        )

        # Extract tracking number if requested
        if get_tracking_num:
            # Search for UPS delivered emails to extract tracking numbers
            (server_response, email_data) = email_search(
                account,
                SENSOR_DATA["ups_delivered"][ATTR_EMAIL],
                today,
                SENSOR_DATA["ups_delivered"][ATTR_SUBJECT][0],
            )
            if server_response == "OK" and email_data[0] is not None:
                tracking = get_tracking(
                    email_data[0], account, SENSOR_DATA["ups_tracking"][ATTR_PATTERN][0]
                )
                result[ATTR_TRACKING] = tracking
            else:
                result[ATTR_TRACKING] = []
        else:
            result[ATTR_TRACKING] = ""
        return result

    # Bail out if unknown sensor type
    if ATTR_EMAIL not in SENSOR_DATA[sensor_type]:
        _LOGGER.debug("Unknown sensor type: %s", str(sensor_type))
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

        (server_response, email_data) = email_search(
            account, SENSOR_DATA[sensor_type][ATTR_EMAIL], today, subject
        )
        if server_response == "OK" and email_data[0] is not None:
            if ATTR_BODY in SENSOR_DATA[sensor_type].keys():
                body_count = SENSOR_DATA[sensor_type].get(ATTR_BODY_COUNT, False)
                _LOGGER.debug("Check body for mail count? %s", body_count)
                count += find_text(
                    email_data, account, SENSOR_DATA[sensor_type][ATTR_BODY], body_count
                )
            else:
                count += len(email_data[0].split())

            _LOGGER.debug(
                "Search for (%s) with subject (%s) results: %s count: %s",
                SENSOR_DATA[sensor_type][ATTR_EMAIL],
                subject,
                email_data[0],
                count,
            )
            found.append(email_data[0])

            # If sensor ends with "_delivered", check email content for "AMAZON". UPS,
            # USPS will say delivered for: "AMAZON" in their email. This is used to
            # fix in transit.
            if (
                sensor_type.endswith("_delivered")
                and sensor_type != AMAZON_DELIVERED
                and data is not None
            ):
                amazon_mentions = find_text(
                    email_data, account, AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT, False
                )
                if amazon_mentions > 0:
                    data["amazon_delivered_by_others"] = (
                        data.get("amazon_delivered_by_others", 0) + amazon_mentions
                    )
                    _LOGGER.debug(
                        "Sensor: %s — Found %s mention(s) of 'AMAZON' in delivered email.",
                        sensor_type,
                        amazon_mentions,
                    )

    if (
        f"{'_'.join(sensor_type.split('_')[:-1])}_tracking" in SENSOR_DATA
        and ATTR_PATTERN
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
    pattern = re.compile(rf"{the_format}")
    mail_list = sdata.split()
    _LOGGER.debug("Searching for tracking numbers in %s messages...", len(mail_list))

    for i in mail_list:
        data = email_fetch(account, i, "(RFC822)")[1]
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                _LOGGER.debug("Checking message subject...")

                # Search subject for a tracking number
                email_subject = msg["subject"]
                if email_subject:
                    email_subject = str(email_subject)
                    if (found := pattern.findall(email_subject)) and len(found) > 0:
                        _LOGGER.debug(
                            "Found tracking number in email subject: %s", found[0]
                        )
                        if found[0] not in tracking:
                            tracking.append(found[0])
                        continue

                # Search in email body for tracking number
                _LOGGER.debug("Checking message body using %s ...", the_format)

                # Special handling for UPS tracking - use simplified approach
                if the_format == "1Z?[0-9A-Z]{16}":
                    try:
                        # Get the raw email content
                        email_content = str(response_part[1], "utf-8", errors="ignore")

                        # Search for tracking number in the entire email content
                        if (found := pattern.findall(email_content)) and len(found) > 0:
                            _LOGGER.debug(
                                "Found tracking number in email: %s", found[0]
                            )
                            if found[0] not in tracking:
                                tracking.append(found[0])
                    except Exception as err:
                        _LOGGER.debug("Error processing email content: %s", str(err))
                else:
                    # Original logic for all other tracking types
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


def find_text(
    sdata: Any, account: Type[imaplib.IMAP4_SSL], search_terms: list, count: bool
) -> int:
    """Filter for specific words in email.

    Return count of items found as integer
    """
    _LOGGER.debug("Searching for (%s) in (%s) emails", search_terms, len(sdata))
    mail_list = sdata[0].split()
    count = 0
    found = None

    for i in mail_list:
        data = email_fetch(account, i, "(RFC822)")[1]
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                for part in msg.walk():
                    for search in search_terms:
                        _LOGGER.debug("Content type: %s", part.get_content_type())
                        if part.get_content_type() not in ["text/html", "text/plain"]:
                            continue
                        email_msg = part.get_payload(decode=True)
                        email_msg = email_msg.decode("utf-8", "ignore")
                        pattern = re.compile(rf"{search}")
                        if (
                            count
                            and (found := pattern.search(email_msg))
                            and len(found.groups()) > 0
                        ):
                            _LOGGER.debug(
                                "Found (%s) in email result: %s",
                                search,
                                str(found.groups()),
                            )
                            count = int(found.group(1))
                        elif (found := pattern.findall(email_msg)) and len(found) > 0:
                            _LOGGER.debug(
                                "Found (%s) in email %s times.", search, str(len(found))
                            )
                            count += len(found)

    _LOGGER.debug("Search for (%s) count results: %s", search_terms, count)
    return count


def ups_search(
    account: Type[imaplib.IMAP4_SSL],
    image_path: str,
    hass: HomeAssistant,
    ups_image_name: str,
    config: Optional[ConfigEntry] = None,
    coordinator_data: Optional[dict] = None,
) -> int:
    """Search for UPS delivery emails and extract delivery photos."""
    _LOGGER.debug("Searching for UPS delivery emails")
    _LOGGER.debug("UPS image name: %s", ups_image_name)

    today = get_formatted_date()
    count = 0
    new_image_saved = False

    # Search for UPS delivered emails
    (server_response, data) = email_search(
        account,
        SENSOR_DATA["ups_delivered"][ATTR_EMAIL],
        today,
        SENSOR_DATA["ups_delivered"][ATTR_SUBJECT][0],
    )

    _LOGGER.debug("UPS email search response: %s", server_response)
    _LOGGER.debug("UPS email search data: %s", data)

    if server_response != "OK" or data[0] is None or data[0] == b"":
        _LOGGER.debug("No UPS delivery emails found")
        # Still need to create no-delivery image and update coordinator data
        if count == 0:
            _LOGGER.debug("No UPS deliveries found.")
            # Generate a new filename for the no-delivery image
            if config:
                no_delivery_filename = image_file_name(hass, config, ups=True)
            else:
                no_delivery_filename = f"{str(uuid.uuid4())}.jpg"
            nomail = f"{os.path.dirname(__file__)}/no_deliveries_ups.jpg"
            try:
                copyfile(nomail, f"{image_path}ups/" + no_delivery_filename)
                # Update coordinator data with the no-delivery filename
                if coordinator_data is not None:
                    coordinator_data[ATTR_UPS_IMAGE] = no_delivery_filename
                    _LOGGER.debug(
                        "Updated coordinator data with no-delivery UPS image: %s",
                        no_delivery_filename,
                    )
            except Exception as err:
                _LOGGER.error("Error attempting to copy image: %s", str(err))
        return count

    # Check if the path exists, if not make it
    ups_path = f"{image_path}ups/"
    if not os.path.isdir(ups_path):
        try:
            os.makedirs(ups_path)
        except Exception as err:
            _LOGGER.critical("Error creating directory: %s", str(err))
            return count

    # Clean up image directory
    cleanup_images(ups_path)

    for num in data[0].split():
        _LOGGER.debug("Processing UPS email number: %s", num)
        msg = email_fetch(account, num, "(RFC822)")[1]
        for response_part in msg:
            if isinstance(response_part, tuple):
                sdata = response_part[1].decode("utf-8", "ignore")
                _LOGGER.debug("Calling get_ups_image for email %s", num)
                # Count the delivery email (regardless of photo extraction)
                count += 1
                # Check if a UPS delivery photo was successfully saved
                if get_ups_image(sdata, account, image_path, hass, ups_image_name):
                    new_image_saved = True

    # Note: No-delivery logic moved to early return case above

    # If a new image was saved, update the coordinator data with the actual filename
    if new_image_saved and coordinator_data is not None:
        # Find the actual file that was created
        for file in os.listdir(ups_path):
            if file.endswith(".jpg"):
                actual_filename = file
                _LOGGER.debug("Found actual UPS image file: %s", actual_filename)
                # Update the coordinator data with the actual filename
                coordinator_data[ATTR_UPS_IMAGE] = actual_filename
                _LOGGER.debug(
                    "Updated coordinator data with UPS image: %s", actual_filename
                )
                break

    _LOGGER.debug("UPS delivery photos extracted: %s", count)
    return count


def amazon_search(
    account: Type[imaplib.IMAP4_SSL],
    image_path: str,
    hass: HomeAssistant,
    amazon_image_name: str,
    amazon_domain: str,
    fwds: str = None,
    coordinator_data: Optional[dict] = None,
) -> int:
    """Find Amazon Delivered email.

    Returns email found count as integer
    """
    _LOGGER.debug("=== AMAZON DELIVERED SEARCH START ===")
    _LOGGER.debug("Searching for Amazon delivered email(s)...")

    subjects = AMAZON_DELIVERED_SUBJECT
    today = get_formatted_date()
    count = 0

    _LOGGER.debug("Today's date: %s", today)
    _LOGGER.debug("Amazon delivered subjects to search: %s", subjects)
    _LOGGER.debug("Cleaning up amazon images...")
    cleanup_images(f"{image_path}amazon/")

    address_list = amazon_email_addresses(fwds, amazon_domain)
    _LOGGER.debug("Amazon email list: %s", str(address_list))

    for subject in subjects:
        _LOGGER.debug("Searching for Amazon delivered emails with subject: %s", subject)
        (server_response, data) = email_search(account, address_list, today, subject)

        if server_response == "OK" and data[0] is not None:
            email_count = len(data[0].split())
            count += email_count
            _LOGGER.debug(
                "Amazon delivered email(s) found for subject '%s': %s",
                subject,
                email_count,
            )
            _LOGGER.debug("Email IDs found: %s", data[0])
            get_amazon_image(
                data[0],
                account,
                image_path,
                hass,
                amazon_image_name,
            )
        else:
            _LOGGER.debug("No Amazon delivered emails found for subject '%s'", subject)

    if count == 0:
        _LOGGER.debug("No Amazon deliveries found.")
        nomail = f"{os.path.dirname(__file__)}/no_deliveries_amazon.jpg"
        try:
            copyfile(nomail, f"{image_path}amazon/" + amazon_image_name)
            # Update coordinator data with the no-delivery filename
            if coordinator_data is not None:
                coordinator_data[ATTR_AMAZON_IMAGE] = amazon_image_name
                _LOGGER.debug(
                    "Updated coordinator data with no-delivery Amazon image: %s",
                    amazon_image_name,
                )
        except Exception as err:
            _LOGGER.error("Error attempting to copy image: %s", str(err))

    _LOGGER.debug("=== AMAZON DELIVERED SEARCH END ===")
    _LOGGER.debug("Final Amazon delivered count: %s", count)
    return count


def get_ups_image(  # pylint: disable=too-many-return-statements
    sdata: Any,
    account: Type[imaplib.IMAP4_SSL],  # pylint: disable=unused-argument
    image_path: str,
    hass: HomeAssistant,  # pylint: disable=unused-argument
    image_name: str,  # pylint: disable=unused-argument
) -> bool:
    """Extract UPS delivery photo from email.

    Returns True if a photo was successfully saved, False otherwise.
    """
    _LOGGER.debug("Attempting to extract UPS delivery photo")

    msg = email.message_from_string(sdata)

    ups_path = f"{image_path}ups/"

    # First pass: look for CID embedded images
    cid_images = {}
    for part in msg.walk():
        if part.get_content_type() == "image/jpeg":
            content_id = part.get("Content-ID")
            if content_id:
                # Remove < > from Content-ID
                cid = content_id.strip("<>")
                _LOGGER.debug("Found CID embedded image: %s", cid)
                cid_images[cid] = part.get_payload(decode=True)

    # Second pass: look for HTML content with CID references
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            _LOGGER.debug("Processing HTML content for UPS delivery photo")
            part_content = part.get_payload(decode=True)
            part_content = part_content.decode("utf-8", "ignore")

            # Look for delivery photo in HTML content
            if "deliveryPhoto" in part_content:
                _LOGGER.debug("Found delivery photo reference in HTML")

                # Check if we have the corresponding CID image
                if "deliveryPhoto" in cid_images:
                    _LOGGER.debug("Found matching CID image for deliveryPhoto")
                    try:
                        with open(ups_path + image_name, "wb") as the_file:
                            the_file.write(cid_images["deliveryPhoto"])
                        _LOGGER.debug(
                            "UPS delivery photo saved from CID: %s", image_name
                        )
                        return True
                    except Exception as err:
                        _LOGGER.error(
                            "Error saving UPS delivery photo from CID: %s", str(err)
                        )
                        return False

                # Fallback: look for base64 encoded images
                base64_pattern = r"data:image/jpeg;base64,([A-Za-z0-9+/=]+)"
                matches = re.findall(base64_pattern, part_content)

                if matches:
                    _LOGGER.debug("Found base64 encoded UPS delivery photo")
                    try:
                        with open(ups_path + image_name, "wb") as the_file:
                            the_file.write(base64.b64decode(matches[0]))
                        _LOGGER.debug(
                            "UPS delivery photo saved from base64: %s", image_name
                        )
                        return True
                    except Exception as err:
                        _LOGGER.error(
                            "Error saving UPS delivery photo from base64: %s", str(err)
                        )
                        return False

    # Third pass: look for regular JPEG attachments
    for part in msg.walk():
        if part.get_content_type() == "image/jpeg":
            filename = part.get_filename()
            if filename:
                _LOGGER.debug("Found UPS delivery photo attachment: %s", filename)
                try:
                    with open(ups_path + image_name, "wb") as the_file:
                        the_file.write(part.get_payload(decode=True))
                    _LOGGER.debug("UPS delivery photo saved: %s", image_name)
                    return True
                except Exception as err:
                    _LOGGER.error("Error saving UPS delivery photo: %s", str(err))
                    return False

    _LOGGER.debug("No UPS delivery photo found in email")
    return False


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
        _LOGGER.debug("Attempting to download Amazon image.")
        # Download the image we found
        hass.add_job(download_img(hass, img_url, image_path, image_name))


async def download_img(
    hass: HomeAssistant, img_url: str, img_path: str, img_name: str
) -> None:
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
                the_file = await hass.async_add_executor_job(open, filepath, "wb")
                the_file.write(data)
                _LOGGER.debug("Amazon image downloaded")


def _process_amazon_forwards(email_list: str | list | None) -> list:
    """Process amazon forward emails.

    Returns list of email addresses
    """
    result = []
    if email_list is not None:
        if not isinstance(email_list, list):
            email_list = email_list.split()
        for fwd in email_list:
            if fwd and fwd != '""' and fwd not in result:
                result.append(fwd)

    _LOGGER.debug("Processed forwards: %s", result)
    return result


def amazon_hub(account: Type[imaplib.IMAP4_SSL], fwds: Optional[str] = None) -> dict:
    """Find Amazon Hub info emails.

    Returns dict of sensor data
    """
    email_addresses = []
    email_addresses.extend(_process_amazon_forwards(fwds))
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
                        if msg.is_multipart():
                            email_msg = quopri.decodestring(str(msg.get_payload(0)))
                        else:
                            email_msg = quopri.decodestring(str(msg.get_payload()))
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


def amazon_otp(account: Type[imaplib.IMAP4_SSL], fwds: Optional[list] = None) -> dict:
    """Find Amazon exception emails.

    Returns dict of sensor data
    """
    tfmt = get_formatted_date()
    info = {}
    body_regex = AMAZON_OTP_REGEX
    email_addresses = []
    email_addresses.extend(_process_amazon_forwards(fwds))

    for address in email_addresses:
        (server_response, sdata) = email_search(
            account, address, tfmt, AMAZON_OTP_SUBJECT
        )

        if server_response == "OK":
            id_list = sdata[0].split()
            _LOGGER.debug("Found Amazon OTP email(s): %s", str(len(id_list)))
            found = []
            for i in id_list:
                data = email_fetch(account, i, "(RFC822)")[1]
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        _LOGGER.debug("Email Multipart: %s", str(msg.is_multipart()))
                        _LOGGER.debug("Content Type: %s", str(msg.get_content_type()))

                        # Get code from message body
                        try:
                            _LOGGER.debug("Decoding OTP email...")
                            email_msg = quopri.decodestring(
                                str(msg.get_payload(0))
                            )  # msg.get_payload(0).encode('utf-8')
                        except Exception as err:
                            _LOGGER.debug(
                                "Problem decoding email message: %s", str(err)
                            )
                            continue
                        email_msg = email_msg.decode("utf-8", "ignore")
                        pattern = re.compile(rf"{body_regex}")
                        search = pattern.search(email_msg)
                        if search is not None:
                            if len(search.groups()) > 1:
                                _LOGGER.debug(
                                    "Amazon OTP search results: %s", search.group(2)
                                )
                                found.append(search.group(2))

    info[ATTR_CODE] = found
    return info


def amazon_exception(
    account: Type[imaplib.IMAP4_SSL],
    fwds: Optional[list] = None,
    the_domain: str = None,
) -> dict:
    """Find Amazon exception emails.

    Returns dict of sensor data
    """
    order_number = []
    tfmt = get_formatted_date()
    count = 0
    info = {}

    address_list = amazon_email_addresses(fwds, the_domain)
    _LOGGER.debug("Amazon email list: %s", str(address_list))

    (server_response, sdata) = email_search(
        account, address_list, tfmt, AMAZON_EXCEPTION_SUBJECT
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


def amazon_date_search(email_msg: str) -> int:
    """Search for amazon date strings in email message."""
    for pattern in AMAZON_TIME_PATTERN_END:
        if (result := email_msg.find(pattern)) != -1:
            return result
    return -1


def amazon_date_regex(email_msg: str) -> str | None:
    """Look for regex strings in email message and return them."""
    for body_regex in AMAZON_TIME_PATTERN_REGEX:
        pattern = re.compile(rf"{body_regex}")
        search = pattern.search(email_msg)
        if search is not None and len(search.groups()) > 0:
            _LOGGER.debug(
                "Amazon Regex: %s Count: %s", body_regex, len(search.groups())
            )
            # return the first group match (first date from a date range)
            return search.group(1)
    return None


def amazon_date_format(arrive_date: str, lang: str) -> tuple:
    """Return the date format."""
    if "de_" in lang:
        return (arrive_date.split(",", 1)[1].strip(), "%d %B")

    if "today" in arrive_date or "tomorrow" in arrive_date:
        return (arrive_date.split(",")[1].strip(), "%B %d")

    if arrive_date.endswith(","):
        return (arrive_date.rstrip(","), "%A, %B %d")

    if "," not in arrive_date:
        return (arrive_date, "%A %d %B")

    return (arrive_date, "%A, %B %d")


def amazon_email_addresses(
    fwds: Optional[str] = None, the_domain: str = None
) -> list | None:
    """Return Amazon email addresses in list format."""
    domains = []
    domains.extend(_process_amazon_forwards(fwds))
    the_domain = the_domain.split()
    domains.extend(the_domain)
    value = []

    for domain in domains:
        if "@" in domain:
            email_address = domain.strip('"')
            value.append(email_address)
        else:
            email_address = []
            addresses = AMAZON_SHIPMENT_TRACKING
            for address in addresses:
                email_address.append(f"{address}@{domain}")
            value.extend(email_address)

    _LOGGER.debug("Amazon email search addresses: %s", str(value))
    return value


def get_items(
    account: Type[imaplib.IMAP4_SSL],
    param: str = None,
    fwds: Optional[str] = None,
    days: int = DEFAULT_AMAZON_DAYS,
    the_domain: str = None,
) -> Union[List[str], int]:
    """Parse Amazon emails for delivery date and order number.

    Returns list of order numbers or email count as integer
    """
    _LOGGER.debug("Attempting to find Amazon email with item list ...")

    # Limit to past X days
    past_date = datetime.date.today() - datetime.timedelta(days=days)
    tfmt = past_date.strftime("%d-%b-%Y")
    deliveries_today = []
    order_number = []
    amazon_delivered = []

    address_list = amazon_email_addresses(fwds, the_domain)
    _LOGGER.debug("Amazon email list: %s", str(address_list))

    (server_response, sdata) = email_search(account, address_list, tfmt)

    if server_response == "OK":
        mail_ids = sdata[0]
        id_list = mail_ids.split()
        _LOGGER.debug("Amazon emails found: %s", str(len(id_list)))
        for i in id_list:
            data = email_fetch(account, i, "(RFC822)")[1]
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Parse email date
                    email_date_str = msg.get("Date")
                    email_date = None
                    if email_date_str:
                        email_date = email.utils.parsedate_to_datetime(
                            email_date_str
                        ).date()
                    _LOGGER.debug("Email from date: %s", str(email_date))

                    today_date = datetime.date.today()

                    # Skip 'arriving' emails that are not from today
                    # if param and "arriving" in param.lower():
                    if param and param.lower() == "arriving":
                        if email_date != today_date:
                            _LOGGER.debug(
                                "Skipping 'arriving' email from %s, not today",
                                email_date,
                            )
                            continue

                    _LOGGER.debug("Email Multipart: %s", str(msg.is_multipart()))
                    _LOGGER.debug("Content Type: %s", str(msg.get_content_type()))

                    # Get and decode subject line
                    encoding = decode_header(msg["subject"])[0][1]
                    if encoding is not None:
                        email_subject = decode_header(msg["subject"])[0][0].decode(
                            encoding, "ignore"
                        )
                    else:
                        email_subject = decode_header(msg["subject"])[0][0]

                    if not isinstance(email_subject, str):
                        email_subject = email_subject.decode("utf-8", "ignore")

                    _LOGGER.debug("Amazon Subject: %s", str(email_subject))

                    # Skip ordered emails because the product hasn't shipped yet.
                    if any(
                        subj.lower() in email_subject.lower()
                        for subj in AMAZON_ORDERED_SUBJECT
                    ):
                        _LOGGER.debug("Ordered email found, skipping.")
                        continue  # Skip processing this email

                    # Order number pattern
                    pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

                    # Skip delivered emails and record order numbers
                    if any(
                        subj.lower() in email_subject.lower()
                        for subj in AMAZON_DELIVERED_SUBJECT
                    ):
                        delivered_orders = pattern.findall(email_subject)
                        if delivered_orders:
                            for o in delivered_orders:
                                if o not in amazon_delivered:
                                    amazon_delivered.append(o)
                                    _LOGGER.debug(
                                        "Delivered order found and stored: %s", o
                                    )
                        else:
                            _LOGGER.debug(
                                "Delivered email found, but no order number matched."
                            )
                        continue  # Skip processing this email

                    # Extract order number from subject
                    if (
                        (found := pattern.findall(email_subject))
                        and len(found) > 0
                        and found[0] not in order_number
                    ):
                        order_number.append(found[0])
                        _LOGGER.debug(
                            "Amazon order number found and appended: %s", str(found[0])
                        )

                    # Try decoding email body
                    try:
                        if msg.is_multipart():
                            email_msg = quopri.decodestring(str(msg.get_payload(0)))
                        else:
                            email_msg = quopri.decodestring(str(msg.get_payload()))
                    except Exception as err:
                        _LOGGER.debug("Problem decoding email message: %s", str(err))
                        _LOGGER.error("Unable to process this email. Skipping.")
                        continue

                    email_msg = email_msg.decode("utf-8", "ignore")

                    # Check message body for order number again
                    if (
                        (found := pattern.findall(email_msg))
                        and len(found) > 0
                        and found[0] not in order_number
                    ):
                        order_number.append(found[0])
                        _LOGGER.debug(
                            "Amazon order number found and appended again: %s",
                            str(found[0]),
                        )

                    # Check for arrival date
                    for search in AMAZON_TIME_PATTERN:
                        _LOGGER.debug("Looking for: %s", search)
                        if search not in email_msg:
                            continue

                        amazon_regex_result = amazon_date_regex(email_msg)
                        if amazon_regex_result is not None:
                            _LOGGER.debug("Found regex result: %s", amazon_regex_result)
                            arrive_date = amazon_regex_result
                        else:
                            start = email_msg.find(search) + len(search)
                            end = amazon_date_search(email_msg)
                            arrive_date = email_msg[start:end].replace(">", "").strip()
                            _LOGGER.debug("First pass: %s", arrive_date)
                            arrive_date = " ".join(arrive_date.split()[0:3])

                        # --- Arrival date logic ---
                        weekday_map = {
                            "monday": 0,
                            "tuesday": 1,
                            "wednesday": 2,
                            "thursday": 3,
                            "friday": 4,
                            "saturday": 5,
                            "sunday": 6,
                        }

                        arrive_date_clean = arrive_date.lower()
                        is_single_word = len(arrive_date_clean.split()) == 1

                        if is_single_word and arrive_date_clean in weekday_map:
                            email_weekday = email_date.weekday()
                            arrive_weekday = weekday_map[arrive_date_clean]
                            days_ahead = (arrive_weekday - email_weekday) % 7
                            arrive_date_obj = email_date + datetime.timedelta(
                                days=days_ahead
                            )

                            if arrive_date_obj < today_date:
                                _LOGGER.debug(
                                    "Skipping single-word arrive_date '%s' as arrival "
                                    "date %s is before today %s",
                                    arrive_date_clean,
                                    arrive_date_obj,
                                    today_date,
                                )
                                continue

                            parsed_date_only = arrive_date_obj
                        else:
                            dateobj = None
                            # Some tests don't have a date on the email
                            if email_date is None:
                                dateobj = dateparser.parse(arrive_date_clean)
                            else:
                                dateobj = dateparser.parse(
                                    arrive_date_clean,
                                    settings={
                                        "PREFER_DATES_FROM": "future",
                                        "RELATIVE_BASE": datetime.datetime.combine(
                                            email_date, datetime.time()
                                        ),
                                        "RETURN_AS_TIMEZONE_AWARE": False,
                                    },
                                )
                            if dateobj is None:
                                _LOGGER.debug(
                                    "Parsed date is None for arrive_date='%s'",
                                    arrive_date_clean,
                                )
                                continue
                            parsed_date_only = dateobj.date()

                        if parsed_date_only == today_date:
                            deliveries_today.append(
                                found[0] if found else "Amazon Order"
                            )
                        else:
                            _LOGGER.debug(
                                "Delivery date not today: %s", parsed_date_only
                            )

    # Remove delivered orders from deliveries_today
    deliveries_today = [
        item for item in deliveries_today if item not in amazon_delivered
    ]

    # Return delivery count or list of order numbers
    value = None
    if param == "count":
        _LOGGER.debug(
            "Amazon Delivery Count (today, not delivered): %s",
            str(len(deliveries_today)),
        )
        _LOGGER.debug("Amazon Order Count: %s", str(len(order_number)))
        value = min(len(deliveries_today), len(order_number))
    else:
        _LOGGER.debug("Amazon order: %s", str(order_number))
        value = order_number

    _LOGGER.debug("Amazon value: %s", str(value))
    return value
