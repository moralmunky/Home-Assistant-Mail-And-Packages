DOMAIN = "mail_and_packages"
VERSION = "0.1.5"
ISSUE_URL = "http://github.com/moralmunky/Home-Assistant-Mail-And-Packages"

CONF_FOLDER = "folder"
CONF_PATH = "image_path"
CONF_DURATION = "gif_duration"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_IMAGE_SECURITY = "image_security"

DEFAULT_NAME = "Mail And Packages"
DEFAULT_PORT = '993'
DEFAULT_FOLDER = '"INBOX"'
DEFAULT_PATH = '/home/homeassistant/.homeassistant/images/mail_and_packages/'
DEFAULT_IMAGE_SECURITY = True
DATA_LOCAL_FILE = 'mail_today.gif'
CAMERA_NAME = "Mail USPS"

USPS_Mail_Email = 'USPSInformedDelivery@usps.gov'
USPS_Packages_Email = 'auto-reply@usps.com'
USPS_Mail_Subject = 'Informed Delivery Daily Digest'
USPS_Delivering_Subject = 'Expected Delivery on'
USPS_Delivered_Subject = 'Item Delivered'

UPS_Email = 'mcinfo@ups.com'
UPS_Delivering_Subject = 'UPS Update: Package Scheduled for Delivery Today'
UPS_Delivering_Subject_2 = 'UPS Update: Follow Your Delivery on a Live Map'
UPS_Delivered_Subject = 'Your UPS Package was delivered'

FEDEX_Email = 'TrackingUpdates@fedex.com'
FEDEX_Delivering_Subject = 'Delivery scheduled for today'
FEDEX_Delivering_Subject_2 = 'Your package is scheduled for delivery today'
FEDEX_Delivered_Subject = 'Your package has been delivered'

GIF_FILE_NAME = 'mail_today.gif'
GIF_DURATION = 5
SCAN_INTERVAL = 5
