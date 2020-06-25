DOMAIN = "mail_and_packages"
VERSION = "0.2.1-hotfix"
ISSUE_URL = "http://github.com/moralmunky/Home-Assistant-Mail-And-Packages"

# Configuration Properties
CONF_FOLDER = "folder"
CONF_PATH = "image_path"
CONF_DURATION = "gif_duration"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_IMAGE_SECURITY = "image_security"
CONF_GENERATE_MP4 = "generate_mp4"

# Defaults
DEFAULT_NAME = "Mail And Packages"
DEFAULT_PORT = "993"
DEFAULT_FOLDER = '"INBOX"'
DEFAULT_PATH = "/home/homeassistant/.homeassistant/images/mail_and_packages/"
DEFAULT_IMAGE_SECURITY = True
DEFAULT_GIF_DURATION = 5
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_GIF_FILE_NAME = "mail_today.gif"
DEFAULT_FFMPEG = False

# USPS
USPS_Mail_Email = "USPSInformedDelivery@usps.gov"
USPS_Mail_Subject = "Informed Delivery Daily Digest"
USPS_Packages_Email = "auto-reply@usps.com"
USPS_Delivering_Subject = "Expected Delivery on"
USPS_Delivered_Subject = "Item Delivered"
USPS_Body_Text = "out for delivery"

# UPS
UPS_Email = "mcinfo@ups.com"
UPS_Delivering_Subject = "UPS Update: Package Scheduled for Delivery Today"
UPS_Delivering_Subject_2 = "UPS Update: Follow Your Delivery on a Live Map"
UPS_Delivered_Subject = "Your UPS Package was delivered"

# FedEx
FEDEX_Email = "TrackingUpdates@fedex.com"
FEDEX_Delivering_Subject = "Delivery scheduled for today"
FEDEX_Delivering_Subject_2 = "Your package is scheduled for delivery today"
FEDEX_Delivered_Subject = "Your package has been delivered"

# Amazon
Amazon_Domains = "amazon.com,amazon.ca,amazon.co.uk,amazon.in"

# Canada Post
CAPost_Email = "donotreply@canadapost.postescanada.ca"
CAPost_Delivered_Subject = "Delivery Notification"
