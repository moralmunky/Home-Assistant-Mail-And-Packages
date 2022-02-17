"""Helper functions for Mail and Packages."""

import datetime
import email
import hashlib
import imaplib
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
from homeassistant.util import dt as dt_util
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
    ATTR_AMAZON_IMAGE,
    ATTR_BODY,
    ATTR_CODE,
    ATTR_COUNT,
    ATTR_EMAIL,
    ATTR_IMAGE_NAME,
    ATTR_IMAGE_PATH,
    ATTR_ORDER,
    ATTR_PATTERN,
    ATTR_SUBJECT,
    ATTR_TRACKING,
    ATTR_USPS_MAIL,
    CONF_ALLOW_EXTERNAL,
    CONF_AMAZON_DAYS,
    CONF_AMAZON_FWDS,
    CONF_CUSTOM_IMG,
    CONF_CUSTOM_IMG_FILE,
    CONF_DURATION,
    CONF_FOLDER,
    CONF_GENERATE_MP4,
    CONF_PATH,
    DEFAULT_AMAZON_DAYS,
    OVERLAY,
    SENSOR_DATA,
    SENSOR_TYPES,
    SHIPPERS,
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


async def _check_ffmpeg() -> bool:
    """Check if ffmpeg is installed.

    Returns boolean
    """
    return which("ffmpeg")


async def _test_login(host: str, port: int, user: str, pwd: str) -> bool:
    """Test IMAP login to specified server.

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
        return True
    except Exception as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
        return False


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
        fetch(hass, config, account, data, sensor)

    # Copy image file to www directory if enabled
    if config.get(CONF_ALLOW_EXTERNAL):
        copy_images(hass, config)

    return data


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
    elif sensor == "mail_updated":
        count[sensor] = dt_util.parse_datetime(update_time())
    else:
        count[sensor] = get_count(
            account, sensor, False, img_out_path, hass, amazon_image_name
        )[ATTR_COUNT]

    data.update(count)
    _LOGGER.debug("Sensor: %s Count: %s", sensor, str(count[sensor]))
    return count[sensor]


def login(
    host: str, port: int, user: str, pwd: str
) -> Union[bool, Type[imaplib.IMAP4_SSL]]:
    """Login to IMAP server.

    Returns account object
    """
    # Catch invalid mail server / host names
    try:
        account = imaplib.IMAP4_SSL(host, port)

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


def update_time() -> str:
    """Get update time.

    Returns current timestamp as string
    """
    # updated = datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")
    updated = datetime.datetime.now(timezone.utc).isoformat(timespec="minutes")

    return updated


def build_search(address: list, date: str, subject: str = None) -> tuple:
    """Build IMAP search query.

    Return tuple of utf8 flag and search query.
    """
    the_date = f'SINCE "{date}"'
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
                email_fetch(account, num, "(RFC822)")[1][0][1].decode("utf-8")
            )

            # walking through the email parts to find images
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                _LOGGER.debug("Extracting image from email")

                # Log error message if we are unable to open the filepath for
                # some reason
                try:
                    with open(
                        image_output_path + part.get_filename(), "wb"
                    ) as the_file:
                        the_file.write(part.get_payload(decode=True))
                        images.append(image_output_path + part.get_filename())
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
        cleanup_images(os.path.split(mp4_file))
        _LOGGER.debug("Removing old mp4: %s", mp4_file)

    # TODO: find a way to call ffmpeg the right way from HA
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
        hass.add_job(download_img(img_url, image_path, image_name))


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
    domains = AMAZON_DOMAINS
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
