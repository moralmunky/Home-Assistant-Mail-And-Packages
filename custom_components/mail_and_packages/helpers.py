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
import shutil
import subprocess  # nosec
import uuid
from email.header import decode_header
from pathlib import Path
from shutil import copyfile, copytree, which
from typing import Any

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
from voluptuous import Email, MultipleInvalid, Schema

from . import const
from .const import (
    AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
    AMAZON_DELIVERED,
    AMAZON_DELIVERED_SUBJECT,
    AMAZON_DOMAINS,
    AMAZON_EXCEPTION,
    AMAZON_EXCEPTION_ORDER,
    AMAZON_EXCEPTION_SUBJECT,
    AMAZON_HUB,
    AMAZON_HUB_BODY,
    AMAZON_HUB_CODE,
    AMAZON_HUB_EMAIL,
    AMAZON_HUB_SUBJECT,
    AMAZON_HUB_SUBJECT_SEARCH,
    AMAZON_IMG_LIST,
    AMAZON_IMG_PATTERN,
    AMAZON_ORDER,
    AMAZON_ORDERED_SUBJECT,
    AMAZON_OTP,
    AMAZON_OTP_REGEX,
    AMAZON_OTP_SUBJECT,
    AMAZON_PACKAGES,
    AMAZON_PATTERN,
    AMAZON_SHIPMENT_SUBJECT,
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
    ATTR_FEDEX_IMAGE,
    ATTR_GRID_IMAGE_NAME,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_PATTERN,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    ATTR_UPS_IMAGE,
    ATTR_USPS_MAIL,
    ATTR_WALMART_IMAGE,
    CAMERA_DATA,
    CAMERA_EXTRACTION_CONFIG,
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_CUSTOM_IMG,
    CONF_AMAZON_CUSTOM_IMG_FILE,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_DOMAIN,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FEDEX_CUSTOM_IMG,
    CONF_FEDEX_CUSTOM_IMG_FILE,
    CONF_FOLDER,
    CONF_FORWARDED_EMAILS,
    CONF_GENERATE_GRID,
    CONF_GENERATE_MP4,
    CONF_IMAP_SECURITY,
    CONF_STORAGE,
    CONF_UPS_CUSTOM_IMG,
    CONF_UPS_CUSTOM_IMG_FILE,
    CONF_VERIFY_SSL,
    CONF_WALMART_CUSTOM_IMG,
    CONF_WALMART_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_CUSTOM_IMG_FILE,
    DEFAULT_AMAZON_DAYS,
    DEFAULT_CUSTOM_IMG_FILE,
    DEFAULT_FEDEX_CUSTOM_IMG_FILE,
    DEFAULT_UPS_CUSTOM_IMG_FILE,
    DEFAULT_WALMART_CUSTOM_IMG_FILE,
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
    host: str, port: int, user: str, pwd: str, security: str, verify: bool = True
):
    """Test login to IMAP server."""
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
    except OSError as err:
        _LOGGER.error("Error connecting into IMAP Server: %s", err)
        return False

    try:
        account.login(user, pwd)
    except OSError as err:
        _LOGGER.error("Error logging into IMAP Server: %s", err)
        return False
    else:
        return True


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


def process_emails(hass: HomeAssistant, config: ConfigEntry) -> dict:  # noqa: C901
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

    # Consolidate Shipper Logic (UPS, Walmart, FedEx)
    base_image_path = f"{hass.config.path()}/{default_image_path(hass, config)}"
    shippers = [
        ("ups", ATTR_UPS_IMAGE, "no_deliveries_ups.jpg"),
        ("walmart", ATTR_WALMART_IMAGE, "no_deliveries_walmart.jpg"),
        ("fedex", ATTR_FEDEX_IMAGE, "no_deliveries_fedex.jpg"),
    ]

    for name, attr, default_img in shippers:
        _LOGGER.debug("Generating %s image name...", name.title())
        img_name = image_file_name(hass, config, **{name: True})
        _LOGGER.debug("%s Image Name: %s", name.title(), img_name)
        _image[attr] = img_name
        _LOGGER.debug("Set %s in coordinator data: %s", attr, img_name)

        # Handle Directory
        shipper_path = f"{base_image_path}{name}/"
        if not Path(shipper_path).is_dir():
            try:
                Path(shipper_path).mkdir(parents=True)
                _LOGGER.debug("Created %s directory: %s", name.title(), shipper_path)
            except OSError as err:
                _LOGGER.error("Error creating %s directory: %s", name.title(), err)

        # Handle Default Image
        full_img_path = f"{shipper_path}{img_name}"
        if not Path(full_img_path).exists():
            _LOGGER.debug(
                "%s image file does not exist, creating default: %s",
                name.title(),
                full_img_path,
            )
            try:
                src = str(Path(__file__).parent / default_img)
                copyfile(src, full_img_path)
                _LOGGER.debug(
                    "Created default %s image: %s", name.title(), full_img_path
                )
            except OSError as err:
                _LOGGER.error("Error creating default %s image: %s", name.title(), err)
        else:
            _LOGGER.debug("%s image file exists: %s", name.title(), full_img_path)

    image_path = default_image_path(hass, config)
    _LOGGER.debug("Image path: %s", image_path)
    _image[ATTR_IMAGE_PATH] = image_path
    data.update(_image)

    # Only update sensors we're intrested in
    for sensor in resources:
        try:
            fetch(hass, config, account, data, sensor)
        except (OSError, ValueError) as err:
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
    paths.append(dst + "walmart/")
    paths.append(dst + "fedex/")

    # Clean up the destination directory
    for path in paths:
        # Path check
        if not Path(path).exists():
            try:
                Path(path).mkdir(parents=True)
            except OSError as err:
                _LOGGER.error("Problem creating: %s, error returned: %s", path, err)
                return
        cleanup_images(path)

    try:
        copytree(src, dst, dirs_exist_ok=True)
    # Fixed BLE001: Catch specific shutil errors and OS errors
    except (OSError, shutil.Error) as err:
        _LOGGER.error(
            "Problem copying files from %s to %s error returned: %s", src, dst, err
        )
        return


def image_file_name(  # noqa: C901
    hass: HomeAssistant,
    config: ConfigEntry,
    amazon: bool = False,
    ups: bool = False,
    walmart: bool = False,
    fedex: bool = False,
) -> str:
    """Determine if filename is to be changed or not.

    Returns filename
    """
    _LOGGER.debug(
        "=== image_file_name CALLED === - amazon: %s, ups: %s, walmart: %s, fedex: %s",
        amazon,
        ups,
        walmart,
        fedex,
    )

    # Map flags to configuration keys and defaults
    # format: (flag, custom_img_key, custom_img_file_key, default_file_const, default_local_file)
    configs = [
        (
            amazon,
            CONF_AMAZON_CUSTOM_IMG,
            CONF_AMAZON_CUSTOM_IMG_FILE,
            DEFAULT_AMAZON_CUSTOM_IMG_FILE,
            "no_deliveries_amazon.jpg",
            "amazon",
        ),
        (
            ups,
            CONF_UPS_CUSTOM_IMG,
            CONF_UPS_CUSTOM_IMG_FILE,
            DEFAULT_UPS_CUSTOM_IMG_FILE,
            "no_deliveries_ups.jpg",
            "ups",
        ),
        (
            walmart,
            CONF_WALMART_CUSTOM_IMG,
            CONF_WALMART_CUSTOM_IMG_FILE,
            DEFAULT_WALMART_CUSTOM_IMG_FILE,
            "no_deliveries_walmart.jpg",
            "walmart",
        ),
        (
            fedex,
            CONF_FEDEX_CUSTOM_IMG,
            CONF_FEDEX_CUSTOM_IMG_FILE,
            DEFAULT_FEDEX_CUSTOM_IMG_FILE,
            "no_deliveries_fedex.jpg",
            "fedex",
        ),
    ]

    base_path = f"{hass.config.path()}/{default_image_path(hass, config)}"
    mail_none = None
    path = None
    is_specific_courier = False

    # Find which courier is active
    for (
        active,
        img_conf,
        file_conf,
        default_file_conf,
        local_default,
        sub_dir,
    ) in configs:
        if active:
            is_specific_courier = True
            _LOGGER.debug("Processing %s image file name", sub_dir.title())
            if config.get(img_conf):
                mail_none = config.get(file_conf) or default_file_conf
                _LOGGER.debug("Using custom %s image: %s", sub_dir.title(), mail_none)
            else:
                mail_none = str(Path(__file__).parent / local_default)
                _LOGGER.debug("Using default %s image: %s", sub_dir.title(), mail_none)

            path = f"{base_path}{sub_dir}"
            _LOGGER.debug("%s path: %s", sub_dir.title(), path)
            break

    # Handle standard mail case (if no specific courier flag was true)
    if not is_specific_courier:
        path = base_path.rstrip(
            "/"
        )  # remove trailing slash to be safe for os.path operations
        if config.get(CONF_CUSTOM_IMG):
            mail_none = config.get(CONF_CUSTOM_IMG_FILE) or DEFAULT_CUSTOM_IMG_FILE
        else:
            mail_none = str(Path(__file__).parent / "mail_none.gif")

    image_name = os.path.split(mail_none)[1]

    # Path check
    if not Path(path).exists():
        try:
            Path(path).mkdir(parents=True)
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
    ext = ".jpg" if amazon or ups or walmart or fedex else ".gif"

    for file_path in Path(path).iterdir():
        filename = file_path.name
        is_image_file = filename.endswith(".gif") or (
            filename.endswith(".jpg") and (amazon or ups or walmart or fedex)
        )
        if is_image_file:
            try:
                created = datetime.datetime.fromtimestamp(
                    file_path.stat().st_ctime
                ).strftime("%d-%b-%Y")
            except OSError as err:
                _LOGGER.error(
                    "Problem accessing file: %s, error returned: %s", filename, err
                )
                return image_name
            today = get_formatted_date()
            # If image isn't mail_none and not created today,
            # return a new filename
            if sha1 != hash_file(str(file_path)) and today != created:
                image_name = f"{uuid.uuid4()!s}{ext}"
            else:
                image_name = filename

    # If we find no images in the image directory generate a new filename
    if image_name in mail_none:
        image_name = f"{uuid.uuid4()!s}{ext}"
        _LOGGER.debug("=== image_file_name GENERATED NEW UUID: %s ===", image_name)
    else:
        _LOGGER.debug("=== image_file_name USING EXISTING: %s ===", image_name)
    _LOGGER.debug("Image Name: %s", image_name)

    # Insert place holder image
    target_path = Path(path) / image_name

    _LOGGER.debug("Copying %s to %s", mail_none, target_path)
    _LOGGER.debug("Source file exists: %s", Path(mail_none).exists())
    _LOGGER.debug("Target directory exists: %s", Path(path).exists())

    try:
        copyfile(mail_none, target_path)
        _LOGGER.debug("Successfully copied image to %s", target_path)
        _LOGGER.debug("Target file exists after copy: %s", target_path.exists())
    except OSError as err:
        _LOGGER.error("Error copying image: %s", err)
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
    with Path(filename).open("rb") as file:
        # loop till the end of the file
        chunk = 0
        while chunk != b"":
            # read only 1024 bytes at a time
            chunk = file.read(1024)
            the_hash.update(chunk)

    # return the hex representation of digest
    return the_hash.hexdigest()


def fetch(  # noqa: C901
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
    amazon_days = config.get(CONF_AMAZON_DAYS, DEFAULT_AMAZON_DAYS)

    # Combine the amazon forwarded emails with the configured forwarded emails (for now)
    forwarded_emails = amazon_fwds + cv.ensure_list_csv(
        config.get(CONF_FORWARDED_EMAILS)
    )

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
            forwarded_emails,
        )
    elif sensor == AMAZON_PACKAGES:
        count[sensor] = get_items(
            account,
            ATTR_COUNT,
            forwarded_emails,
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
        value = amazon_hub(
            account,
            forwarded_emails,
        )
        count[sensor] = value[ATTR_COUNT]
        count[AMAZON_HUB_CODE] = value[ATTR_CODE]
    elif sensor == AMAZON_EXCEPTION:
        info = amazon_exception(account, forwarded_emails, amazon_domain)
        count[sensor] = info[ATTR_COUNT]
        count[AMAZON_EXCEPTION_ORDER] = info[ATTR_ORDER]
    elif sensor == AMAZON_OTP:
        count[sensor] = amazon_otp(
            account,
            forwarded_emails,
        )
    elif "_packages" in sensor:
        prefix = sensor.replace("_packages", "")
        delivering = fetch(hass, config, account, data, f"{prefix}_delivering")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        count[sensor] = delivering + delivered
    elif "_delivering" in sensor:
        prefix = sensor.replace("_delivering", "")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        info = get_count(
            account,
            sensor,
            True,
            amazon_domain=amazon_domain,
            data=data,
            forwarded_emails=forwarded_emails,
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
        if "amazon_packages" in data and sensor != "amazon_packages":
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
            forwarded_emails,
            data=data,
        )[ATTR_COUNT]

    data.update(count)
    _LOGGER.debug("Sensor: %s Count: %s", sensor, count[sensor])
    return count[sensor]


def login(
    host: str, port: int, user: str, pwd: str, security: str, verify: bool = True
) -> bool | type[imaplib.IMAP4_SSL]:
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

    except OSError as err:
        _LOGGER.error("Network error while connecting to server: %s", err)
        return False

    # If login fails give error message
    try:
        account.login(user, pwd)
    except OSError as err:
        _LOGGER.error("Error logging into IMAP Server: %s", err)
        return False

    return account


def selectfolder(account: type[imaplib.IMAP4_SSL], folder: str) -> bool:
    """Select folder inside the mailbox."""
    try:
        account.list()
    except OSError as err:
        _LOGGER.error("Error listing folders: %s", err)
        return False
    try:
        account.select(folder, readonly=True)
    except OSError as err:
        _LOGGER.error("Error selecting folder: %s", err)
        return False
    return True


def get_today() -> datetime.date:
    """Get today's date using system local timezone (Home Assistant's timezone).

    Returns date object using the system's local timezone.
    """
    # For testing, set the date you wish here
    return datetime.date.today()
    # return datetime.date.today() - datetime.timedelta(days=1)


def get_formatted_date() -> str:
    """Return today in specific format.

    Returns current timestamp as string
    """
    return get_today().strftime("%d-%b-%Y")


def update_time() -> datetime.datetime:
    """Get update time.

    Returns current timestamp as datetime object.
    """
    return datetime.datetime.now(datetime.UTC)


def build_search(address: list, date: str, subject: str = "") -> tuple:
    """Build IMAP search query.

    Return tuple of utf8 flag and search query.
    """
    the_date = f"SINCE {date}"
    imap_search = None
    utf8_flag = False
    prefix_list = None
    email_list = None

    if len(address) == 1:
        email_list = address[0]
    else:
        email_list = '" FROM "'.join(address)
        prefix_list = " ".join(["OR"] * (len(address) - 1))

    _LOGGER.debug("DEBUG subject: %s", subject)

    if subject is not None:
        if not subject.isascii():
            utf8_flag = True
            if prefix_list is not None:
                imap_search = f'({prefix_list} FROM "{email_list}" {the_date})'
            else:
                imap_search = f'(FROM "{email_list}" {the_date})'
        elif prefix_list is not None:
            imap_search = (
                f'({prefix_list} FROM "{email_list}" SUBJECT "{subject}" {the_date})'
            )
        else:
            imap_search = f'(FROM "{email_list}" SUBJECT "{subject}" {the_date})'
    elif prefix_list is not None:
        imap_search = f'({prefix_list} FROM "{email_list}" {the_date})'
    else:
        imap_search = f'(FROM "{email_list}" {the_date})'

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    return (utf8_flag, imap_search)


def email_search(
    account: type[imaplib.IMAP4_SSL], address: list, date: str, subject: str = ""
) -> tuple:
    """Search emails with from, subject, senton date.

    Returns a tuple
    """
    utf8_flag, search = build_search(address, date, subject)
    value = ("", [""])

    if account.host == "imap.mail.yahoo.com" and utf8_flag:
        # Yahoo IMAP has issues with UTF8 searching, so bail out
        return "OK", [b""]

    if utf8_flag:
        subject = subject.encode("utf-8")
        account.literal = subject
        try:
            value = account.search("utf-8", search, "SUBJECT")
        except OSError as err:
            _LOGGER.debug("Error searching emails with unicode characters: %s", err)
            value = "BAD", err.args[0]
    else:
        try:
            value = account.search(None, search)
        except OSError as err:
            _LOGGER.error("Error searching emails: %s", err)
            value = "BAD", err.args[0]

    _LOGGER.debug("email_search value: %s", value)

    (check, new_value) = value
    # Handle case where account.search() returns a Mock (in tests)
    # Only convert to list when status is "OK" - "BAD" responses keep error as-is
    if check == "OK":
        # Ensure we always return a proper tuple with a list as the second element
        # for "OK" responses
        if not isinstance(new_value, list):
            _LOGGER.debug(
                "email_search: new_value is not a list (type: %s), converting to empty list",
                type(new_value).__name__,
            )
            new_value = [b""]
        elif len(new_value) == 0:
            # Empty list is valid, keep it as is
            pass
        elif new_value[0] is None:
            _LOGGER.debug("email_search value was invalid: None")
            new_value = [b""]
    # For "BAD" responses, keep the error message as-is (could be string or other type)

    return (check, new_value)


def email_fetch(
    account: type[imaplib.IMAP4_SSL], num, parts: str = "(RFC822)"
) -> tuple:
    """Download specified email for parsing.

    Args:
        account: IMAP account instance
        num: Email message ID (int, str, or bytes)
        parts: Message parts to fetch

    Returns tuple

    """
    # iCloud doesn't support RFC822 so override the 'message parts'
    if account.host == "imap.mail.me.com":
        parts = "BODY[]"

    # Convert num to string for imaplib
    if isinstance(num, bytes):
        num_str = num.decode()
    else:
        num_str = str(num)

    try:
        value = account.fetch(num_str, parts)
    except OSError as err:
        _LOGGER.error("Error fetching emails: %s", err)
        value = "BAD", err.args[0]

    return value


def get_mails(  # noqa: C901
    account: type[imaplib.IMAP4_SSL],
    image_output_path: str,
    gif_duration: int,
    image_name: str,
    gen_mp4: bool = False,
    custom_img: str = "",
    gen_grid: bool = False,
    forwarded_emails: list[str] = [],
) -> int:
    """Create GIF image based on the attachments in the inbox."""
    image_count = 0
    images = []
    images_delete = []
    msg = ""

    _LOGGER.debug("Attempting to find Informed Delivery mail")
    _LOGGER.debug("Informed delivery search date: %s", get_formatted_date())

    if forwarded_emails:
        email_addresses = forwarded_emails + SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL]
    else:
        email_addresses = SENSOR_DATA[ATTR_USPS_MAIL][ATTR_EMAIL]

    (server_response, data) = email_search(
        account,
        email_addresses,
        get_formatted_date(),
        SENSOR_DATA[ATTR_USPS_MAIL][ATTR_SUBJECT][0],
    )

    # Bail out on error
    if server_response != "OK" or data[0] is None:
        return image_count

    # Check to see if the path exists, if not make it
    if not Path(image_output_path).is_dir():
        try:
            Path(image_output_path).mkdir(parents=True, exist_ok=True)
        except OSError as err:
            _LOGGER.critical("Error creating directory: %s", err)

    # Clean up image directory
    _LOGGER.debug("Cleaning up image directory: %s", image_output_path)
    cleanup_images(image_output_path)

    # Copy overlays to image directory
    _LOGGER.debug("Checking for overlay files in: %s", image_output_path)
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
                                    target_path = Path(image_output_path) / filename
                                    with target_path.open("wb") as the_file:
                                        the_file.write(base64.b64decode(data))
                                        images.append(str(target_path))
                                        image_count = image_count + 1
                                except (OSError, ValueError) as err:
                                    _LOGGER.critical("Error opening filepath: %s", err)
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
                                target_path = Path(image_output_path) / filename
                                with target_path.open("wb") as the_file:
                                    the_file.write(part.get_payload(decode=True))
                                    images.append(str(target_path))
                                    image_count = image_count + 1
                            except OSError as err:
                                _LOGGER.critical("Error opening filepath: %s", err)
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
            images.append(str(Path(__file__).parent / "image-no-mailpieces700.jpg"))
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
        _LOGGER.debug("Image Count: %s", image_count)

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
                    fp=Path(image_output_path) / image_name,
                    format="GIF",
                    append_images=imgs,
                    save_all=True,
                    duration=gif_duration * 1000,
                    loop=0,
                )
                _LOGGER.debug("Mail image generated.")
            except (OSError, ValueError) as err:
                _LOGGER.error("Error attempting to generate image: %s", err)
            for image in images_delete:
                cleanup_images(f"{os.path.split(image)[0]}/", os.path.split(image)[1])

        elif image_count == 0:
            _LOGGER.debug("No mail found.")
            # Construct Path object
            target_file = Path(image_output_path) / image_name

            if target_file.is_file():
                _LOGGER.debug("Removing %s", target_file)
                cleanup_images(image_output_path, image_name)

            try:
                _LOGGER.debug("Copying nomail gif")
                if custom_img is not None:
                    nomail = custom_img
                else:
                    nomail = str(Path(__file__).parent / "mail_none.gif")

                copyfile(nomail, image_output_path + image_name)

            except OSError as err:
                _LOGGER.error("Error attempting to copy image: %s", err)

        if gen_mp4:
            _generate_mp4(image_output_path, image_name)
        if gen_grid:
            generate_grid_img(image_output_path, image_name, image_count)

    return image_count


def random_filename(ext: str = ".jpg") -> str:
    """Generate random filename."""
    return f"{uuid.uuid4()!s}{ext}"


def _generate_mp4(path: str, image_file: str) -> None:
    """Generate mp4 from gif.

    use a subprocess so we don't lock up the thread
    comamnd: ffmpeg -f gif -i infile.gif outfile.mp4
    """
    base_path = Path(path)
    gif_image = base_path / image_file
    mp4_file = base_path / image_file.replace(".gif", ".mp4")

    filecheck = mp4_file.is_file()

    _LOGGER.debug("Generating mp4: %s", mp4_file)
    if filecheck:
        # Construct path string with trailing slash to ensure cleanup_images concatenates correctly
        cleanup_images(str(mp4_file.parent) + "/", mp4_file.name)
        _LOGGER.debug("Removing old mp4: %s", mp4_file)

    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(gif_image),
            "-pix_fmt",
            "yuv420p",
            str(mp4_file),
        ]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
    except subprocess.CalledProcessError as err:
        _LOGGER.error("FFmpeg failed to generate MP4: %s", err)


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

    gif_image = Path(path + image_file)
    png_file = image_file.replace(".gif", "_grid.png")
    png_image = Path(path).joinpath(png_file)

    filecheck = png_image.is_file()

    _LOGGER.debug("Generating png image grid %s from %s", png_image, gif_image)
    if filecheck:
        # cleanup_images expects a tuple or string path, so we use string parts here
        # or we could update cleanup_images to handle Path objects natively later.
        cleanup_images(str(png_image.parent) + "/", png_image.name)
        _LOGGER.debug("Removing old png grid: %s", png_image)

    # TODO: find a way to call ffmpeg the right way from HA
    subprocess.call(
        [
            "ffmpeg",
            "-i",
            str(gif_image),
            "-r",
            "0.20",
            "-filter_complex",
            f"tile=2x{length}:padding=10:color=black",
            str(png_image),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def resize_images(images: list, width: int, height: int) -> list:
    """Resize images."""
    all_images = []
    for image_path in images:
        try:
            img_path = Path(image_path)
            with img_path.open("rb") as fd_img:
                img = Image.open(fd_img)
                img.thumbnail((width, height), resample=Image.Resampling.LANCZOS)
                img = ImageOps.pad(
                    img, (width, height), method=Image.Resampling.LANCZOS
                )
                img = img.crop((0, 0, width, height))
                new_image_path = img_path.with_suffix(".gif")
                img.save(new_image_path, img.format)
                all_images.append(str(new_image_path))

        except (OSError, ValueError) as err:
            _LOGGER.error("Error processing image %s: %s", image_path, err)
            continue

    return all_images


def copy_overlays(path: str) -> None:
    """Copy overlay images to image output path."""
    overlays = OVERLAY
    check = all(item.name in overlays for item in Path(path).iterdir())

    # Copy files if they are missing
    if not check:
        for file in overlays:
            _LOGGER.debug("Copying file to: %s", path + file)
            copyfile(
                Path(__file__).parent / file,
                path + file,
            )


def cleanup_images(path: str, image: str | None = None) -> None:  # noqa: C901
    """Clean up image storage directory.

    Only supose to delete .gif, .mp4, and .jpg files
    """
    _LOGGER.debug("=== cleanup_images CALLED === path: %s, image: %s", path, image)

    if isinstance(path, tuple):
        path = path[0]
        image = path[1]
    if image is not None:
        full_path = path + image
        _LOGGER.debug("cleanup_images - Removing specific file: %s", full_path)
        try:
            file_path_obj = Path(full_path)
            if file_path_obj.exists():
                file_path_obj.unlink()
                _LOGGER.debug("cleanup_images - Successfully removed: %s", full_path)
            else:
                _LOGGER.debug("cleanup_images - File does not exist: %s", full_path)
        except OSError as err:
            _LOGGER.error("Error attempting to remove image: %s", err)
        return

    # Only clean up if directory exists
    if not Path(path).is_dir():
        _LOGGER.debug("cleanup_images - Directory does not exist: %s", path)
        return

    try:
        files_before = [x.name for x in Path(path).iterdir()]
        _LOGGER.debug(
            "cleanup_images - Files in directory BEFORE cleanup: %s", files_before
        )
        for file in files_before:
            if file.endswith((".gif", ".mp4", ".jpg", ".png")):
                full_path = path + file
                _LOGGER.debug("cleanup_images - Removing file: %s", full_path)
                try:
                    file_path_obj = Path(full_path)
                    if file_path_obj.exists():
                        file_path_obj.unlink()
                        _LOGGER.debug(
                            "cleanup_images - Successfully removed: %s", full_path
                        )
                    else:
                        _LOGGER.debug(
                            "cleanup_images - File does not exist: %s", full_path
                        )
                except OSError as err:
                    _LOGGER.error("Error attempting to remove found image: %s", err)

        if Path(path).is_dir():
            files_after = [f.name for f in Path(path).iterdir()]
        else:
            files_after = []

        _LOGGER.debug(
            "cleanup_images - Files in directory AFTER cleanup: %s", files_after
        )
    except FileNotFoundError:
        # Directory was removed between check and listdir
        _LOGGER.debug("cleanup_images - Directory removed during cleanup: %s", path)
    except OSError as err:
        _LOGGER.error("Error listing directory for cleanup: %s", err)


def get_count(  # noqa: C901
    account: type[imaplib.IMAP4_SSL],
    sensor_type: str,
    get_tracking_num: bool = False,
    image_path: str | None = None,
    hass: HomeAssistant | None = None,
    amazon_image_name: str | None = None,
    amazon_domain: str | None = None,
    forwarded_emails: list[str] = [],
    data: dict | None = None,
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
    unique_email_ids = set()  # Track unique email IDs to avoid double counting

    # Return Amazon delivered info
    if sensor_type == AMAZON_DELIVERED:
        _LOGGER.debug("=== PROCESSING AMAZON DELIVERED SENSOR ===")
        result[ATTR_COUNT] = amazon_search(
            account,
            image_path,
            hass,
            amazon_image_name,
            amazon_domain,
            forwarded_emails,
            data,
        )
        result[ATTR_TRACKING] = ""
        return result

    # Bail out if unknown sensor type
    if ATTR_EMAIL not in SENSOR_DATA[sensor_type]:
        _LOGGER.debug("Unknown sensor type: %s", sensor_type)
        result[ATTR_COUNT] = count
        result[ATTR_TRACKING] = ""
        return result

    # Check if this is a generic delivery sensor with image extraction (UPS, Walmart, FedEx)
    # Derive shipper_name from sensor_type (e.g., "ups_delivered" -> "ups")
    shipper_name = None
    if sensor_type.endswith("_delivered"):
        potential_shipper = sensor_type.replace("_delivered", "")
        camera_key = f"{potential_shipper}_camera"
        # Check if this shipper has a camera in CAMERA_DATA
        # (excluding usps_camera and generic_camera)
        if camera_key in CAMERA_DATA and camera_key not in (
            "usps_camera",
            "generic_camera",
        ):
            shipper_name = potential_shipper

    # Setup image extraction if this is a generic delivery sensor
    image_attr = None
    image_name = None
    no_delivery_image_file = None
    extraction_config = {}
    new_image_saved = False
    if shipper_name:
        # Derive all values from shipper_name
        image_attr_name = f"ATTR_{shipper_name.upper()}_IMAGE"
        image_attr = getattr(const, image_attr_name, None)
        if image_attr is None:
            _LOGGER.error(
                "Could not find image attribute %s for %s",
                image_attr_name,
                shipper_name,
            )
            result[ATTR_COUNT] = count
            result[ATTR_TRACKING] = ""
            return result

        default_image_name = f"{shipper_name}_delivery.jpg"
        no_delivery_image_file = (
            f"{Path(__file__).parent}/no_deliveries_{shipper_name}.jpg"
        )

        # Get shipper-specific extraction config
        extraction_config = CAMERA_EXTRACTION_CONFIG.get(shipper_name, {})
        image_type = extraction_config.get("image_type", "jpeg")
        cid_name = extraction_config.get("cid_name")
        attachment_filename_pattern = extraction_config.get(
            "attachment_filename_pattern"
        )

        image_name = (
            data.get(image_attr, default_image_name) if data else default_image_name
        )
        _LOGGER.debug(
            (
                "%s - get_count: image_name from coordinator data: %s "
                "(image_attr: %s, data has key: %s)"
            ),
            shipper_name,
            image_name,
            image_attr,
            image_attr in data if data else False,
        )
        # Ensure image_path ends with / but avoid double slashes
        if image_path is None:
            _LOGGER.error(
                "get_count: image_path is None for sensor %s, cannot extract images",
                sensor_type,
            )
            result[ATTR_COUNT] = count
            result[ATTR_TRACKING] = ""
            return result
        normalized_image_path = image_path.rstrip("/") + "/"
        absolute_image_path = normalized_image_path
        absolute_shipper_path = f"{normalized_image_path}{shipper_name}/"
        _LOGGER.debug(
            "Setting Shipper paths to absolute_image_path:(%s) and absolute_shipper_path:(%s)",
            absolute_image_path,
            absolute_shipper_path,
        )

        # Create directory if needed (use absolute path)
        shipper_path_obj = Path(absolute_shipper_path)
        if not shipper_path_obj.is_dir():
            try:
                shipper_path_obj.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                _LOGGER.critical("Error creating directory: %s", err)
                result[ATTR_COUNT] = count
                result[ATTR_TRACKING] = ""
                return result

    # Cache sensor data to avoid repeated lookups
    sensor_data = SENSOR_DATA[sensor_type]
    subjects = sensor_data[ATTR_SUBJECT]
    sensor_email = sensor_data[ATTR_EMAIL]

    if forwarded_emails:
        email_addresses = forwarded_emails + sensor_email
    else:
        email_addresses = sensor_email

    is_delivered_sensor = sensor_type.endswith("_delivered")

    # Loop through all subjects (unified path for both generic delivery and normal sensors)
    for subject in subjects:
        _LOGGER.debug(
            "Attempting to find mail from (%s) with subject (%s)",
            email_addresses,
            subject,
        )

        (server_response, email_data) = email_search(
            account, email_addresses, today, subject
        )
        if (
            server_response == "OK"
            and email_data[0] is not None
            and email_data[0] != b""
        ):
            # Get email IDs for this subject search
            email_ids = email_data[0].split()
            # Track unique email IDs to avoid double counting when multiple subjects match
            new_email_ids = []
            for email_id in email_ids:
                email_id_str = (
                    email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                )
                if email_id_str not in unique_email_ids:
                    unique_email_ids.add(email_id_str)
                    new_email_ids.append(email_id)

            # Only count new emails (not already counted from previous subject matches)
            if new_email_ids:
                # Count emails using less intensive method (same for both paths)
                if ATTR_BODY in sensor_data:
                    body_count = sensor_data.get(ATTR_BODY_COUNT, False)
                    _LOGGER.debug("Check body for mail count? %s", body_count)
                    # Create a mock email_data with only new email IDs
                    new_email_data = (
                        b" ".join(
                            email_id.encode() if isinstance(email_id, str) else email_id
                            for email_id in new_email_ids
                        ),
                    )
                    count += find_text(
                        new_email_data,
                        account,
                        sensor_data[ATTR_BODY],
                        body_count,
                    )
                else:
                    count += len(new_email_ids)

            # If generic delivery sensor, extract images from emails
            if shipper_name:
                for email_id in new_email_ids:
                    msg = email_fetch(account, email_id, "(RFC822)")[1]
                    for response_part in msg:
                        if isinstance(response_part, tuple):
                            # Pass raw bytes to preserve binary attachments
                            email_bytes = response_part[1]
                            _LOGGER.debug(
                                "%s - Attempting image extraction for email %s, image_name: %s",
                                shipper_name,
                                email_id,
                                image_name,
                            )
                            # Get the image
                            extraction_result = _generic_delivery_image_extraction(
                                email_bytes,
                                absolute_image_path,  # Use absolute path for saving
                                image_name,
                                shipper_name,
                                image_type,
                                cid_name,
                                attachment_filename_pattern,
                            )
                            _LOGGER.debug(
                                "%s - Image extraction returned: %s",
                                shipper_name,
                                extraction_result,
                            )
                            expected_file_path = f"{absolute_shipper_path}{image_name}"
                            expected_path_obj = Path(expected_file_path)

                            # If we get a result and the file exists, then we can save the image
                            if extraction_result and expected_path_obj.exists():
                                file_size = expected_path_obj.stat().st_size
                                _LOGGER.debug(
                                    "%s - File verified on disk: %s (%d bytes)",
                                    shipper_name,
                                    expected_file_path,
                                    file_size,
                                )
                                new_image_saved = True
                                # Update coordinator data immediately with the exact image name
                                if data is not None:
                                    old_value = data.get(image_attr, "NOT SET")
                                    _LOGGER.debug(
                                        (
                                            "%s - UPDATING COORDINATOR: Setting %s ="
                                            "%s (was: %s) in coordinator data",
                                        ),
                                        shipper_name,
                                        image_attr,
                                        image_name,
                                        old_value,
                                    )
                                    data[image_attr] = image_name
                                    new_value = data.get(image_attr, "NOT SET")
                                    _LOGGER.debug(
                                        "%s - Coordinator data updated. %s is now: %s",
                                        shipper_name,
                                        image_attr,
                                        new_value,
                                    )
                                    # Log all image-related keys in coordinator
                                    image_keys = [
                                        k for k in data if "image" in k.lower()
                                    ]
                                    _LOGGER.debug(
                                        "%s - All image keys in coordinator: %s",
                                        shipper_name,
                                        {k: data.get(k, "NOT SET") for k in image_keys},
                                    )
                                else:
                                    _LOGGER.warning(
                                        "%s - Coordinator data dict is None, cannot update %s",
                                        shipper_name,
                                        image_attr,
                                    )
                                _LOGGER.debug(
                                    "%s - Image successfully saved and coordinator updated: %s",
                                    shipper_name,
                                    expected_file_path,
                                )
                            else:
                                _LOGGER.debug(
                                    (
                                        "%s - Image extraction returned False"
                                        "(no image found in email)"
                                    ),
                                    shipper_name,
                                )

            _LOGGER.debug(
                "Search for (%s) with subject (%s) results: %s count: %s",
                email_addresses,
                subject,
                email_data[0],
                count,
            )
            found.append(email_data[0])

            # If sensor ends with "_delivered", check email content for "AMAZON". UPS,
            # USPS will say delivered for: "AMAZON" in their email. This is used to
            # fix in transit.
            # Only check new emails to avoid double counting
            if (
                is_delivered_sensor
                and sensor_type != AMAZON_DELIVERED
                and data is not None
                and new_email_ids
            ):
                # Use original email_data for Amazon check (all emails, not just new ones)
                amazon_mentions = find_text(
                    email_data,
                    account,
                    AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT,
                    False,
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

    # Handle generic delivery sensor post-processing
    if shipper_name:
        # If no emails found AND no image was saved, set default image
        # Don't overwrite extracted delivery images with default image
        if count == 0 and not new_image_saved and no_delivery_image_file:
            # Clean up image directory before setting default (use absolute path)
            # Only clean up if directory exists
            if Path(absolute_shipper_path).is_dir():
                cleanup_images(absolute_shipper_path)

            try:
                # Ensure directory exists before copying (use absolute path)
                shipper_dir = Path(absolute_shipper_path)
                if not shipper_dir.is_dir():
                    shipper_dir.mkdir(parents=True, exist_ok=True)

                copyfile(no_delivery_image_file, absolute_shipper_path + image_name)
                if data is not None:
                    data[image_attr] = image_name
            except OSError as err:
                _LOGGER.error("Error attempting to copy image: %s", err)

    # Derive tracking sensor key (e.g., "ups_delivered" -> "ups_tracking")
    tracking_sensor_key = f"{'_'.join(sensor_type.split('_')[:-1])}_tracking"
    if (
        tracking_sensor_key in SENSOR_DATA
        and ATTR_PATTERN in SENSOR_DATA[tracking_sensor_key]
    ):
        track = SENSOR_DATA[tracking_sensor_key][ATTR_PATTERN][0]

    if track is not None and get_tracking_num and count > 0:
        for sdata in found:
            tracking.extend(get_tracking(sdata, account, track))
        tracking = list(dict.fromkeys(tracking))

    if len(tracking) > 0:
        # Use tracking numbers found for count (more accurate)
        count = len(tracking)

    result[ATTR_TRACKING] = tracking

    # Always ensure ATTR_COUNT is set before returning
    result[ATTR_COUNT] = count
    # Safety check: ensure result always has ATTR_COUNT
    if ATTR_COUNT not in result:
        _LOGGER.error(
            "get_count: ATTR_COUNT not set for sensor %s, defaulting to 0",
            sensor_type,
        )
        result[ATTR_COUNT] = 0
    return result


def get_tracking(  # noqa: C901
    sdata: Any, account: type[imaplib.IMAP4_SSL], the_format: str | None = None
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
                    except (TypeError, UnicodeError) as err:
                        _LOGGER.debug("Error processing email content: %s", err)
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


def _scan_email_for_text(
    account: type[imaplib.IMAP4_SSL],
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

    data = email_fetch(account, email_id, "(RFC822)")[1]
    for response_part in data:
        if not isinstance(response_part, tuple):
            continue

        msg = email.message_from_bytes(response_part[1])

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


def find_text(
    sdata: Any, account: type[imaplib.IMAP4_SSL], search_terms: list, body_count: bool
) -> int:
    """Filter for specific words in email."""
    _LOGGER.debug("Searching for (%s) in (%s) emails", search_terms, len(sdata))
    mail_list = sdata[0].split()
    count = 0

    # Pre-compile regex patterns once
    patterns = [re.compile(rf"{term}") for term in search_terms]

    for i in mail_list:
        matches, value = _scan_email_for_text(account, i, patterns, body_count)

        if body_count:
            # If extracting a value, "last found value wins" (updates count)
            if value is not None:
                count = value
        else:
            # If counting occurrences, accumulate
            count += matches

    return count


def _save_image_data_to_disk(shipper_name: str, path: str, image_data: bytes) -> bool:
    """Write image bytes to disk and verify."""
    try:
        # Ensure directory exists
        directory = Path(path).parent
        if not directory.is_dir():
            _LOGGER.debug("%s - Creating directory: %s", shipper_name, directory)
            directory.mkdir(parents=True, exist_ok=True)

        _LOGGER.debug(
            "%s - Writing %d bytes to file: %s", shipper_name, len(image_data), path
        )
        with Path(path).open("wb") as the_file:
            the_file.write(image_data)

    except OSError as err:
        _LOGGER.error(
            "Error saving %s delivery photo to %s: %s", shipper_name, path, err
        )
        return False
    else:
        if Path(path).exists():
            file_size = Path(path).stat().st_size
            _LOGGER.debug(
                "%s - SUCCESS: Image written to disk: %s (%d bytes)",
                shipper_name,
                path,
                file_size,
            )
            return True

        _LOGGER.error(
            "%s - ERROR: File write reported success but file doesn't exist: %s",
            shipper_name,
            path,
        )
        return False


def _generic_delivery_image_extraction(  # noqa: C901
    sdata: Any,
    image_path: str,
    image_name: str,
    shipper_name: str,
    image_type: str,
    cid_name: str | None = None,
    attachment_filename_pattern: str | None = None,
) -> bool:
    """Extract delivery photos from email.

    Args:
        sdata: Email content as bytes or string
        image_path: Base path for images
        image_name: Name for the image file
        shipper_name: Name of the shipper (e.g., "ups", "walmart", "fedex")
        image_type: Image MIME type ("jpeg" or "png")
        cid_name: Optional CID name to look for in HTML (e.g., "deliveryPhoto")
        attachment_filename_pattern: Optional pattern to match in attachment filenames

    Returns:
        True if image was saved, False otherwise

    """
    _LOGGER.debug("Attempting to extract %s delivery photo", shipper_name)
    _LOGGER.debug("%s - image_path parameter: %s", shipper_name, image_path)

    # Handle both bytes and string input
    if isinstance(sdata, bytes):
        msg = email.message_from_bytes(sdata)
    else:
        msg = email.message_from_string(sdata)
    # Normalize image_path to avoid double slashes (same as in get_count)
    normalized_image_path = image_path.rstrip("/") + "/"
    shipper_path = f"{normalized_image_path}{shipper_name}/"
    _LOGGER.debug("%s - Constructed shipper_path: %s", shipper_name, shipper_path)
    content_type = f"image/{image_type}"
    base64_pattern = rf"data:image/{image_type};base64,((?:[A-Za-z0-9+/]{{4}})*(?:[A-Za-z0-9+/]{{2}}==|[A-Za-z0-9+/]{{3}}=)?)"

    # First pass: look for CID embedded images (if CID name provided)
    cid_images = {}
    if cid_name:
        for part in msg.walk():
            if part.get_content_type() == content_type:
                content_id = part.get("Content-ID")
                if content_id:
                    cid = content_id.strip("<>")
                    cid_images[cid] = part.get_payload(decode=True)

    # Second pass: look for HTML content with CID references or base64
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            part_payload = part.get_payload(decode=True)
            if isinstance(part_payload, bytes):
                part_content = part_payload.decode("utf-8", "ignore")
            else:
                part_content = str(part_payload)

            # Check for CID reference
            if cid_name and cid_name in part_content:
                _LOGGER.debug(
                    "%s - Found CID reference '%s' in email content",
                    shipper_name,
                    cid_name,
                )
                if cid_name in cid_images:
                    _LOGGER.debug(
                        "%s - Found CID image data for '%s' (%d bytes)",
                        shipper_name,
                        cid_name,
                        len(cid_images[cid_name]) if cid_images[cid_name] else 0,
                    )
                    try:
                        full_path = shipper_path + image_name
                        image_data_bytes = cid_images[cid_name]
                        saved = _save_image_data_to_disk(
                            shipper_name, full_path, image_data_bytes
                        )
                    except (OSError, ValueError, TypeError) as err:
                        _LOGGER.error(
                            "Error saving %s delivery photo from CID: %s",
                            shipper_name,
                            err,
                        )
                        return False
                    else:
                        if saved:
                            return True
                        return False

            # Look for base64 encoded images
            matches = re.findall(base64_pattern, part_content)
            if matches:
                _LOGGER.debug(
                    "%s - Found %d base64 image(s) in email content",
                    shipper_name,
                    len(matches),
                )
                try:
                    base64_data = matches[0].replace(" ", "").replace("=3D", "=")
                    _LOGGER.debug(
                        "%s - Decoding base64 image data (%d chars)",
                        shipper_name,
                        len(base64_data),
                    )
                    full_path = shipper_path + image_name
                    image_data_bytes = base64.b64decode(base64_data)
                    saved = _save_image_data_to_disk(
                        shipper_name, full_path, image_data_bytes
                    )
                except (OSError, ValueError, TypeError) as err:
                    _LOGGER.error(
                        "Error saving %s delivery photo from base64: %s",
                        shipper_name,
                        err,
                    )
                    return False
                else:
                    if saved:
                        return True
                    return False

    # Third pass: look for attachments
    for part in msg.walk():
        if part.get_content_type() == content_type:
            filename = part.get_filename()
            if filename:
                _LOGGER.debug(
                    "%s - Found attachment: %s (content_type: %s)",
                    shipper_name,
                    filename,
                    part.get_content_type(),
                )
                # Check filename pattern if provided, otherwise accept any
                if attachment_filename_pattern:
                    if attachment_filename_pattern.lower() not in filename.lower():
                        _LOGGER.debug(
                            "%s - Attachment filename '%s' doesn't match pattern '%s', skipping",
                            shipper_name,
                            filename,
                            attachment_filename_pattern,
                        )
                        continue
                    _LOGGER.debug(
                        "%s - Attachment filename '%s' matches pattern '%s'",
                        shipper_name,
                        filename,
                        attachment_filename_pattern,
                    )
                try:
                    full_path = shipper_path + image_name
                    image_data_bytes = part.get_payload(decode=True)
                    saved = _save_image_data_to_disk(
                        shipper_name, full_path, image_data_bytes
                    )
                except (OSError, ValueError, TypeError) as err:
                    _LOGGER.error(
                        "Error saving %s delivery photo to %s: %s",
                        shipper_name,
                        shipper_path + image_name,
                        err,
                    )
                    return False
                else:
                    if saved:
                        return True
                    return False

    _LOGGER.debug("No %s delivery photo found in email", shipper_name)
    return False


def amazon_search(
    account: type[imaplib.IMAP4_SSL],
    image_path: str,
    hass: HomeAssistant,
    amazon_image_name: str,
    amazon_domain: str,
    fwds: str | None = None,
    coordinator_data: dict | None = None,
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
    _LOGGER.debug("Amazon email list: %s", address_list)

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
        nomail = f"{Path(__file__).parent}/no_deliveries_amazon.jpg"
        try:
            copyfile(nomail, f"{image_path}amazon/" + amazon_image_name)
            # Update coordinator data with the no-delivery filename
            if coordinator_data is not None:
                coordinator_data[ATTR_AMAZON_IMAGE] = amazon_image_name
                _LOGGER.debug(
                    "Updated coordinator data with no-delivery Amazon image: %s",
                    amazon_image_name,
                )
        except OSError as err:
            _LOGGER.error("Error attempting to copy image: %s", err)

    _LOGGER.debug("=== AMAZON DELIVERED SEARCH END ===")
    _LOGGER.debug("Final Amazon delivered count: %s", count)
    return count


def get_amazon_image(
    sdata: Any,
    account: type[imaplib.IMAP4_SSL],
    image_path: str,
    hass: HomeAssistant,
    image_name: str,
) -> None:
    """Find Amazon delivery image."""
    _LOGGER.debug("Searching for Amazon image in emails...")

    img_url = None
    mail_list = sdata.split()
    _LOGGER.debug("HTML Amazon emails found: %s", len(mail_list))
    pattern = re.compile(rf"{AMAZON_IMG_PATTERN}")

    for i in mail_list:
        data = email_fetch(account, i, "(RFC822)")[1]
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                _LOGGER.debug("Email Multipart: %s", msg.is_multipart())
                _LOGGER.debug("Content Type: %s", msg.get_content_type())

                for part in msg.walk():
                    if part.get_content_type() != "text/html":
                        continue
                    _LOGGER.debug("Processing HTML email...")
                    part = part.get_payload(decode=True)
                    part = part.decode("utf-8", "ignore")
                    found = pattern.findall(part)
                    for url in found:
                        if url[1] not in AMAZON_IMG_LIST:
                            continue
                        img_url = url[0] + url[1] + url[2]
                        _LOGGER.debug("Amazon img URL: %s", img_url)
                        break

    if img_url is not None:
        _LOGGER.debug("Attempting to download Amazon image.")
        hass.add_job(download_img(hass, img_url, image_path, image_name))
    else:
        # No S3 delivery image found in emails, use default image
        try:
            _LOGGER.debug("No Amazon delivery image found in emails, using default.")
            nomail = f"{Path(__file__).parent}/no_deliveries_amazon.jpg"
            copyfile(nomail, f"{image_path}amazon/{image_name}")
        except OSError as err:
            _LOGGER.error("Error attempting to copy default image: %s", err)


async def download_img(
    hass: HomeAssistant, img_url: str, img_path: str, img_name: str
) -> None:
    """Download image from url."""
    img_path = f"{img_path}amazon/"
    filepath = f"{img_path}{img_name}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(img_url.replace("&amp;", "&")) as resp:
                if resp.status != 200:
                    _LOGGER.error(
                        "Problem downloading file http error: %s", resp.status
                    )
                    return
                content_type = resp.headers["content-type"]
                _LOGGER.debug("URL content-type: %s", content_type)
                if "image" in content_type:
                    data = await resp.read()
                    _LOGGER.debug("Downloading image to: %s", filepath)
                    the_file = await hass.async_add_executor_job(open, filepath, "wb")
                    the_file.write(data)
                    _LOGGER.debug("Amazon image downloaded")
        except aiohttp.ClientError as err:
            _LOGGER.error("Problem downloading file connection error: %s", err)


def _process_amazon_forwards(email_list: str | list | None) -> list:
    """Process amazon forward emails.

    Returns list of email addresses that are actually Amazon domains.
    This filters out non-Amazon forwarded addresses to prevent false matches.
    """
    result = []
    if email_list is not None:
        if not isinstance(email_list, list):
            email_list = email_list.split()
        for fwd in email_list:
            if fwd and fwd != '""' and fwd not in result:
                # Only include forwarded addresses if they are actual Amazon domains
                if any(
                    amazon_domain in fwd.lower() for amazon_domain in AMAZON_DOMAINS
                ):
                    result.append(fwd)
                    _LOGGER.debug("Including Amazon forwarded address: %s", fwd)
                else:
                    _LOGGER.debug("Filtering out non-Amazon forwarded address: %s", fwd)

    _LOGGER.debug("Processed forwards: %s", result)
    return result


def _extract_hub_code(
    msg: email.message.Message, subject_regex: str, body_regex: str
) -> str | None:
    """Extract Amazon Hub code from email message."""
    # Check subject first
    email_subject = msg.get("subject", "")
    pattern = re.compile(rf"{subject_regex}")
    search = pattern.search(str(email_subject))
    if search and len(search.groups()) > 1:
        return search.group(3)

    # Check body if not found in subject
    try:
        if msg.is_multipart():
            payload = msg.get_payload(0)
        else:
            payload = msg.get_payload()

        # safely decode payload
        email_msg = quopri.decodestring(str(payload))
        email_msg = email_msg.decode("utf-8", "ignore")

        pattern = re.compile(rf"{body_regex}")
        search = pattern.search(email_msg)
        if search and len(search.groups()) > 1:
            return search.group(2)

    except (ValueError, TypeError, IndexError) as err:
        _LOGGER.debug("Problem decoding email message: %s", err)

    return None


def amazon_hub(account: type[imaplib.IMAP4_SSL], fwds: list[str] | None = None) -> dict:
    """Find Amazon Hub info emails."""
    email_addresses = []
    email_addresses.extend(_process_amazon_forwards(fwds))
    email_addresses.extend(AMAZON_HUB_EMAIL)

    body_regex = AMAZON_HUB_BODY
    subject_regex = AMAZON_HUB_SUBJECT_SEARCH
    info = {}
    today = get_formatted_date()
    found_codes = []
    processed_ids = set()

    _LOGGER.debug("[Hub] Amazon email list: %s", email_addresses)

    # Fix: Iterate through subjects (AMAZON_HUB_SUBJECT is a list)
    for subject in AMAZON_HUB_SUBJECT:
        (server_response, sdata) = email_search(
            account, email_addresses, today, subject=subject
        )

        if server_response != "OK" or sdata[0] is None:
            continue

        id_list = sdata[0].split()
        if not id_list:
            continue

        _LOGGER.debug("Amazon hub emails found: %s", len(id_list))

        for i in id_list:
            # Deduplicate emails by ID
            if i in processed_ids:
                continue
            processed_ids.add(i)

            data = email_fetch(account, i, "(RFC822)")[1]
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    code = _extract_hub_code(msg, subject_regex, body_regex)
                    if code:
                        found_codes.append(code)

    info[ATTR_COUNT] = len(found_codes)
    info[ATTR_CODE] = found_codes

    return info


def amazon_otp(account: type[imaplib.IMAP4_SSL], fwds: list | None = None) -> dict:
    """Find Amazon OTP code emails.

    Returns dict of sensor data
    """
    tfmt = get_formatted_date()
    info = {}
    found = []
    body_regex = AMAZON_OTP_REGEX
    email_addresses = []
    email_addresses.extend(_process_amazon_forwards(fwds))
    email_addresses.extend(AMAZON_HUB_EMAIL)

    (server_response, sdata) = email_search(
        account, email_addresses, tfmt, AMAZON_OTP_SUBJECT
    )

    if server_response == "OK":
        id_list = sdata[0].split()
        _LOGGER.debug("Found Amazon OTP email(s): %s", len(id_list))
        for i in id_list:
            data = email_fetch(account, i, "(RFC822)")[1]
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    _LOGGER.debug("Email Multipart: %s", msg.is_multipart())
                    _LOGGER.debug("Content Type: %s", msg.get_content_type())

                    # Get code from message body
                    try:
                        _LOGGER.debug("Decoding OTP email...")
                        # Safely handle both multipart and single-part emails
                        payload = (
                            msg.get_payload(0)
                            if msg.is_multipart()
                            else msg.get_payload()
                        )
                        # Check if payload is None before converting to string
                        if payload:
                            email_msg = quopri.decodestring(str(payload))
                            email_msg = email_msg.decode("utf-8", "ignore")

                            pattern = re.compile(rf"{body_regex}")
                            search = pattern.search(email_msg)
                            if search is not None:
                                if len(search.groups()) > 1:
                                    _LOGGER.debug(
                                        "Amazon OTP search results: %s", search.group(2)
                                    )
                                    found.append(search.group(2))
                        else:
                            _LOGGER.debug("Email payload was empty/None")

                    except (ValueError, TypeError, IndexError) as err:
                        _LOGGER.debug("Problem decoding email message: %s", err)
                        continue

    info[ATTR_CODE] = found
    return info


def amazon_exception(
    account: type[imaplib.IMAP4_SSL],
    fwds: list | None = None,
    the_domain: str | None = None,
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
        order_number.extend(order_numbers)

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


def amazon_email_addresses(
    fwds: str | None = None, the_domain: str | None = None
) -> list | None:
    """Return Amazon email addresses in list format."""
    domains = []
    domains.extend(_process_amazon_forwards(fwds))

    if the_domain:
        # Only split if the_domain is not None
        the_domain_list = the_domain.split()
        domains.extend(the_domain_list)

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

    _LOGGER.debug("Amazon email search addresses: %s", value)
    return value


def _search_amazon_emails(
    account: type[imaplib.IMAP4_SSL], address_list: list[str], days: int
) -> list[bytes]:
    """Search for Amazon emails and return a unique list of email IDs."""
    past_date = get_today() - datetime.timedelta(days=days)
    tfmt = past_date.strftime("%d-%b-%Y")
    amazon_subjects = (
        AMAZON_DELIVERED_SUBJECT + AMAZON_SHIPMENT_SUBJECT + AMAZON_ORDERED_SUBJECT
    )
    all_emails = []

    # Search for Amazon emails with relevant subjects
    for subject in amazon_subjects:
        _LOGGER.debug("Searching for Amazon emails with subject: %s", subject)
        (server_response, sdata) = email_search(account, address_list, tfmt, subject)
        if server_response == "OK" and sdata[0] is not None:
            email_ids = sdata[0].split()
            _LOGGER.debug("Found %s emails for subject '%s'", len(email_ids), subject)
            all_emails.extend(email_ids)

    # Remove duplicates while preserving order
    unique_emails = []
    for email_id in all_emails:
        if email_id not in unique_emails:
            unique_emails.append(email_id)

    return unique_emails


def _get_email_body(msg: email.message.Message) -> str:
    """Extract and decode the email body safely."""
    try:
        if msg.is_multipart():
            email_msg = quopri.decodestring(str(msg.get_payload(0)))
        else:
            email_msg = quopri.decodestring(str(msg.get_payload()))
        return email_msg.decode("utf-8", "ignore")
    except (ValueError, TypeError, IndexError) as err:
        _LOGGER.debug("Problem decoding email message: %s", err)
        return ""


def _extract_order_numbers(text: str, pattern: re.Pattern) -> list[str]:
    """Extract order numbers from text using a regex pattern."""
    return pattern.findall(text)


def _parse_amazon_arrival_date(
    email_msg: str, email_date: datetime.date
) -> datetime.date | None:
    """Determine the arrival date from the email body."""
    today_date = get_today()
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    for search in AMAZON_TIME_PATTERN:
        if search not in email_msg:
            continue

        amazon_regex_result = amazon_date_regex(email_msg)
        if amazon_regex_result is not None:
            arrive_date = amazon_regex_result
        else:
            start = email_msg.find(search) + len(search)
            end = amazon_date_search(email_msg)
            arrive_date = email_msg[start:end].replace(">", "").strip()
            arrive_date = " ".join(arrive_date.split()[0:3])

        arrive_date_clean = arrive_date.lower()
        is_single_word = len(arrive_date_clean.split()) == 1

        if is_single_word and arrive_date_clean in weekday_map:
            email_weekday = email_date.weekday()
            arrive_weekday = weekday_map[arrive_date_clean]
            days_ahead = (arrive_weekday - email_weekday) % 7
            arrive_date_obj = email_date + datetime.timedelta(days=days_ahead)

            if arrive_date_obj < today_date:
                continue

            return arrive_date_obj

        # Parse date string
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

        if dateobj is not None:
            if hasattr(dateobj, "date"):
                return dateobj.date()
            return dateobj

    return None


def get_items(  # noqa: C901
    account: type[imaplib.IMAP4_SSL],
    param: str | None = None,
    fwds: str | None = None,
    days: int = DEFAULT_AMAZON_DAYS,
    the_domain: str | None = None,
) -> list[str] | int:
    """Parse Amazon emails for delivery date and order number."""
    _LOGGER.debug("Attempting to find Amazon email with item list ...")
    today_date = get_today()

    # Track packages
    packages_arriving_today = {}  # {order_id: count}
    delivered_packages = {}  # {order_id: count}
    amazon_delivered = []  # List of delivered order IDs (for backward compat)
    deliveries_today = []  # Fallback for emails without order numbers
    all_shipped_orders = set()

    address_list = amazon_email_addresses(fwds, the_domain)
    unique_emails = _search_amazon_emails(account, address_list, days)
    _LOGGER.debug("Total unique Amazon emails found: %s", len(unique_emails))

    order_pattern = re.compile(r"[0-9]{3}-[0-9]{7}-[0-9]{7}")

    for email_id in unique_emails:
        # Convert bytes to string for fetch if necessary
        fetch_id = email_id.decode() if isinstance(email_id, bytes) else email_id
        data = email_fetch(account, fetch_id, "(RFC822)")[1]

        for response_part in data:
            if not isinstance(response_part, tuple):
                continue

            msg = email.message_from_bytes(response_part[1])

            # Parse Date
            email_date_str = msg.get("Date")
            email_date = None
            if email_date_str:
                parsed_date = dateparser.parse(email_date_str)
                if parsed_date:
                    email_date = parsed_date.date()

            # Param check: skip old "arriving" emails
            if param and param.lower() == "arriving" and email_date != today_date:
                continue

            # Parse Subject
            header_val = msg["subject"]
            encoding = decode_header(header_val)[0][1]
            subject_bytes = decode_header(header_val)[0][0]
            if encoding:
                email_subject = subject_bytes.decode(encoding, "ignore")
            elif isinstance(subject_bytes, bytes):
                email_subject = subject_bytes.decode("utf-8", "ignore")
            else:
                email_subject = str(subject_bytes)

            # Skip "Ordered" emails
            if any(s.lower() in email_subject.lower() for s in AMAZON_ORDERED_SUBJECT):
                continue

            email_msg = _get_email_body(msg)

            # --- Handle Delivered Emails ---
            if any(
                s.lower() in email_subject.lower() for s in AMAZON_DELIVERED_SUBJECT
            ):
                orders = _extract_order_numbers(email_subject, order_pattern)
                if not orders and email_msg:
                    orders = _extract_order_numbers(email_msg, order_pattern)

                for o in orders:
                    delivered_packages[o] = delivered_packages.get(o, 0) + 1
                    if o not in amazon_delivered:
                        amazon_delivered.append(o)
                continue

            # --- Handle Shipped/Arriving Emails ---
            order_id = None
            orders = _extract_order_numbers(email_subject, order_pattern)
            if orders:
                order_id = orders[0]
            elif email_msg:
                orders = _extract_order_numbers(email_msg, order_pattern)
                if orders:
                    order_id = orders[0]

            if order_id:
                all_shipped_orders.add(order_id)

            if email_msg:
                parsed_arrival = _parse_amazon_arrival_date(email_msg, email_date)

                if parsed_arrival == today_date:
                    if order_id:
                        packages_arriving_today[order_id] = (
                            packages_arriving_today.get(order_id, 0) + 1
                        )
                    else:
                        deliveries_today.append("Amazon Order")

    # Final Calculation
    deliveries_today = [
        item for item in deliveries_today if item not in amazon_delivered
    ]

    final_count = 0
    for order_id, arriving_count in packages_arriving_today.items():
        delivered_count = delivered_packages.get(order_id, 0)
        final_count += max(0, arriving_count - delivered_count)

    final_count += len(deliveries_today)

    if param == "count":
        return final_count

    return list(all_shipped_orders)


def generate_delivery_gif(delivery_images: list, gif_path: str) -> bool:
    """Generate an animated GIF from delivery images.

    Args:
        delivery_images: List of image file paths
        gif_path: Path where the GIF should be saved

    Returns:
        bool: True if GIF was created successfully, False otherwise

    """
    try:
        # Open all images
        corrected_images = []
        for img_path in delivery_images:
            img = Image.open(img_path)
            img = ImageOps.exif_transpose(img)  # auto-rotates according to EXIF
            corrected_images.append(img)

        # Create animated GIF (3 seconds per image)
        corrected_images[0].save(
            gif_path,
            format="GIF",
            append_images=corrected_images[1:],
            save_all=True,
            duration=3000,  # 3 seconds per image
            loop=0,  # Infinite loop
        )

        _LOGGER.debug(
            "Generated animated GIF with %d delivery images at %s",
            len(delivery_images),
            gif_path,
        )

    except (OSError, ValueError, Image.UnidentifiedImageError) as e:
        _LOGGER.error("Error creating animated GIF: %s", e)
        return False
    else:
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
