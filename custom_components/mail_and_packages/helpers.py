""" Functions for Mail and Packages """

import datetime
import email
import imaplib
import logging
import os
import quopri
import re
import subprocess
import uuid
from shutil import copyfile, which

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


def get_resources():
    """Resource selection schema."""

    known_available_resources = {
        sensor_id: sensor[const.SENSOR_NAME]
        for sensor_id, sensor in const.SENSOR_TYPES.items()
    }

    return known_available_resources


async def _validate_path(path):
    """ make sure path is valid """
    if os.path.exists(path):
        return True
    else:
        return False


async def _check_ffmpeg():
    """ check if ffmpeg is installed """
    if which("ffmpeg") is not None:
        return True
    else:
        return False


async def _test_login(host, port, user, pwd):
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


def process_emails(hass, config):
    """ Process emails and return value """
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    folder = config.get(const.CONF_FOLDER)
    user = config.get(CONF_USERNAME)
    pwd = config.get(CONF_PASSWORD)
    img_out_path = config.get(const.CONF_PATH)
    gif_duration = config.get(const.CONF_DURATION)
    image_security = config.get(const.CONF_IMAGE_SECURITY)
    generate_mp4 = config.get(const.CONF_GENERATE_MP4)
    resources = config.get(CONF_RESOURCES)
    amazon_fwds = config.get(const.CONF_AMAZON_FWDS)

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
    if image_security:
        image_name = str(uuid.uuid4()) + ".gif"
    else:
        image_name = const.DEFAULT_GIF_FILE_NAME

    _image[const.ATTR_IMAGE_NAME] = image_name
    data.update(_image)

    # Only update sensors we're intrested in
    for sensor in resources:
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
            delivering = prefix + "_delivering"
            delivered = prefix + "_delivered"
            total = 0
            if delivered in data and delivering in data:
                total = data[delivering] + data[delivered]
            count[sensor] = total
        elif "_delivering" in sensor:
            prefix = sensor.split("_")[0]
            delivering = prefix + "_delivering"
            delivered = prefix + "_delivered"
            tracking = prefix + "_tracking"
            info = get_count(account, sensor, True)
            total = info[const.ATTR_COUNT]
            if delivered in data:
                total = total - data[delivered]
            total = max(0, total)
            count[sensor] = total
            count[tracking] = info[const.ATTR_TRACKING]
        elif sensor == "zpackages_delivered":
            count[sensor] = 0  # initialize the variable
            for shipper in const.SHIPPERS:
                delivered = shipper + "_delivered"
                if delivered in data and delivered != sensor:
                    count[sensor] += data[delivered]
        elif sensor == "zpackages_transit":
            total = 0
            for shipper in const.SHIPPERS:
                delivering = shipper + "_delivering"
                if delivering in data and delivering != sensor:
                    total += data[delivering]
            count[sensor] = max(0, total)
        elif sensor == "mail_updated":
            count[sensor] = update_time()
        else:
            count[sensor] = get_count(account, sensor, False, img_out_path, hass)[
                const.ATTR_COUNT
            ]

        data.update(count)

    return data


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


def get_formatted_date():
    """Returns today in specific format"""
    today = datetime.datetime.today().strftime("%d-%b-%Y")
    #
    # for testing
    # today = '06-May-2020'
    #
    return today


def update_time():
    """gets update time"""
    updated = datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")

    return updated


def email_search(account, address, date, subject=None):
    """Search emails with from, subject, senton date.

    Returns a tuple
    """

    imap_search = None  # Holds our IMAP SEARCH command

    if isinstance(address, list) and subject is not None:
        if len(address) == 1:
            email_list = address[0]
            imap_search = f'(FROM "{email_list}" SUBJECT "{subject}" SENTON "{date}")'
        else:
            email_list = '" FROM "'.join(address)
            prefix_list = " ".join(["OR"] * (len(address) - 1))
            imap_search = f'({prefix_list} FROM "{email_list}" SUBJECT "{subject}" SENTON "{date}")'

    elif subject is not None:
        imap_search = f'(FROM "{address}" SUBJECT "{subject}" SENTON "{date}")'
    else:
        imap_search = f'(FROM "{address}" SENTON "{date}")'

    _LOGGER.debug("DEBUG imap_search: %s", imap_search)

    try:
        value = account.search(None, imap_search)
    except Exception as err:
        _LOGGER.error("Error searching emails: %s", str(err))
        value = "BAD", err.args[0]

    return value


def email_fetch(account, num, type="(RFC822)"):
    """Download specified email for parsing.

    Returns tuple
    """
    try:
        value = account.fetch(num, type)
    except Exception as err:
        _LOGGER.error("Error fetching emails: %s", str(err))
        value = "BAD", err.args[0]

    return value


def get_mails(account, image_output_path, gif_duration, image_name, gen_mp4=False):
    """Creates GIF image based on the attachments in the inbox"""
    today = get_formatted_date()
    image_count = 0
    images = []
    imagesDelete = []
    msg = ""
    address = const.SENSOR_DATA["usps_mail"][const.ATTR_EMAIL][0]
    subject = const.SENSOR_DATA["usps_mail"][const.ATTR_SUBJECT][0]

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


def _generate_mp4(path, image_file):
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


def resize_images(images, width, height):
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


def copy_overlays(path):
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


def cleanup_images(path, image=None):
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


def get_count(account, sensor_type, get_tracking_num=False, image_path=None, hass=None):
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
                count += find_text(data[0], account, body)
            else:
                count += len(data[0].split())

            _LOGGER.debug(
                "Search for (%s) with subject 1 (%s) results: %s count: %s",
                email,
                subject,
                data[0],
                count,
            )

    pattern = f"{sensor_type.split('_')[0]}_tracking"
    if const.ATTR_PATTERN in const.SENSOR_DATA[pattern].keys():
        track = const.SENSOR_DATA[pattern][const.ATTR_PATTERN][0]

    if track is not None and count > 0:
        tracking = get_tracking(data[0], account, track)

    if len(tracking) > 0:
        # Use tracking numbers found for count (more accurate)
        count = len(tracking)

    result[const.ATTR_TRACKING] = tracking

    result[const.ATTR_COUNT] = count
    return result


def get_tracking(sdata, account, format=None):
    """Parse tracking numbers from email """
    _LOGGER.debug("Searching for tracking numbers...")
    tracking = []
    pattern = None
    mail_list = sdata.split()

    pattern = re.compile(r"{}".format(format))
    for i in mail_list:
        typ, data = email_fetch(account, i, "(RFC822)")
        for response_part in data:
            if not isinstance(response_part, tuple):
                continue
            msg = email.message_from_bytes(response_part[1])

            # Search subject for a tracking number
            email_subject = msg["subject"]
            found = pattern.findall(email_subject)
            if len(found) > 0:
                _LOGGER.debug(
                    "Found tracking number in email subject: (%s)",
                    found[0],
                )
                if found[0] in tracking:
                    continue
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
                if found[0] in tracking:
                    continue
                tracking.append(found[0])
                continue

    if len(tracking) == 0:
        _LOGGER.debug("No tracking numbers found")

    return tracking


def find_text(sdata, account, search):
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
            if not isinstance(response_part, tuple):
                continue
            msg = email.message_from_bytes(response_part[1])
            email_msg = quopri.decodestring(str(msg.get_payload(0)))
            try:
                email_msg = email_msg.decode("utf-8", "ignore")
            except Exception as err:
                _LOGGER.warning(
                    "Error while attempting to find (%s) in email: %s",
                    search,
                    str(err),
                )
                continue
            pattern = re.compile(r"{}".format(search))
            found = pattern.search(email_msg)
            if found is not None:
                _LOGGER.debug("Found (%s) in email", search)
                count += 1

    _LOGGER.debug("Search for (%s) count results: %s", search, count)
    return count


def amazon_search(account, image_path, hass):
    """ Find Amazon Delivered email """
    _LOGGER.debug("Searching for Amazon delivered email(s)...")
    domains = const.Amazon_Domains.split(",")
    subject = const.AMAZON_Delivered_Subject
    today = get_formatted_date()
    count = 0

    for domain in domains:
        email = const.AMAZON_Email + domain
        _LOGGER.debug("Amazon email search address: %s", str(email))

        (rv, data) = email_search(account, email, today, subject)

        if rv != "OK":
            continue

        count += len(data[0].split())
        _LOGGER.debug("Amazon delivered email(s) found: %s", count)
        get_amazon_image(data[0], account, image_path, hass)

    return count


def get_amazon_image(sdata, account, image_path, hass):
    """ Find Amazon delivery image """
    _LOGGER.debug("Searching for Amazon image in emails...")
    search = const.AMAZON_IMG_PATTERN

    img_url = None
    mail_list = sdata.split()
    _LOGGER.debug("HTML Amazon emails found: %s", len(mail_list))

    for i in mail_list:
        typ, data = email_fetch(account, i, "(RFC822)")
        for response_part in data:
            if not isinstance(response_part, tuple):
                continue
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
                body = body.decode("utf-8")
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


async def download_img(img_url, img_path):
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


def amazon_hub(account, fwds=None):
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
            if not isinstance(response_part, tuple):
                continue
            msg = email.message_from_bytes(response_part[1])

            # Get combo number from subject line
            email_subject = msg["subject"]
            pattern = re.compile(r"{}".format(subject_regex))
            found.append(pattern.search(email_subject).group(3))

    info[const.ATTR_COUNT] = len(found)
    info[const.ATTR_CODE] = found

    return info


def get_items(account, param, fwds=None):
    """Parse Amazon emails for delivery date and order number"""

    _LOGGER.debug("Attempting to find Amazon email with item list ...")

    # Limit to past 3 days (plan to make this configurable)
    past_date = datetime.date.today() - datetime.timedelta(days=3)
    tfmt = past_date.strftime("%d-%b-%Y")
    deliveriesToday = []
    orderNum = []
    domains = const.Amazon_Domains.split(",")
    if fwds and fwds != '""':
        for fwd in fwds:
            domains.append(fwd)

    for domain in domains:
        if "@" in domain:
            email_address = domain
            _LOGGER.debug("Amazon email search address: %s", str(email_address))
        else:
            email_address = "shipment-tracking@" + domain
            _LOGGER.debug("Amazon email search address: %s", str(email_address))

        (rv, sdata) = email_search(account, email_address, tfmt)

        if rv == "OK":
            mail_ids = sdata[0]
            id_list = mail_ids.split()
            _LOGGER.debug("Amazon emails found: %s", str(len(id_list)))
            for i in id_list:
                typ, data = email_fetch(account, i, "(RFC822)")
                for response_part in data:
                    if not isinstance(response_part, tuple):
                        continue
                    msg = email.message_from_bytes(response_part[1])

                    _LOGGER.debug("Email Multipart: %s", str(msg.is_multipart()))
                    _LOGGER.debug("Content Type: %s", str(msg.get_content_type()))

                    # Get order number from subject line
                    email_subject = msg["subject"]
                    pattern = re.compile(r"#[0-9]{3}-[0-9]{7}-[0-9]{7}")
                    found = pattern.findall(email_subject)

                    # Don't add the same order number twice
                    if len(found) > 0 and found[0] not in orderNum:
                        orderNum.append(found[0])

                    # Catch bad format emails
                    try:
                        email_msg = quopri.decodestring(str(msg.get_payload(0)))
                        email_msg = email_msg.decode("utf-8", "ignore")
                    except Exception as err:
                        _LOGGER.debug(
                            "Error while attempting to parse Amazon email: %s",
                            str(err),
                        )
                        continue

                    searches = const.AMAZON_TIME_PATTERN.split(",")
                    for search in searches:
                        if search not in email_msg:
                            continue

                        start = email_msg.find(search) + len(search)
                        end = email_msg.find("Track your package:")
                        arrive_date = email_msg[start:end].strip()
                        arrive_date = arrive_date.split(" ")
                        arrive_date = arrive_date[0:3]
                        arrive_date[2] = arrive_date[2][:2]
                        arrive_date = " ".join(arrive_date).strip()
                        if "today" in arrive_date or "tomorrow" in arrive_date:
                            arrive_date = arrive_date.split(",")[1].strip()
                            dateobj = datetime.datetime.strptime(arrive_date, "%B %d")
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
    elif param == "order":
        _LOGGER.debug("Amazon order: %s", str(orderNum))
        return orderNum
    else:
        _LOGGER.debug("Amazon json: %s", str(deliveriesToday))
        return deliveriesToday
