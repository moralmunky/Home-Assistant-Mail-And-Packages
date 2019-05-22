"""
Based on @skalavala work at https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html
"""
# from homeassistant.components.sensor import PLATFORM_SCHEMA
# import voluptuous as vol
# import homeassistant.helpers.config_validation as cv
# from homeassistant.const import (
#     CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_FOLDER,
#     CONF_IMAGE_OUTPUT_PATH)
# 
# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#     vol.Required(CONF_HOST): cv.string,
#     vol.Required(CONF_PORT): cv.string,
#     vol.Required(CONF_USERNAME): cv.string,
#     vol.Required(CONF_PASSWORD): cv.string,
#     vol.Required(CONF_FOLDER): cv.string,
#     vol.Required(CONF_IMAGE_OUTPUT_PATH): cv.string,
# })

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import logging

import asyncio

import email
import datetime, imaplib, re, sys
from datetime import timedelta
import os
import time
import subprocess
from shutil import copyfile

_LOGGER = logging.getLogger(__name__)

from . import DOMAIN
#DOMAIN = 'mail_and_packages'

host = 'imap.mail.com'
port = 993
username = 'email@email.com'
password = 'password'
folder   = 'Inbox'
image_output_path = '/path/to/.homeassistant/www/mail_and_packages/'

# host = hass.data[DOMAIN]['host']
# port = hass.data[DOMAIN]['port']
# username = hass.data[DOMAIN]['username']
# password = hass.data[DOMAIN]['password']
# folder   = hass.data[DOMAIN]['folder']
# image_output_path = hass.data[DOMAIN]['image_output_path']

#USPS_Email = 'munkyhome@icloud.com'
USPS_Email = 'USPSInformedDelivery@usps.gov'
USPS_Mail_Subject = 'Informed Delivery Daily Digest'
USPS_Delivering_Subject = 'Expected Delivery on'
USPS_Delivered_Subject = 'Item Delivered'

#UPS_Email = 'munkyhome@icloud.com'
UPS_Email = 'mcinfo@ups.com'
UPS_Delivering_Subject = 'UPS Update: Package Scheduled for Delivery Today'
UPS_Delivered_Subject = 'Your UPS Package was delivered'

#FEDEX_Email = 'munkyhome@icloud.com'
FEDEX_Email = 'TrackingUpdates@fedex.com'
FEDEX_Delivering_Subject = 'Delivery scheduled for today'
FEDEX_Delivered_Subject = 'Your package has been delivered'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)
GIF_FILE_NAME = "mail_today.gif"
GIF_MAKER_OPTIONS = 'convert -delay 300 -loop 0 -coalesce -set dispose background '

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    # We only want this platform to be set up via discovery.
#     host = conf[CONF_HOST]
# 	port = conf[CONF_PORT]
# 	username = conf[CONF_USERNAME]
# 	password = conf[CONF_PASSWORD]
# 	folder = conf[CONF_FOLDER]
# 	image_output_path = conf[CONF_IMAGE_OUTPUT_PATH]
	
    if discovery_info is None:
      return
    add_devices([MailCheck(),USPS_Mail(),USPS_Delivering(),USPS_Delivered(),UPS_Delivering(),UPS_Delivered(),FEDEX_Delivering(),FEDEX_Delivered()])
    
#@asyncio.coroutine
#def async_setup(hass, config):
#     host = conf[CONF_HOST]
# 	port = conf[CONF_PORT]
# 	username = conf[CONF_USERNAME]
# 	password = conf[CONF_PASSWORD]
# 	folder = conf[CONF_FOLDER]
# 	image_output_path = conf[CONF_IMAGE_OUTPUT_PATH]
	
    # Return boolean to indicate that initialization was successful.
#    return True
    
 #   add_devices([MailCheck(),USPS_Mail(),USPS_Delivering(),USPS_Delivered(),UPS_Delivering(),UPS_Delivered(),FEDEX_Delivering(),FEDEX_Delivered()])
        
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
        return "Time"
        
    @Throttle(MIN_TIME_BETWEEN_UPDATES)    
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['Last_Check']
        self._state = update_time()
    
class USPS_Mail(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"
        
    @Throttle(MIN_TIME_BETWEEN_UPDATES) 
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        account = login()
        selectfolder(account, folder)
        self._state = get_mails(account)

class USPS_Delivering(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"
    
    @Throttle(MIN_TIME_BETWEEN_UPDATES) 
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['USPS_Delivering']
        account = login()
        selectfolder(account, folder)
        self._state = usps_delivering_count(account)

class USPS_Delivered(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['USPS_Delivered']
        account = login()
        selectfolder(account, folder)
        self._state = usps_delivered_count(account)

class UPS_Delivering(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['UPS_Delivering']
        account = login()
        selectfolder(account, folder)
        self._state = ups_delivering_count(account)

class UPS_Delivered(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['UPS_Delivered']
        account = login()
        selectfolder(account, folder)
        self._state = ups_delivering_count(account)

class FEDEX_Delivering(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['FEDEX_Delivering']
        account = login()
        selectfolder(account, folder)
        self._state = fedex_delivering_count(account)

class FEDEX_Delivered(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
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
        return "Items"

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
#         self._state = self.hass.data[DOMAIN]['FEDEX_Delivered']
        account = login()
        selectfolder(account, folder)
        self._state = fedex_delivered_count(account)


# Login Method
###############################################################################
def login():
    account = imaplib.IMAP4_SSL(host, port)

    try:
        rv, data = account.login(username, password)
    except imaplib.IMAP4.error:
        sys.exit(1)

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

# Creates GIF image based on the attachments in the inbox
###############################################################################
def get_mails(account):
    today = get_formatted_date()
    image_count = 0

    (rv, data) = account.search(None,
                                '(FROM "' + USPS_Email + '" SUBJECT "' + USPS_Mail_Subject + '" SINCE "'
                                 + today + '")')

    if rv == 'OK':
        for num in data[0].split():
            (rv, data) = account.fetch(num, '(RFC822)')
            msg = email.message_from_string(data[0][1].decode('utf-8'))
            images = []
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

            if image_count > 0:
                all_images = ''

                for image in images:
                    all_images = all_images + image + ' '

                os.system(GIF_MAKER_OPTIONS + all_images
                          + image_output_path + GIF_FILE_NAME)

                for image in images:
                    os.remove(image)
                image_count = image_count - 1

        if image_count == 0:
            os.remove(image_output_path + GIF_FILE_NAME)
            copyfile(image_output_path + 'mail_none.gif',
                     image_output_path + GIF_FILE_NAME)

        return image_count

# gets USPS delivering packages count
###############################################################################
def usps_delivering_count(account):
    count = 0 
    today = get_formatted_date()

    rv, data = account.search(None, 
              '(FROM "' + USPS_Email + '" SUBJECT "' + USPS_Delivering_Subject + '" SINCE "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())
        #use to test
        #count = 5

    return count

# gets USPS delivered packages count
###############################################################################
def usps_delivered_count(account):
    count = 0 
    today = get_formatted_date()

    rv, data = account.search(None, 
              '(FROM "' + USPS_Email + '" SUBJECT "' + USPS_Delivered_Subject + '" SINCE "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())
        #use to test
        #count = 5

    return count

# gets UPS delivering packages count
###############################################################################
def ups_delivering_count(account):
    count = 0 
    today = get_formatted_date()

    rv, data = account.search(None, 
              '(FROM "' + UPS_Email + '" SUBJECT "' + UPS_Delivering_Subject + '" SINCE "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())
        #use to test
        #count = 5

    return count

# gets UPS delivered packages count
###############################################################################
def ups_delivered_count(account):
    count = 0 
    today = get_formatted_date()

    rv, data = account.search(None, 
              '(FROM "' + UPS_Email + '" SUBJECT "' + UPS_Delivered_Subject + '" SINCE "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())
        #use to test
        #count = 5

    return count
    
# gets FedEx delivering package count
###############################################################################
def fedex_delivering_count(account):
    count = 0 
    today = get_formatted_date()

    rv, data = account.search(None, 
              '(FROM "' + FEDEX_Email + '" SUBJECT "' + FEDEX_Delivering_Subject + '" SINCE "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())
        #use to test
        #count = 4
        
    return count

# gets FedEx delivered package count
###############################################################################
def fedex_delivered_count(account):
    count = 0 
    today = get_formatted_date()

    rv, data = account.search(None, 
              '(FROM "' + FEDEX_Email + '" SUBJECT "' + FEDEX_Delivered_Subject + '" SINCE "' + today + '")')

    if rv == 'OK':
        count = len(data[0].split())
        #use to test
        #count = 4

    return count

# gets FedEx pickup count
###############################################################################
# def fedex_delivered_count(account):
#     count = 0 
#     today = get_formatted_date()
# 
#     rv, data = account.search(None, 
#               '(FROM "munkyhome@icloud.com" SUBJECT "Your package has been delivered" SINCE "' + 
#               today + '")')
# 
#     if rv == 'OK':
#         count = len(data[0].split())
#         #use to test
#         #count = 4
# 
#     return count
    
# gets update time
###############################################################################
def update_time():
    updated = datetime.datetime.now().strftime('%b-%d-%Y %I:%M %p')
    
    return updated
