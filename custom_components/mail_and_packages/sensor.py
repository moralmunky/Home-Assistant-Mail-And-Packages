"""
Based on @skalavala work at
https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html

Configuration code contribution from @firstof9 https://github.com/firstof9/
"""

# import voluptuous as vol
import logging
import asyncio
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
    USPS_Mail_Email,
    USPS_Packages_Email,
    USPS_Mail_Subject,
    USPS_Delivering_Subject,
    USPS_Delivered_Subject,
    UPS_Email,
    UPS_Delivering_Subject,
    UPS_Delivered_Subject,
    FEDEX_Email,
    FEDEX_Delivering_Subject,
    FEDEX_Delivered_Subject,
    GIF_FILE_NAME,
    IMG_RESIZE_OPTIONS,
    GIF_MAKER_OPTIONS,
    VERSION,
    ISSUE_URL,
)

from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


@asyncio.coroutine
async def async_setup_entry(hass, entry, async_add_entities):

    _LOGGER.info('version %s is starting, if you have any issues please report'
                 ' them here: %s', VERSION, ISSUE_URL)

    config = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_USERNAME: entry.data[CONF_USERNAME],
        CONF_PASSWORD: entry.data[CONF_PASSWORD],
        CONF_PORT: entry.data[CONF_PORT],
        CONF_FOLDER: entry.data[CONF_FOLDER],
        CONF_PATH: entry.data[CONF_PATH]
    }

    async_add_entities([MailCheck(), USPS_Mail(hass, config),
                       USPS_Packages(hass, config),
                       USPS_Delivering(hass, config),
                       USPS_Delivered(hass, config),
                       UPS_Packages(hass, config),
                       UPS_Delivering(hass, config),
                       UPS_Delivered(hass, config),
                       FEDEX_Packages(hass, config),
                       FEDEX_Delivering(hass, config),
                       FEDEX_Delivered(hass, config),
                       Packages_Delivered(hass, config),
                       Packages_Transit(hass, config)])


class MailCheck(Entity):

    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""

        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail Updated'

    @property
    def state(self):
        """Return the state of the sensor."""

        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""

        return 'Time'

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

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._img_out_path = config.get(CONF_PATH)

        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail USPS Mail'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_mails(account, self._img_out_path)
        else:
            _LOGGER.debug("USPS Mail: Host was left blank not "
                          "attempting connection")


class USPS_Packages(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail USPS Packages'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, USPS_Packages_Email,
                                    USPS_Delivering_Subject)
            self._state += get_count(account, USPS_Packages_Email,
                                     USPS_Delivered_Subject)
        else:
            _LOGGER.debug("USPS Packages: Host was left blank not "
                          "attempting connection")


class USPS_Delivering(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail USPS Delivering'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, USPS_Packages_Email,
                                    USPS_Delivering_Subject)
        else:
            _LOGGER.debug("USPS Delivering: Host was left blank not "
                          "attempting connection")


class USPS_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail USPS Delivered'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, USPS_Packages_Email,
                                    USPS_Delivered_Subject)
        else:
            _LOGGER.debug("USPS Delivered: Host was left blank not "
                          "attempting connection")


class Packages_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Packages Delivered'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, USPS_Packages_Email,
                                    USPS_Delivered_Subject)
            self._state += get_count(account, UPS_Email, UPS_Delivered_Subject)
            self._state += get_count(account, FEDEX_Email,
                                     FEDEX_Delivered_Subject)
        else:
            _LOGGER.debug("Packages Transit: Host was left blank not "
                          "attempting connection")


class Packages_Transit(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Packages In Transit'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, USPS_Packages_Email,
                                    USPS_Delivering_Subject)
            self._state += get_count(account, UPS_Email,
                                     UPS_Delivering_Subject)
            self._state += get_count(account, FEDEX_Email,
                                     FEDEX_Delivering_Subject)
        else:
            _LOGGER.debug("Packages Transit: Host was left blank not "
                          "attempting connection")


class UPS_Packages(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'UPS Packages'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, UPS_Email, UPS_Delivering_Subject)
            self._state += get_count(account, UPS_Email, UPS_Delivered_Subject)
        else:
            _LOGGER.debug("UPS Packages: Host was left blank not "
                          "attempting connection")


class UPS_Delivering(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail UPS Delivering'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, UPS_Email, UPS_Delivering_Subject)
        else:
            _LOGGER.debug("UPS Delivering: Host was left blank not "
                          "attempting connection")


class UPS_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail UPS Delivered'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, UPS_Email, UPS_Delivered_Subject)
        else:
            _LOGGER.debug("UPS Delivered: Host was left blank not "
                          "attempting connection")


class FEDEX_Packages(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'FEDEX Packages'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, FEDEX_Email,
                                    FEDEX_Delivering_Subject)
            self._state += get_count(account, FEDEX_Email,
                                     FEDEX_Delivered_Subject)
        else:
            _LOGGER.debug("FEDEX Packages: Host was left blank not "
                          "attempting connection")


class FEDEX_Delivering(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail FEDEX Delivering'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, FEDEX_Email,
                                    FEDEX_Delivering_Subject)
        else:
            _LOGGER.debug("FEDEX Delivering: Host was left blank not "
                          "attempting connection")


class FEDEX_Delivered(Entity):

    """Representation of a Sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._host = config.get(CONF_HOST)
        self._port = config.get(CONF_PORT)
        self._folder = config.get(CONF_FOLDER)
        self._user = config.get(CONF_USERNAME)
        self._pwd = config.get(CONF_PASSWORD)
        self._state = 0
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return 'Mail FEDEX Delivered'

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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._host is not None:
            account = login(self._host, self._port, self._user, self._pwd)
            selectfolder(account, self._folder)
            self._state = get_count(account, FEDEX_Email,
                                    FEDEX_Delivered_Subject)
        else:
            _LOGGER.debug("FEDEX Delivered: Host was left blank not "
                          "attempting connection")

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

def get_mails(account, image_output_path):
    today = get_formatted_date()
    image_count = 0
    images = []
    msg = ''

    _LOGGER.debug("Attempting to find Informed Delivery mail")

    (rv, data) = account.search(None,
                                '(FROM "' + USPS_Mail_Email + '" SUBJECT "' +
                                USPS_Mail_Subject + '" ON "' + today + '")')

    # Get number of emails found
    messageIDsString = str(data[0], encoding='utf8')
    listOfSplitStrings = messageIDsString.split(" ")
    msg_count = len(listOfSplitStrings)

    if rv == 'OK':
        for num in data[0].split():
            (rv, data) = account.fetch(num, '(RFC822)')
            msg = email.message_from_string(data[0][1].decode('utf-8'))

            # walking through the email parts to find images
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue

                filepath = image_output_path + part.get_filename()
                fp = open(filepath, 'wb')
                fp.write(part.get_payload(decode=True))
                images.append(filepath)
                image_count = image_count + 1
                fp.close()

        # Remove duplicate images
        _LOGGER.debug("Removing duplicate images.")
        images = list(dict.fromkeys(images))

        # Create copy of image list for deleting temperary images
        imagesDelete = images

        # Look for mail pieces without images image
        html_text = str(msg)
        link_pattern = re.compile('image-no-mailpieces700.jpg')
        search = link_pattern.search(html_text)
        if search is not None:
            images.append(image_output_path + 'image-no-mailpieces700.jpg')
            image_count = image_count + 1
            _LOGGER.debug("Image found: " + image_output_path +
                          "image-no-mailpieces700.jpg.")

        # Remove USPS announcement images
        _LOGGER.debug("Removing USPS announcement images.")
        remove_terms = ['mailerProvidedImage', 'ra_0']
        images = [el for el in images if not any(ignore in el for ignore
                                                 in remove_terms)]
        image_count = len(images)

        if image_count > 0:
            all_images = ''

            # Combine images into GIF
            for image in images:
                # Convert to similar images sizes
                os.system(IMG_RESIZE_OPTIONS + image + ' ' + image)
                # Add images to a list for imagemagick
                all_images = all_images + image + ' '
            try:
                os.system(GIF_MAKER_OPTIONS + all_images
                          + image_output_path + GIF_FILE_NAME)
                _LOGGER.info("Mail image generated.")
            except Exception as err:
                _LOGGER.error("Error attempting to generate image: %s",
                              str(err))

        for image in imagesDelete:
            try:
                os.remove(image)
            except Exception as err:
                _LOGGER.error("Error attempting to remove image: %s", str(err))

    if image_count == 0:
        _LOGGER.info("No mail found.")
        try:
            os.remove(image_output_path + GIF_FILE_NAME)
        except Exception as err:
            _LOGGER.error("Error attempting to remove image: %s", str(err))

        try:
            copyfile(image_output_path + 'mail_none.gif',
                     image_output_path + GIF_FILE_NAME)
        except Exception as err:
            _LOGGER.error("Error attempting to copy image: %s", str(err))

    return image_count

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
