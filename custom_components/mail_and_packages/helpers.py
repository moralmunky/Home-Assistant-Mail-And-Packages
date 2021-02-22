""" Helper functions for Mail and Packages """

import datetime
import email
import hashlib
import imaplib
import logging
import os
import quopri
import re
import subprocess
import uuid
from email.header import decode_header
from shutil import copyfile, which
from typing import Any, List, Optional, Union

import aiohttp
import imageio as io
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
)
from PIL import Image
from resizeimage import resizeimage

from . import const

_LOGGER = logging.getLogger(__name__)

# Config Flow Helpers


def get_resources() -> dict:
    """Resource selection schema."""

    known_available_resources = {
        sensor_id: sensor[const.SENSOR_NAME]
        for sensor_id, sensor in const.SENSOR_TYPES.items()
    }

    return known_available_resources


async def _check_ffmpeg() -> bool:
    """ check if ffmpeg is installed """
    if which("ffmpeg") is not None:
        return True
    else:
        return False


async def _test_login(host, port, user, pwd) -> bool:
    """function used to login"""
    # Attempt to catch invalid mail server hosts
    try:
        account = imaplib.IMAP4_SSL(host, port)
    except Exception as err:
        _LOGGER.error("Error connecting into IMAP Server: %s", str(err))
        return False
    # Validate we can login to mail server
    try:
        rv, data = account.login(user, pwd)
        return True
    except Exception as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
        return False


# Email Data helpers


def default_image_path(hass: Any, config_entry: Any) -> str:
    """ Return value of the default image path """

    updated_config = config_entry.data.copy()

    # Set default image path (internal use)
    if const.CONF_PATH not in config_entry.data.keys():
        return "images/mail_and_packages/"

    # Set default image path (external use if enabled)
    elif const.CONF_ALLOW_EXTERNAL in config_entry.data.keys():
        if updated_config[const.CONF_ALLOW_EXTERNAL]:
            return "www/mail_and_packages/"

    # Return the default
    return "images/mail_and_packages/"


def process_emails(hass: Any, config: Any) -> dict:
    """ Process emails and return value """
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    user = config.get(CONF_USERNAME)
    pwd = config.get(CONF_PASSWORD)
    folder = config.get(const.CONF_FOLDER)
    resources = config.get(CONF_RESOURCES)

    # Login to email server and select the folder
    account = login(host, port, user, pwd)

    # Do not process if account returns false
    if not account:
        return

    selectfolder(account, folder)

    # Create the dict container
    data = {}

    # Create image file name dict container
    _image = {}
    image_name = image_file_name(hass, config)
    _LOGGER.debug("Image name: %s", image_name)
    _image[const.ATTR_IMAGE_NAME] = image_name

    image_path = config.get(const.CONF_PATH)
    # image_path = default_image_path(hass, config)
    _LOGGER.debug("Image path: %s", image_path)
    _image[const.ATTR_IMAGE_PATH] = image_path
    data.update(_image)

    # Only update sensors we're intrested in
    for sensor in resources:
        fetch(hass, config, account, data, sensor)

    return data


def image_file_name(hass: Any, config: Any) -> str:
    """Determine if filename is to be changed or not.

    Returns filename
    """
    image_name = None
    path = f"{hass.config.path()}/{config.get(const.CONF_PATH)}"
    mail_none = f"{os.path.dirname(__file__)}/mail_none.gif"

    # Path check
    path_check = os.path.exists(path)
    if not path_check:
        try:
            os.makedirs(path)
        except OSError as err:
            _LOGGER.error("Problem creating: %s, error returned: %s", path, err)
            return "mail_none.gif"

    # SHA1 file hash check
    try:
        sha1 = hash_file(mail_none)
    except OSError as err:
        _LOGGER.error("Problem accessing file: %s, error returned: %s", mail_none, err)
        return "mail_none.gif"

    for file in os.listdir(path):
        if file.endswith(".gif"):
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
                image_name = f"{str(uuid.uuid4())}.gif"
            else:
                image_name = file

    # Handle no gif file found
    if image_name is None:
        image_name = f"{str(uuid.uuid4())}.gif"

    return image_name


def hash_file(filename: str) -> str:
    """ "This function returns the SHA-1 hash
    of the file passed into it"""

    # make a hash object
    h = hashlib.sha1()

    # open file for reading in binary mode
    with open(filename, "rb") as file:

        # loop till the end of the file
        chunk = 0
        while chunk != b"":
            # read only 1024 bytes at a time
            chunk = file.read(1024)
            h.update(chunk)

    # return the hex representation of digest
    return h.hexdigest()


def fetch(hass: Any, config: Any, account: Any, data: dict, sensor: str):
    """Fetch data for a single sensor, including any sensors it depends on."""

    img_out_path = f"{hass.config.path()}/{config.get(const.CONF_PATH)}"
    gif_duration = config.get(const.CONF_DURATION)
    generate_mp4 = config.get(const.CONF_GENERATE_MP4)
    amazon_fwds = config.get(const.CONF_AMAZON_FWDS)
    image_name = data[const.ATTR_IMAGE_NAME]

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
        )
    elif sensor == const.AMAZON_PACKAGES:
        count[sensor] = get_items(account, const.ATTR_COUNT, amazon_fwds)
        count[const.AMAZON_ORDER] = get_items(account, const.ATTR_ORDER)
    elif sensor == const.AMAZON_HUB:
        value = amazon_hub(account, amazon_fwds)
        count[sensor] = value[const.ATTR_COUNT]
        count[const.AMAZON_HUB_CODE] = value[const.ATTR_CODE]
    elif "_packages" in sensor:
        prefix = sensor.split("_")[0]
        delivering = fetch(hass, config, account, data, f"{prefix}_delivering")
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        count[sensor] = delivering + delivered
    elif "_delivering" in sensor:
        prefix = sensor.split("_")[0]
        delivered = fetch(hass, config, account, data, f"{prefix}_delivered")
        info = get_count(account, sensor, True)
        count[sensor] = max(0, info[const.ATTR_COUNT] - delivered)
        count[f"{prefix}_tracking"] = info[const.ATTR_TRACKING]
    elif sensor == "zpackages_delivered":
        count[sensor] = 0  # initialize the variable
        for shipper in const.SHIPPERS:
            delivered = f"{shipper}_delivered"
            if delivered in data and delivered != sensor:
                count[sensor] += fetch(hass, config, account, data, delivered)
    elif sensor == "zpackages_transit":
        total = 0
        for shipper in const.SHIPPERS:
            delivering = f"{shipper}_delivering"
            if delivering in data and delivering != sensor:
                total += fetch(hass, config, account, data, delivering)
        count[sensor] = max(0, total)
    elif sensor == "mail_updated":
        count[sensor] = update_time()
    else:
        count[sensor] = get_count(account, sensor, False, img_out_path, hass)[
            const.ATTR_COUNT
        ]

    data.update(count)
    _LOGGER.debug("Sensor: %s Count: %s", sensor, str(count[sensor]))
    return count[sensor]


def login(host, port, user, pwd):
    """function used to login"""

    # Catch invalid mail server / host names
    try:
        account = imaplib.IMAP4_SSL(host, port)

    except Exception as err:
        _LOGGER.error("Network error while connecting to server: %s", str(err))
        return False

    # If login fails give error message
    try:
        rv, data = account.login(user, pwd)
    except Exception as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
        return False

    return account


def selectfolder(account, folder):
    """Select folder inside the mailbox"""
    try:
        rv, mailboxes = account.list()
    except Exception as err:
        _LOGGER.error("Error listing folders: %s", str(err))
    try:
        rv, data = account.select(folder)
    except Exception as err:
        _LOGGER.error("Error selecting folder: %s", str(err))


def get_formatted_date() -> str:
    """Returns today in specific format"""
    today = datetime.datetime.today().strftime("%d-%b-%Y")
    #
    # for testing
    # today = "11-Jan-2021"
    #
    return today


def update_time() -> str:
    """gets update time"""
    updated = datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")

    return updated


def email_search(account: Any, address: list, date: str, subject: str = None) -> tuple:
    """Search emails with from, subject, senton date.

    Returns a tuple
    """

    imap_search = None  # Holds our IMAP SEARCH command
    prefix_list = None
    email_list = address
    search = None
    the_date = f'SINCE "{date}"'

    if isinstance(address, list):
        if len(address) == 1:
            email_list = address[0]

        else:
            email_list = '" FROM "'.join(address)
            prefix_list = " ".join(["OR"] * (len(address) - 1))

    if subject is not None:
        search = f'FROM "{email_list}" SUBJECT "{subject}" {the_date}'
    else:
        search = f'FROM "{email_list}" {the_date}'

    if prefix_list is not None:
        imap_search = f"({prefix_list} {search})"
    else:
        imap_search = f"({search})"

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    try:
        value = account.search(None, imap_search)
    except Exception as err:
        _LOGGER.error("Error searching emails: %s", str(err))
        value = "BAD", err.args[0]

    return value


def email_fetch(account: Any, num: int, type: str = "(RFC822)") -> tuple:
    """Download specified email for parsing.

    Returns tuple
    """
    try:
        value = account.fetch(num, type)
    except Exception as err:
        _LOGGER.error("Error fetching emails: %s", str(err))
        value = "BAD", err.args[0]

    return value


def get_mails(
    account: Any,
    image_output_path: str,
    gif_duration: int,
    image_name: str,
    gen_mp4: bool = False,
) -> int:
    """Creates GIF image based on the attachments in the inbox"""
    today = get_formatted_date()
    image_count = 0
    images = []
    imagesDelete = []
    msg = ""
    address = const.SENSOR_DATA[const.ATTR_USPS_MAIL][const.ATTR_EMAIL]
    subject = const.SENSOR_DATA[const.ATTR_USPS_MAIL][const.ATTR_SUBJECT][0]

    _LOGGER.debug("Attempting to find Informed Delivery mail")
    _LOGGER.debug("Informed delivery search date: %s", today)

    (rv, data) = email_search(account, address, today, subject)

    # Check to see if the path exists, if not make it
    pathcheck = os.path.isdir(image_output_path)
    if not pathcheck:
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

    if rv == "OK":
        _LOGGER.debug("Informed Delivery email found processing...")
        for num in data[0].split():
            (rv, data) = email_fetch(account, num, "(RFC822)")
            msg = email.message_from_string(data[0][1].decode("utf-8"))

            # walking through the email parts to find images
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                _LOGGER.debug("Extracting image from email")
                filepath = image_output_path + part.get_filename()

                # Log error message if we are unable to open the filepath for
                # some reason
                try:
                    fp = open(filepath, "wb")
                except Exception as err:
                    _LOGGER.critical("Error opening filepath: %s", str(err))
                    return
                fp.write(part.get_payload(decode=True))
                images.append(filepath)
                image_count = image_count + 1
                fp.close()

        # Remove duplicate images
        _LOGGER.debug("Removing duplicate images.")
        images = list(dict.fromkeys(images))

        # Create copy of image list for deleting temporary images
        imagesDelete = images[:]

        # Look for mail pieces without images image
        html_text = str(msg)
        link_pattern = re.compile(r"\bimage-no-mailpieces?700\.jpg\b")
        search = link_pattern.search(html_text)
        if search is not None:
            images.append(os.path.dirname(__file__) + "/image-no-mailpieces700.jpg")
            image_count = image_count + 1
            _LOGGER.debug(
                "Placeholder image found using: " + "image-no-mailpieces700.jpg."
            )

        # Remove USPS announcement images
        _LOGGER.debug("Removing USPS announcement images.")
        remove_terms = ["mailerProvidedImage", "ra_0", "Mail Attachment.txt"]
        images = [
            el for el in images if not any(ignore in el for ignore in remove_terms)
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
                imagesDelete.append(image)

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
            for image in imagesDelete:
                path = f"{os.path.split(image)[0]}/"
                file = os.path.split(image)[1]
                cleanup_images(path, file)

        elif image_count == 0:
            _LOGGER.info("No mail found.")
            filecheck = os.path.isfile(image_output_path + image_name)
            if filecheck:
                _LOGGER.debug("Removing " + image_output_path + image_name)
                cleanup_images(image_output_path, image_name)

            try:
                _LOGGER.debug("Copying nomail gif")
                copyfile(
                    os.path.dirname(__file__) + "/mail_none.gif",
                    image_output_path + image_name,
                )
            except Exception as err:
                _LOGGER.error("Error attempting to copy image: %s", str(err))

        if gen_mp4:
            _generate_mp4(image_output_path, image_name)

    return image_count


def _generate_mp4(path: str, image_file: str):
    """
    Generate mp4 from gif
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
    """
    Resize images
    This should keep the aspect ratio of the images
    """
    all_images = []
    for image in images:
        try:
            fd_img = open(image, "rb")
        except Exception as err:
            _LOGGER.error("Error attempting to open image %s: %s", str(image), str(err))
            continue
        try:
            img = Image.open(fd_img)
        except Exception as err:
            _LOGGER.error("Error attempting to read image %s: %s", str(image), str(err))
            continue
        img = resizeimage.resize_contain(img, [width, height])
        pre, ext = os.path.splitext(image)
        image = pre + ".gif"
        img.save(image, img.format)
        fd_img.close()
        all_images.append(image)

    return all_images


def copy_overlays(path: str):
    """ Copy overlay images to image output path."""

    overlays = const.OVERLAY
    check = all(item in overlays for item in os.listdir(path))

    # Copy files if they are missing
    if not check:
        for file in overlays:
            _LOGGER.debug("Copying file to: %s", str(path + file))
            copyfile(
                os.path.dirname(__file__) + "/" + file,
                path + file,
            )


def cleanup_images(path: str, image: Optional[str] = None):
    """
    Clean up image storage directory
    Only supose to delete .gif and .mp4 files
    """

    if image is not None:
        try:
            os.remove(path + image)
        except Exception as err:
            _LOGGER.error("Error attempting to remove image: %s", str(err))
        return

    for file in os.listdir(path):
        if file.endswith(".gif") or file.endswith(".mp4"):
            try:
                os.remove(path + file)
            except Exception as err:
                _LOGGER.error("Error attempting to remove found image: %s", str(err))


def get_count(
    account: Any,
    sensor_type: str,
    get_tracking_num: bool = False,
    image_path: Optional[str] = None,
    hass: Optional[Any] = None,
) -> dict:
    """
    Get Package Count
    todo: convert subjects to list and use a for loop
    """
    count = 0
    tracking = []
    result = {}
    today = get_formatted_date()
    body = None
    track = None
    data = None

    # Return Amazon delivered info
    if sensor_type == const.AMAZON_DELIVERED:
        result[const.ATTR_COUNT] = amazon_search(account, image_path, hass)
        result[const.ATTR_TRACKING] = ""
        return result

    # Bail out if unknown sensor type
    if const.ATTR_EMAIL not in const.SENSOR_DATA[sensor_type]:
        _LOGGER.debug("Unknown sensor type: %s", str(sensor_type))
        result[const.ATTR_COUNT] = count
        result[const.ATTR_TRACKING] = ""
        return result

    email = const.SENSOR_DATA[sensor_type][const.ATTR_EMAIL]
    subjects = const.SENSOR_DATA[sensor_type][const.ATTR_SUBJECT]
    if const.ATTR_BODY in const.SENSOR_DATA[sensor_type].keys():
        body = const.SENSOR_DATA[sensor_type][const.ATTR_BODY] or None

    for subject in subjects:

        _LOGGER.debug(
            "Attempting to find mail from (%s) with subject (%s)", email, subject
        )

        (rv, data) = email_search(account, email, today, subject)
        if rv == "OK":
            if body is not None:
                count += find_text(data[0], account, body[0])
            else:
                count += len(data[0].split())

            _LOGGER.debug(
                "Search for (%s) with subject (%s) results: %s count: %s",
                email,
                subject,
                data[0],
                count,
            )

    pattern = f"{sensor_type.split('_')[0]}_tracking"
    if const.ATTR_PATTERN in const.SENSOR_DATA[pattern].keys():
        track = const.SENSOR_DATA[pattern][const.ATTR_PATTERN][0]

    if track is not None and get_tracking_num and count > 0:
        tracking = get_tracking(data[0], account, track)

    if len(tracking) > 0:
        # Use tracking numbers found for count (more accurate)
        count = len(tracking)

    result[const.ATTR_TRACKING] = tracking

    result[const.ATTR_COUNT] = count
    return result


def get_tracking(sdata: Any, account: Any, format: Optional[str] = None) -> list:
    """Parse tracking numbers from email """
    _LOGGER.debug("Searching for tracking numbers...")
    tracking = []
    pattern = None
    mail_list = sdata.split()

    pattern = re.compile(r"{}".format(format))
    for i in mail_list:
        typ, data = email_fetch(account, i, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                # Search subject for a tracking number
                email_subject = msg["subject"]
                found = pattern.findall(email_subject)
                if len(found) > 0:
                    _LOGGER.debug(
                        "Found tracking number in email subject: (%s)",
                        found[0],
                    )
                    if found[0] not in tracking:
                        tracking.append(found[0])
                    continue

                # Search in email body for tracking number
                email_msg = quopri.decodestring(str(msg.get_payload(0)))
                email_msg = email_msg.decode("utf-8", "ignore")
                found = pattern.findall(email_msg)
                if len(found) > 0:
                    # DHL is special
                    if " " in format:
                        found[0] = found[0].split(" ")[1]

                    _LOGGER.debug("Found tracking number in email body: %s", found[0])
                    if found[0] not in tracking:
                        tracking.append(found[0])
                    continue

    if len(tracking) == 0:
        _LOGGER.debug("No tracking numbers found")

    return tracking


def find_text(sdata: Any, account: Any, search: str) -> int:
    """
    Filter for specific words in email
    Return count of items found
    """
    _LOGGER.debug("Searching for (%s) in (%s) emails", search, len(sdata))
    mail_list = sdata.split()
    count = 0
    found = None

    for i in mail_list:
        typ, data = email_fetch(account, i, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                email_msg = quopri.decodestring(str(msg.get_payload(0)))
                email_msg = email_msg.decode("utf-8", "ignore")
                pattern = re.compile(r"{}".format(search))
                found = pattern.findall(email_msg)
                if len(found) > 0:
                    _LOGGER.debug(
                        "Found (%s) in email %s times.", search, str(len(found))
                    )
                    count += len(found)

    _LOGGER.debug("Search for (%s) count results: %s", search, count)
    return count


def amazon_search(account: Any, image_path: str, hass: Any) -> int:
    """ Find Amazon Delivered email """
    _LOGGER.debug("Searching for Amazon delivered email(s)...")
    domains = const.Amazon_Domains.split(",")
    subjects = const.AMAZON_Delivered_Subject
    today = get_formatted_date()
    count = 0

    for domain in domains:
        for subject in subjects:
            email = const.AMAZON_Email + domain
            _LOGGER.debug("Amazon email search address: %s", str(email))

            (rv, data) = email_search(account, email, today, subject)

            if rv != "OK":
                continue

            count += len(data[0].split())
            _LOGGER.debug("Amazon delivered email(s) found: %s", count)
            get_amazon_image(data[0], account, image_path, hass)

    return count


def get_amazon_image(sdata: Any, account: Any, image_path: str, hass: Any):
    """ Find Amazon delivery image """
    _LOGGER.debug("Searching for Amazon image in emails...")
    search = const.AMAZON_IMG_PATTERN

    img_url = None
    mail_list = sdata.split()
    _LOGGER.debug("HTML Amazon emails found: %s", len(mail_list))

    for i in mail_list:
        typ, data = email_fetch(account, i, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                _LOGGER.debug("Email Multipart: %s", str(msg.is_multipart()))
                _LOGGER.debug("Content Type: %s", str(msg.get_content_type()))
                if not msg.is_multipart() and msg.get_content_type() != "text/html":
                    continue
                for part in msg.walk():
                    if part.get_content_type() != "text/html":
                        continue
                    _LOGGER.debug("Processing HTML email...")
                    body = part.get_payload(decode=True)
                    body = body.decode("utf-8", "ignore")
                    pattern = re.compile(r"{}".format(search))
                    found = pattern.findall(body)
                    for url in found:
                        if url[1] != "us-prod-temp.s3.amazonaws.com":
                            continue
                        img_url = url[0] + url[1] + url[2]
                        _LOGGER.debug("Amazon img URL: %s", img_url)
                        break

    if img_url is not None:
        # Download the image we found
        hass.add_job(download_img(img_url, image_path))


async def download_img(img_url: str, img_path: str):
    """ Download image from url """
    filepath = img_path + "amazon_delivered.jpg"
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
                with open(filepath, "wb") as f:
                    f.write(data)
                    _LOGGER.debug("Amazon image downloaded")


def amazon_hub(account: Any, fwds: Optional[str] = None) -> dict:
    """ Find Amazon Hub info and return it """
    email_address = const.AMAZON_HUB_EMAIL
    subject_regex = const.AMAZON_HUB_SUBJECT
    info = {}
    today = get_formatted_date()

    (rv, sdata) = email_search(account, email_address, today)

    if len(sdata) == 0:
        info[const.ATTR_COUNT] = 0
        info[const.ATTR_CODE] = []
        return info

    found = []
    mail_ids = sdata[0]
    id_list = mail_ids.split()
    _LOGGER.debug("Amazon hub emails found: %s", str(len(id_list)))
    for i in id_list:
        typ, data = email_fetch(account, i, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                # Get combo number from subject line
                email_subject = msg["subject"]
                pattern = re.compile(r"{}".format(subject_regex))
                found.append(pattern.search(email_subject).group(3))

    info[const.ATTR_COUNT] = len(found)
    info[const.ATTR_CODE] = found

    return info


def get_items(
    account: Any, param: str, fwds: Optional[str] = None
) -> Union[List[str], int]:
    """Parse Amazon emails for delivery date and order number"""

    _LOGGER.debug("Attempting to find Amazon email with item list ...")

    # Limit to past 3 days (plan to make this configurable)
    past_date = datetime.date.today() - datetime.timedelta(days=3)
    tfmt = past_date.strftime("%d-%b-%Y")
    deliveriesToday = []
    orderNum = []
    domains = const.Amazon_Domains.split(",")
    if isinstance(fwds, list):
        for fwd in fwds:
            if fwd != '""':
                domains.append(fwd)
                _LOGGER.debug("Amazon email adding %s to list", str(fwd))

    for domain in domains:
        if "@" in domain:
            email_address = domain
            _LOGGER.debug("Amazon email search address: %s", str(email_address))
        else:
            email_address = []
            addresses = const.AMAZON_SHIPMENT_TRACKING
            for address in addresses:
                email_address.append(f"{address}@{domain}")
            _LOGGER.debug("Amazon email search address: %s", str(email_address))

        (rv, sdata) = email_search(account, email_address, tfmt)

        if rv == "OK":
            mail_ids = sdata[0]
            id_list = mail_ids.split()
            _LOGGER.debug("Amazon emails found: %s", str(len(id_list)))
            for i in id_list:
                typ, data = email_fetch(account, i, "(RFC822)")
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
                        found = pattern.findall(email_subject)

                        # Don't add the same order number twice
                        if len(found) > 0 and found[0] not in orderNum:
                            orderNum.append(found[0])

                        try:
                            email_msg = quopri.decodestring(str(msg.get_payload(0)))
                        except Exception as err:
                            _LOGGER.debug(
                                "Problem decoding email message: %s", str(err)
                            )
                            continue
                        email_msg = email_msg.decode("utf-8", "ignore")
                        searches = const.AMAZON_TIME_PATTERN.split(",")
                        for search in searches:
                            if search not in email_msg:
                                continue

                            start = email_msg.find(search) + len(search)
                            end = email_msg.find("Track your")
                            arrive_date = email_msg[start:end].strip()
                            arrive_date = arrive_date.split(" ")
                            arrive_date = arrive_date[0:3]
                            arrive_date[2] = arrive_date[2][:2]
                            arrive_date = " ".join(arrive_date).strip()
                            if "today" in arrive_date or "tomorrow" in arrive_date:
                                arrive_date = arrive_date.split(",")[1].strip()
                                dateobj = datetime.datetime.strptime(
                                    arrive_date, "%B %d"
                                )
                            else:
                                dateobj = datetime.datetime.strptime(
                                    arrive_date, "%A, %B %d"
                                )

                            if (
                                dateobj.day == datetime.date.today().day
                                and dateobj.month == datetime.date.today().month
                            ):
                                deliveriesToday.append("Amazon Order")

    if param == "count":
        _LOGGER.debug("Amazon Count: %s", str(len(deliveriesToday)))
        return len(deliveriesToday)
    else:
        _LOGGER.debug("Amazon order: %s", str(orderNum))
        return orderNum
