DOMAIN = "mail_and_packages"
VERSION = "0.0.5"
ISSUE_URL = "http://github.com/moralmunky/Home-Assistant-Mail-And-Packages"

CONF_FOLDER = "folder"
CONF_PATH = "image_path"

DEFAULT_NAME = "Mail And Packages"
DEFAULT_PORT = '993'
DEFAULT_FOLDER = 'Inbox'
DEFAULT_PATH = '/home/homeassistant/.homeassistant/www/mail_and_packages/'
DATA_LOCAL_FILE = 'mail_today.gif'
CAMERA_NAME = "Mail USPS"

USPS_Mail_Email = 'USPSInformedDelivery@usps.gov'
USPS_Packages_Email = 'auto-reply@usps.com'
USPS_Mail_Subject = 'Informed Delivery Daily Digest'
USPS_Delivering_Subject = 'Expected Delivery on'
USPS_Delivered_Subject = 'Item Delivered'

UPS_Email = 'mcinfo@ups.com'
UPS_Delivering_Subject = 'UPS Update: Package Scheduled for Delivery Today'
UPS_Delivered_Subject = 'Your UPS Package was delivered'

FEDEX_Email = 'TrackingUpdates@fedex.com'
FEDEX_Delivering_Subject = 'Delivery scheduled for today'
FEDEX_Delivered_Subject = 'Your package has been delivered'

GIF_FILE_NAME = 'mail_today.gif'
IMG_RESIZE_OPTIONS = ('convert -resize 700x315 ')
GIF_MAKER_OPTIONS = ('convert -delay 300 -loop 0 -coalesce -fill white '
                     '-dispose Background ')
