"""
Based on @skalavala work at
https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html

Configuration code contribution from @firstof9 https://github.com/firstof9/
"""

import logging
import imageio as io
import os
import subprocess
import re
import imaplib
import email
import datetime
import uuid
from datetime import timedelta
from shutil import copyfile
from PIL import Image
from resizeimage import resizeimage
import quopri

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

from .const import (
    CONF_FOLDER,
    CONF_PATH,
    CONF_DURATION,
    CONF_IMAGE_SECURITY,
    CONF_SCAN_INTERVAL,
    CONF_GENERATE_MP4,
    DEFAULT_GIF_FILE_NAME,
    USPS_Mail_Email,
    USPS_Packages_Email,
    USPS_Mail_Subject,
    USPS_Delivering_Subject,
    USPS_Delivered_Subject,
    USPS_Body_Text,
    UPS_Email,
    UPS_Delivering_Subject,
    UPS_Delivering_Subject_2,
    UPS_Delivered_Subject,
    FEDEX_Email,
    FEDEX_Delivering_Subject,
    FEDEX_Delivering_Subject_2,
    FEDEX_Delivered_Subject,
    Amazon_Domains,
    CAPost_Email,
    CAPost_Delivered_Subject,
)

_LOGGER = logging.getLogger(__name__)

# Sensor definitions
# Name, unit of measure, icon
SENSOR_TYPES = {
    "mail_updated": ["Mail Updated", None, "mdi:update",],
    "usps_mail": ["Mail USPS Mail", "piece(s)", "mdi:mailbox-up",],
    "usps_delivered": [
        "Mail USPS Delivered",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    "usps_delivering": ["Mail USPS Delivering", "package(s)", "mdi:truck-delivery",],
    "usps_packages": [
        "Mail USPS Packages",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    "ups_delivered": [
        "Mail UPS Delivered",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    "ups_delivering": ["Mail UPS Delivering", "package(s)", "mdi:truck-delivery",],
    "ups_packages": ["Mail UPS Packages", "package(s)", "mdi:package-variant-closed",],
    "fedex_delivered": [
        "Mail FedEx Delivered",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    "fedex_delivering": ["Mail FedEx Delivering", "package(s)", "mdi:truck-delivery",],
    "fedex_packages": [
        "Mail FedEx Packages",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    "amazon_packages": ["Mail Amazon Packages", "package(s)", "mdi:amazon",],
    "capost_delivered": [
        "Mail Canada Post Delivered",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    "capost_packages": [
        "Mail Canada Post Packages",
        "package(s)",
        "mdi:package-variant-closed",
    ],
    ###
    # !!! Insert new sensors above these two !!!
    ###
    "packages_delivered": [
        "Mail Packages Delivered",
        "package(s)",
        "mdi:package-variant",
    ],
    "packages_transit": [
        "Mail Packages In Transit",
        "package(s)",
        "mdi:truck-delivery",
    ],
}


async def async_setup_entry(hass, entry, async_add_entities):

    config = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_USERNAME: entry.data[CONF_USERNAME],
        CONF_PASSWORD: entry.data[CONF_PASSWORD],
        CONF_PORT: entry.data[CONF_PORT],
        CONF_FOLDER: entry.data[CONF_FOLDER],
        CONF_PATH: entry.data[CONF_PATH],
        CONF_DURATION: entry.data[CONF_DURATION],
        CONF_IMAGE_SECURITY: entry.data[CONF_IMAGE_SECURITY],
        CONF_SCAN_INTERVAL: entry.data[CONF_SCAN_INTERVAL],
        CONF_GENERATE_MP4: entry.data[CONF_GENERATE_MP4],
    }

    data = EmailData(hass, config)
    sensors = []

    for variable in SENSOR_TYPES:
        sensors.append(PackagesSensor(data, variable))

    async_add_entities(sensors, True)


class EmailData:
    """The class for handling the data retrieval."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._img_out_path = config.get(CONF_PATH)
        self._gif_duration = config.get(CONF_DURATION)
        self._image_security = config.get(CONF_IMAGE_SECURITY)
        self._generate_mp4 = config.get(CONF_GENERATE_MP4)
        self._scan_interval = timedelta(minutes=config.get(CONF_SCAN_INTERVAL))
        self._data = None
        self._image_name = None

        _LOGGER.debug("Config scan interval: %s", self._scan_interval)

        self.update = Throttle(self._scan_interval)(self.update)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}
        if self._state:
            attr["server"] = self.data._host
        return attr

    def update(self):
        """Get the latest data"""
        if self._host is not None:
            """Login to email server and select the folder"""
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)

            if self._image_security:
                self._image_name = str(uuid.uuid4()) + ".gif"
            else:
                self._image_name = DEFAULT_GIF_FILE_NAME

            data = {}

            for sensor in SENSOR_TYPES:
                count = {}
                if sensor == "usps_mail":
                    count[sensor] = get_mails(
                        account,
                        self._img_out_path,
                        self._gif_duration,
                        self._image_name,
                        self._generate_mp4,
                    )
                elif sensor == "amazon_packages":
                    count[sensor] = get_items(account, "count")
                    count["amazon_order"] = get_items(account, "order")
                elif sensor == "usps_packages":
                    total = data["usps_delivering"] + data["usps_delivered"]
                    count[sensor] = total
                elif sensor == "ups_packages":
                    total = data["ups_delivering"] + data["ups_delivered"]
                    count[sensor] = total
                elif sensor == "fedex_packages":
                    total = data["fedex_delivering"] + data["fedex_delivered"]
                    count[sensor] = total
                elif sensor == "capost_packages":
                    total = data["capost_delivered"]
                    count[sensor] = total
                elif sensor == "usps_delivering":
                    total = int(get_count(account, sensor)) - data["usps_delivered"]
                    if total < 0:
                        total = 0
                    count[sensor] = total
                elif sensor == "fedex_delivering":
                    total = int(get_count(account, sensor)) - data["fedex_delivered"]
                    if total < 0:
                        total = 0
                    count[sensor] = total
                elif sensor == "ups_delivering":
                    total = int(get_count(account, sensor)) - data["ups_delivered"]
                    if total < 0:
                        total = 0
                    count[sensor] = total
                elif sensor == "packages_delivered":
                    count[sensor] = (
                        data["fedex_delivered"]
                        + data["ups_delivered"]
                        + data["usps_delivered"]
                        + data["capost_delivered"]
                    )
                elif sensor == "packages_transit":
                    total = (
                        data["fedex_delivering"]
                        + data["ups_delivering"]
                        + data["usps_delivering"]
                    )
                    if total < 0:
                        total = 0
                    count[sensor] = total
                elif sensor == "mail_updated":
                    count[sensor] = update_time()
                else:
                    count[sensor] = get_count(account, sensor)

                data.update(count)
            self._data = data
        else:
            _LOGGER.error("Host was left blank not attempting connection")

        self._scan_time = update_time()
        _LOGGER.debug("Updated scan time: %s", self._scan_time)


class PackagesSensor(Entity):

    """ Represntation of a sensor """

    def __init__(self, data, sensor_type):
        """ Initialize the sensor """
        self._name = SENSOR_TYPES[sensor_type][0]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.type = sensor_type
        self.data = data
        self._state = None
        self.update()

    @property
    def unique_id(self):
        """
        Return a unique, Home Assistant friendly identifier for this entity.
        """
        return f"{self.data._host}_{self._name}"

    @property
    def name(self):
        """Return the name of the sensor."""

        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""

        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the unit of measurement."""

        return self._icon

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}
        attr["server"] = self.data._host
        if "amazon" in self._name:
            attr["order"] = self.data._data["amazon_order"]
        elif "Mail USPS Mail" == self._name:
            attr["image"] = self.data._image_name
        return attr

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        self.data.update()
        # Using a dict to send the data back
        self._state = self.data._data[self.type]


def login(host, port, user, pwd):
    """function used to login"""

    # Catch invalid mail server / host names
    try:
        account = imaplib.IMAP4_SSL(host, port)
    except imaplib.IMAP4.error as err:
        _LOGGER.error("Error connecting into IMAP Server: %s", str(err))
        return False
    # If login fails give error message
    try:
        rv, data = account.login(user, pwd)
    except imaplib.IMAP4.error as err:
        _LOGGER.error("Error logging into IMAP Server: %s", str(err))
    return account


def selectfolder(account, folder):
    """Select folder inside the mailbox"""
    try:
        rv, mailboxes = account.list()
    except imaplib.IMAP4.error as err:
        _LOGGER.error("Error listing folders: %s", str(err))
    try:
        rv, data = account.select(folder)
    except imaplib.IMAP4.error as err:
        _LOGGER.error("Error selecting folder: %s", str(err))


def get_formatted_date():
    """Returns today in specific format"""
    today = datetime.datetime.today().strftime("%d-%b-%Y")
    """
    # for testing
    # today = '06-May-2020'
    """
    return today


def update_time():
    """gets update time"""
    updated = datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")

    return updated


def get_mails(account, image_output_path, gif_duration, image_name, gen_mp4=False):
    """Creates GIF image based on the attachments in the inbox"""
    today = get_formatted_date()
    image_count = 0
    images = []
    imagesDelete = []
    msg = ""

    _LOGGER.debug("Attempting to find Informed Delivery mail")

    (rv, data) = account.search(
        None,
        '(FROM "'
        + USPS_Mail_Email
        + '" SUBJECT "'
        + USPS_Mail_Subject
        + '" SENTON "'
        + today
        + '")',
    )

    """Check to see if the path exists, if not make it"""
    pathcheck = os.path.isdir(image_output_path)
    if not pathcheck:
        try:
            os.makedirs(image_output_path)
        except Exception as err:
            _LOGGER.critical("Error creating directory: %s", str(err))

    """Clean up image directory"""
    _LOGGER.debug("Cleaning up image directory: %s", str(image_output_path))
    cleanup_images(image_output_path)

    if rv == "OK":
        _LOGGER.debug("Informed Delivery email found processing...")
        for num in data[0].split():
            (rv, data) = account.fetch(num, "(RFC822)")
            msg = email.message_from_string(data[0][1].decode("utf-8"))

            """walking through the email parts to find images"""
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                _LOGGER.debug("Extracting image from email")
                filepath = image_output_path + part.get_filename()

                """Log error message if we are unable to open the filepath for
                some reason"""
                try:
                    fp = open(filepath, "wb")
                except Exception as err:
                    _LOGGER.critical("Error opening filepath: %s", str(err))
                fp.write(part.get_payload(decode=True))
                images.append(filepath)
                image_count = image_count + 1
                fp.close()

        """Remove duplicate images"""
        _LOGGER.debug("Removing duplicate images.")
        images = list(dict.fromkeys(images))

        """Create copy of image list for deleting temporary images"""
        imagesDelete = images[:]

        """Look for mail pieces without images image"""
        html_text = str(msg)
        link_pattern = re.compile(r"\bimage-no-mailpieces?700\.jpg\b")
        search = link_pattern.search(html_text)
        if search is not None:
            images.append(os.path.dirname(__file__) + "/image-no-mailpieces700.jpg")
            image_count = image_count + 1
            _LOGGER.debug(
                "Placeholder image found using: " + "image-no-mailpieces700.jpg."
            )

        """Remove USPS announcement images"""
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
            """Resize images to 724x320"""
            all_images = resize_images(images, 724, 320)

            """Create copy of image list for deleting temporary images"""
            for image in all_images:
                imagesDelete.append(image)

            """Create numpy array of images"""
            _LOGGER.debug("Creating array of image files...")
            all_images = [io.imread(image) for image in all_images]

            try:
                _LOGGER.debug("Generating animated GIF")
                """Use ImageIO to create mail images"""
                io.mimwrite(
                    os.path.join(image_output_path, image_name),
                    all_images,
                    duration=gif_duration,
                )
                _LOGGER.info("Mail image generated.")
            except Exception as err:
                _LOGGER.error("Error attempting to generate image: %s", str(err))
            for image in imagesDelete:
                try:
                    os.remove(image)
                except Exception as err:
                    _LOGGER.error("Error attempting to remove image: %s", str(err))

        elif image_count == 0:
            _LOGGER.info("No mail found.")
            filecheck = os.path.isfile(image_output_path + image_name)
            if filecheck:
                try:
                    _LOGGER.debug("Removing " + image_output_path + image_name)
                    os.remove(image_output_path + image_name)
                except Exception as err:
                    _LOGGER.error("Error attempting to remove image: %s", str(err))
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
        try:
            os.remove(mp4_file)
            _LOGGER.debug("Removing old mp4: %s", mp4_file)
        except Exception as err:
            _LOGGER.error("Error attempting to remove mp4: %s", str(err))

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


def cleanup_images(path):
    """
    Clean up image storage directory
    Only supose to delete .gif and .mp4 files
    """
    for file in os.listdir(path):
        if file.endswith(".gif") or file.endswith(".mp4"):
            os.remove(path + file)


def get_count(account, sensor_type):
    """
    Get Package Count
    add IF clauses to filter by sensor_type for email and subjects
    todo: convert subjects to list and use a for loop
    """
    count = 0
    today = get_formatted_date()
    email = None
    subject = None
    subject_2 = None
    filter_text = None

    if sensor_type == "usps_delivered":
        email = USPS_Packages_Email
        subject = USPS_Delivered_Subject
    elif sensor_type == "usps_delivering":
        email = USPS_Packages_Email
        subject = USPS_Delivering_Subject
        filter_text = USPS_Body_Text
    elif sensor_type == "ups_delivered":
        email = UPS_Email
        subject = UPS_Delivered_Subject
    elif sensor_type == "ups_delivering":
        email = UPS_Email
        subject = UPS_Delivering_Subject
        subject_2 = UPS_Delivering_Subject_2
    elif sensor_type == "fedex_delivering":
        email = FEDEX_Email
        subject = FEDEX_Delivering_Subject
        subject_2 = FEDEX_Delivering_Subject_2
    elif sensor_type == "fedex_delivered":
        email = FEDEX_Email
        subject = FEDEX_Delivered_Subject
    elif sensor_type == "capost_delivered":
        email = CAPost_Email
        subject = CAPost_Delivered_Subject
    else:
        _LOGGER.error("Unknown sensor type: %s", str(sensor_type))
        return False

    _LOGGER.debug("Attempting to find mail from %s with subject 1 %s", email, subject)
    try:
        (rv, data) = account.search(
            None,
            '(FROM "' + email + '" SUBJECT "' + subject + '" SENTON "' + today + '")',
        )
    except imaplib.IMAP4.error as err:
        _LOGGER.error("Error searching emails: %s", str(err))
        return False

    if rv == "OK":
        if filter_text is not None:
            count += find_text(data[0], account, filter_text)
        else:
            count += len(data[0].split())
        _LOGGER.debug(
            "Search for %s with subject 1 %s results: %s", email, subject, data[0]
        )

    if subject_2 is not None:
        _LOGGER.debug(
            "Attempting to find mail from %s with subject 2 %s", email, subject_2
        )
        try:
            (rv, data) = account.search(
                None,
                '(FROM "'
                + email
                + '" SUBJECT "'
                + subject_2
                + '" SENTON "'
                + today
                + '")',
            )
        except imaplib.IMAP4.error as err:
            _LOGGER.error("Error searching emails: %s", str(err))
            return False

        if rv == "OK":
            if filter_text is not None:
                count += find_text(data[0], account, filter_text)
            else:
                count += len(data[0].split())
            _LOGGER.debug(
                "Search for %s with subject 2 %s results: %s", email, subject_2, data[0]
            )

    return count


def find_text(sdata, account, search):
    """Filter for specific words in email"""
    _LOGGER.debug("Searching for %s in emails", search)
    mail_list = sdata.split()
    count = 0

    for i in mail_list:
        typ, data = account.fetch(i, "(RFC822)")
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                email_msg = quopri.decodestring(str(msg.get_payload(0)))
                email_msg = email_msg.decode("utf-8")
                pattern = re.compile(r"\b{}\b".format(search))
                found = pattern.search(email_msg)
                if found is not None:
                    _LOGGER.debug("Found %s in email", search)
                    count += 1

    return count


def get_items(account, param):
    """Parse Amazon emails for delivery date and order number"""

    _LOGGER.debug("Attempting to find Amazon email with item list ...")

    """Limit to past 3 days (plan to make this configurable)"""
    past_date = datetime.date.today() - datetime.timedelta(days=3)
    tfmt = past_date.strftime("%d-%b-%Y")
    deliveriesToday = []
    orderNum = []
    domains = Amazon_Domains.split(",")

    for domain in domains:
        try:
            email_address = "shipment-tracking@" + domain
            (rv, sdata) = account.search(
                None, '(FROM "' + email_address + '" SINCE ' + tfmt + ")"
            )
        except imaplib.IMAP4.error as err:
            _LOGGER.error("Error searching emails: %s", str(err))

        else:
            mail_ids = sdata[0]
            id_list = mail_ids.split()
            _LOGGER.debug("Amazon emails found: %s", str(len(id_list)))
            for i in id_list:
                typ, data = account.fetch(i, "(RFC822)")
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        """Get order number from subject line"""
                        email_subject = msg["subject"]
                        pattern = re.compile(r"#[0-9]{3}-[0-9]{7}-[0-9]{7}")
                        found = pattern.search(email_subject)
                        if found is not None:
                            orderNum.append(found[0])

                        """Catch bad format emails"""
                        try:
                            email_msg = quopri.decodestring(str(msg.get_payload(0)))
                            email_msg = email_msg.decode("utf-8")
                        except Exception as err:
                            _LOGGER.debug(
                                "Error while attempting to parse Amazon " + "email: %s",
                                str(err),
                            )
                            continue

                        if "will arrive:" in email_msg:
                            start = email_msg.find("will arrive:") + len("will arrive:")
                            end = email_msg.find("Track your package:")
                            arrive_date = email_msg[start:end].strip()
                            arrive_date = arrive_date.split(" ")
                            arrive_date = arrive_date[0:3]
                            arrive_date[2] = arrive_date[2][:2]
                            arrive_date = " ".join(arrive_date).strip()
                            dateobj = datetime.datetime.strptime(
                                arrive_date, "%A, %B %d"
                            )
                            if (
                                dateobj.day == datetime.date.today().day
                                and dateobj.month == datetime.date.today().month
                            ):
                                deliveriesToday.append("Amazon Order")

                        elif "estimated delivery date is:" in email_msg:
                            start = email_msg.find("estimated delivery date is:") + len(
                                "estimated delivery date is:"
                            )
                            end = email_msg.find("Track your package at")
                            arrive_date = email_msg[start:end].strip()
                            arrive_date = arrive_date.split(" ")
                            arrive_date = arrive_date[0:3]
                            arrive_date[2] = arrive_date[2][:2]
                            arrive_date = " ".join(arrive_date).strip()
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
