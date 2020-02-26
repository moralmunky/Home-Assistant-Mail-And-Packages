"""
Based on @skalavala work at
https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html

Configuration code contribution from @firstof9 https://github.com/firstof9/
"""

import asyncio
import logging
import imageio as io
# from skimage.transform import resize
# from skimage import img_as_ubyte
import os
import re
import imaplib
import email
import datetime
from datetime import timedelta
from shutil import copyfile

from homeassistant.helpers.entity import Entity

from homeassistant.const import (
     CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD)

from .const import (
    CONF_FOLDER,
    CONF_PATH,
    CONF_DURATION,
    USPS_Mail_Email,
    USPS_Packages_Email,
    USPS_Mail_Subject,
    USPS_Delivering_Subject,
    USPS_Delivered_Subject,
    UPS_Email,
    UPS_Delivering_Subject,
    UPS_Delivering_Subject_2,
    UPS_Delivered_Subject,
    FEDEX_Email,
    FEDEX_Delivering_Subject,
    FEDEX_Delivering_Subject_2,
    FEDEX_Delivered_Subject,
    GIF_FILE_NAME,
)

from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


async def async_setup_entry(hass, entry, async_add_entities):

    # _LOGGER.info('version %s is starting, if you have any issues please report'
    #              ' them here: %s', VERSION, ISSUE_URL)

    config = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_USERNAME: entry.data[CONF_USERNAME],
        CONF_PASSWORD: entry.data[CONF_PASSWORD],
        CONF_PORT: entry.data[CONF_PORT],
        CONF_FOLDER: entry.data[CONF_FOLDER],
        CONF_PATH: entry.data[CONF_PATH],
        CONF_DURATION: entry.data[CONF_DURATION]
    }

    data = EmailData(hass, config)

    async_add_entities([MailCheck(data), USPS_Mail(hass, data),
                       USPS_Packages(hass, data),
                       USPS_Delivering(hass, data),
                       USPS_Delivered(hass, data),
                       UPS_Packages(hass, data),
                       UPS_Delivering(hass, data),
                       UPS_Delivered(hass, data),
                       FEDEX_Packages(hass, data),
                       FEDEX_Delivering(hass, data),
                       FEDEX_Delivered(hass, data),
                       Packages_Delivered(hass, data),
                       Packages_Transit(hass, data)], True)


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
        self._fedex_delivered = None
        self._fedex_delivering = None
        self._fedex_packages = None
        self._ups_packages = None
        self._ups_delivering = None
        self._ups_delivered = None
        self._usps_packages = None
        self._usps_delivering = None
        self._usps_delivered = None
        self._usps_mail = None
        self._packages_delivered = None
        self._packages_transit = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data"""
        if self._host is not None:
            # Login to email server and select the folder
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)

            # Tally emails and generate mail images
            self._usps_mail = get_mails(account, self._img_out_path,
                                        self._gif_duration)
            self._usps_delivering = get_count(account, USPS_Packages_Email,
                                              USPS_Delivering_Subject)
            self._usps_delivered = get_count(account, USPS_Packages_Email,
                                             USPS_Delivered_Subject)
            self._usps_packages = self._usps_delivering + self._usps_delivered
            self._ups_delivered = get_count(account, UPS_Email,
                                            UPS_Delivered_Subject)
            self._ups_delivering = (get_count(account, UPS_Email,
                                              UPS_Delivering_Subject) +
                                    get_count(account, UPS_Email,
                                              UPS_Delivering_Subject_2))
            self._ups_packages = self._ups_delivered + self._ups_delivering
            self._fedex_delivered = get_count(account, FEDEX_Email,
                                              FEDEX_Delivered_Subject)
            self._fedex_delivering = (get_count(account, FEDEX_Email,
                                                FEDEX_Delivering_Subject) +
                                      get_count(account, FEDEX_Email,
                                                FEDEX_Delivering_Subject_2))
            self._fedex_packages = (self._fedex_delivered +
                                    self._fedex_delivering)
            self._packages_transit = (self._fedex_delivering +
                                      self._ups_delivering +
                                      self._usps_delivering)
            self._packages_delivered = (self._fedex_delivered +
                                        self._ups_delivered +
                                        self._usps_delivered)

            # Subtract the number of delivered packages from those in transit
            if self._packages_transit >= self._packages_delivered:
                self._packages_transit -= self._packages_delivered

        else:
            _LOGGER.debug("Host was left blank not attempting connection")


class MailCheck(Entity):

    """Representation of a Sensor."""

    def __init__(self, data):
        """Initialize the sensor."""
        self._name = 'Mail Updated'
        self.data = data
        self._state = None
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:update"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        self._state = update_time()


class USPS_Mail(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail USPS Mail'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Items'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:mailbox-up"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._usps_mail


class USPS_Packages(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail USPS Packages'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:package-variant-closed"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._usps_packages


class USPS_Delivering(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail USPS Delivering'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:truck-delivery"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._usps_delivering


class USPS_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail USPS Delivered'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:package-variant-closed"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._usps_delivered


class Packages_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail Packages Delivered'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""
        return "mdi:package-variant"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._packages_delivered


class Packages_Transit(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail Packages In Transit'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""
        return "mdi:truck-delivery"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._packages_transit


class UPS_Packages(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail UPS Packages'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:package-variant-closed"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._ups_packages


class UPS_Delivering(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail UPS Delivering'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:truck-delivery"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._ups_delivering


class UPS_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail UPS Delivered'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:package-variant-closed"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._ups_delivered


class FEDEX_Packages(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail FEDEX Packages'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:package-variant-closed"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._fedex_packages


class FEDEX_Delivering(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail FEDEX Delivering'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:truck-delivery"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._fedex_delivering


class FEDEX_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, data):
        """Initialize the sensor."""
        self._name = 'Mail FEDEX Delivered'
        self.data = data
        self._state = 0
        self.update()

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
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
        """Return the unit of measurement."""

        return 'Packages'

    @property
    def icon(self):
        """Return the unit of measurement."""

        return "mdi:package-variant"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.data.update()
        self._state = self.data._fedex_delivered

# Login Method
###############################################################################


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

# Select folder inside the mailbox
###############################################################################


def selectfolder(account, folder):
    rv, mailboxes = account.list()
    rv, data = account.select(folder)


# Returns today in specific format
###############################################################################

def get_formatted_date():
    return datetime.datetime.today().strftime('%d-%b-%Y')


# gets update time
###############################################################################

def update_time():
    updated = datetime.datetime.now().strftime('%b-%d-%Y %I:%M %p')

    return updated


# Creates GIF image based on the attachments in the inbox
###############################################################################

def get_mails(account, image_output_path, gif_duration):
    today = get_formatted_date()
    image_count = 0
    images = []
    imagesDelete = []
    msg = ''

    _LOGGER.debug("Attempting to find Informed Delivery mail")

    (rv, data) = account.search(None,
                                '(FROM "' + USPS_Mail_Email + '" SUBJECT "' +
                                USPS_Mail_Subject + '" ON "' + today + '")')

    # Get number of emails found
    # messageIDsString = str(data[0], encoding='utf8')
    # listOfSplitStrings = messageIDsString.split(" ")
    # msg_count = len(listOfSplitStrings)

    if rv == 'OK':
        _LOGGER.debug("Informed Delivery email found processing...")
        for num in data[0].split():
            (rv, data) = account.fetch(num, '(RFC822)')
            msg = email.message_from_string(data[0][1].decode('utf-8'))

            # walking through the email parts to find images
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue

                _LOGGER.debug("Extracting image from email")
                filepath = image_output_path + part.get_filename()

                # Check to see if the path exists, if not make it
                pathcheck = os.path.isdir(image_output_path)
                if not pathcheck:
                    try:
                        os.mkdir(image_output_path)
                    except Exception as err:
                        _LOGGER.critical("Error creating directory: %s",
                                         str(err))

                # Log error message if we are unable to open the filepath for
                # some reason
                try:
                    fp = open(filepath, 'wb')
                except Exception as err:
                    _LOGGER.critical("Error opening filepath: %s", str(err))
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
        link_pattern = re.compile('image-no-mailpieces700.jpg')
        search = link_pattern.search(html_text)
        if search is not None:
            images.append(os.path.dirname(__file__) +
                          '/image-no-mailpieces700.jpg')
            image_count = image_count + 1
            _LOGGER.debug("Placeholder image found using: " +
                          "image-no-mailpieces700.jpg.")

        # Remove USPS announcement images
        _LOGGER.debug("Removing USPS announcement images.")
        remove_terms = ['mailerProvidedImage', 'ra_0', 'Mail Attachment.txt']
        images = [el for el in images if not any(ignore in el for ignore
                                                 in remove_terms)]
        image_count = len(images)
        _LOGGER.debug("Image Count: %s", str(image_count))

        if image_count > 0:
            all_images = []

            # _LOGGER.debug("Resizing images to 700x315...")
            # # Resize images to 700x315
            # all_images = resize_images(all_images)

            _LOGGER.debug("Creating array of image files...")
            # Create numpy array of images
            all_images = [io.imread(image) for image in images]

            try:
                _LOGGER.debug("Generating animated GIF")
                # Use ImageIO to create mail images
                io.mimwrite(os.path.join(image_output_path, GIF_FILE_NAME),
                            all_images, duration=gif_duration)
                _LOGGER.info("Mail image generated.")
            except Exception as err:
                _LOGGER.error("Error attempting to generate image: %s",
                              str(err))
            for image in imagesDelete:
                try:
                    os.remove(image)
                except Exception as err:
                    _LOGGER.error("Error attempting to remove image: %s",
                                  str(err))

        elif image_count == 0:
            _LOGGER.info("No mail found.")
            try:
                _LOGGER.debug("Removing " + image_output_path + GIF_FILE_NAME)
                os.remove(image_output_path + GIF_FILE_NAME)
            except Exception as err:
                _LOGGER.error("Error attempting to remove image: %s", str(err))
            try:
                _LOGGER.debug("Copying nomail gif")
                copyfile(os.path.dirname(__file__) + '/mail_none.gif',
                         image_output_path + GIF_FILE_NAME)
            except Exception as err:
                _LOGGER.error("Error attempting to copy image: %s", str(err))

    return image_count

# Resize images
# This should keep the aspect ratio of the images
#################################################


# def resize_images(images):
    # sized_images = []
    # for image in images:
    #     if image.shape[1] < 700:
    #         wpercent = 700/image.shape[1]
    #         height = int(float(image.shape[0])*float(wpercent))
    #         sized_images.append(img_as_ubyte(resize(image, (height, 700))))
    #     else:
        # sized_images.append(img_as_ubyte(resize(image, (317, 700),
        #                     mode='symmetric')))


    # return sized_images


# Get Package Count
###############################################################################


def get_count(account, email, subject):
    count = 0
    today = get_formatted_date()

    _LOGGER.debug("Attempting to find mail from %s with subject %s", email,
                  subject)

    (rv, data) = account.search(None, '(FROM "' + email + '" SUBJECT "'
                                + subject + '" ON "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())

    return count
