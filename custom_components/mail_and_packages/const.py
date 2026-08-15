"""Constants for Mail and Packages."""

from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .entity import MailandPackagesBinarySensorEntityDescription

DOMAIN = "mail_and_packages"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.0-dev"  # Now updated by release workflow
ISSUE_URL = "http://github.com/moralmunky/Home-Assistant-Mail-And-Packages"
PLATFORM = "sensor"
PLATFORMS = ["binary_sensor", "camera", "sensor"]
DATA = "data"
COORDINATOR = "coordinator_mail"
OVERLAY = ["overlay.png", "vignette.png", "white.png"]
SERVICE_UPDATE_FILE_PATH = "update_file_path"
CAMERA = "cameras"
CONFIG_VER = 20

# Attributes
ATTR_AMAZON_IMAGE = "amazon_image"
ATTR_COUNT = "count"
ATTR_CODE = "code"
ATTR_GRID_IMAGE_NAME = "grid_image"
ATTR_ORDER = "order"
ATTR_TRACKING = "tracking"
ATTR_TRACKING_NUM = "tracking_#"
ATTR_IMAGE = "image"
ATTR_IMAGE_PATH = "image_path"
ATTR_SERVER = "server"
ATTR_IMAGE_NAME = "image_name"
ATTR_EMAIL = "email"
ATTR_SUBJECT = "subject"
ATTR_BODY = "body"
ATTR_BODY_COUNT = "body_count"
ATTR_PATTERN = "pattern"
ATTR_USPS_MAIL = "usps_mail"
ATTR_UPS_IMAGE = "ups_image"
ATTR_WALMART_IMAGE = "walmart_image"
ATTR_FEDEX_IMAGE = "fedex_image"
ATTR_GENERIC_IMAGE = "generic_image"
ATTR_USPS_IMAGE = "usps_image"
ATTR_POST_DE_IMAGE = "post_de_image"
ATTR_HOME_DEPOT_IMAGE = "home_depot_image"

# Configuration Properties
CONF_ALLOW_EXTERNAL = "allow_external"
CONF_CAMERA_NAME = "camera_name"
CONF_CUSTOM_IMG = "custom_img"
CONF_CUSTOM_IMG_FILE = "custom_img_file"
CONF_AMAZON_CUSTOM_IMG = "amazon_custom_img"
CONF_AMAZON_CUSTOM_IMG_FILE = "amazon_custom_img_file"
CONF_UPS_CUSTOM_IMG = "ups_custom_img"
CONF_UPS_CUSTOM_IMG_FILE = "ups_custom_img_file"
CONF_WALMART_CUSTOM_IMG = "walmart_custom_img"
CONF_WALMART_CUSTOM_IMG_FILE = "walmart_custom_img_file"
CONF_FEDEX_CUSTOM_IMG = "fedex_custom_img"
CONF_FEDEX_CUSTOM_IMG_FILE = "fedex_custom_img_file"
CONF_GENERIC_CUSTOM_IMG = "generic_custom_img"
CONF_GENERIC_CUSTOM_IMG_FILE = "generic_custom_img_file"
CONF_POST_DE_CUSTOM_IMG = "post_de_custom_img"
CONF_POST_DE_CUSTOM_IMG_FILE = "post_de_custom_img_file"
CONF_HOME_DEPOT_CUSTOM_IMG = "home_depot_custom_img"
CONF_HOME_DEPOT_CUSTOM_IMG_FILE = "home_depot_custom_img_file"
CONF_STORAGE = "storage"
CONF_FOLDER = "folder"
CONF_PATH = "image_path"
CONF_DURATION = "gif_duration"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_IMAGE_SECURITY = "image_security"
CONF_IMAP_TIMEOUT = "imap_timeout"
CONF_GENERATE_GRID = "generate_grid"
CONF_GENERATE_MP4 = "generate_mp4"
CONF_AMAZON_FWDS = "amazon_fwds"
CONF_AMAZON_DAYS = "amazon_days"
CONF_VERIFY_SSL = "verify_ssl"
CONF_IMAP_SECURITY = "imap_security"
CONF_AMAZON_DOMAIN = "amazon_domain"
CONF_ALLOW_FORWARDED_EMAILS = "allow_forwarded_emails"
CONF_FORWARDED_EMAILS = "forwarded_emails"
CONF_FORWARDING_HEADER = "forwarding_header"
CONF_CUSTOM_DAYS = "custom_days"
CONF_USPS_PLACEHOLDER = "usps_placeholder"

# Defaults
DEFAULT_CAMERA_NAME = "Mail USPS Camera"
DEFAULT_NAME = "Mail And Packages"
DEFAULT_PORT = "993"
DEFAULT_FOLDER = "INBOX"
DEFAULT_PATH = "custom_components/mail_and_packages/images/"
DEFAULT_IMAGE_SECURITY = True
DEFAULT_IMAP_TIMEOUT = 60
DEFAULT_GIF_DURATION = 5
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_CUSTOM_DAYS = 3
MAX_TRACKING_AGE_DAYS = 14
DEFAULT_GIF_FILE_NAME = "mail_today.gif"
DEFAULT_AMAZON_FWDS = "(none)"
DEFAULT_ALLOW_EXTERNAL = False
DEFAULT_CUSTOM_IMG = False
DEFAULT_CUSTOM_IMG_FILE = "custom_components/mail_and_packages/mail_none.gif"
DEFAULT_AMAZON_CUSTOM_IMG = False
DEFAULT_AMAZON_CUSTOM_IMG_FILE = (
    "custom_components/mail_and_packages/no_deliveries_amazon.jpg"
)
DEFAULT_UPS_CUSTOM_IMG = False
DEFAULT_UPS_CUSTOM_IMG_FILE = (
    "custom_components/mail_and_packages/no_deliveries_ups.jpg"
)
DEFAULT_WALMART_CUSTOM_IMG = False
DEFAULT_WALMART_CUSTOM_IMG_FILE = (
    "custom_components/mail_and_packages/no_deliveries_walmart.jpg"
)
DEFAULT_FEDEX_CUSTOM_IMG = False
DEFAULT_FEDEX_CUSTOM_IMG_FILE = (
    "custom_components/mail_and_packages/no_deliveries_fedex.jpg"
)
DEFAULT_GENERIC_CUSTOM_IMG = False
DEFAULT_GENERIC_CUSTOM_IMG_FILE = (
    "custom_components/mail_and_packages/no_deliveries_generic.jpg"
)
DEFAULT_POST_DE_CUSTOM_IMG = False
DEFAULT_POST_DE_CUSTOM_IMG_FILE = "custom_components/mail_and_packages/mail_none.gif"
DEFAULT_HOME_DEPOT_CUSTOM_IMG = False
DEFAULT_HOME_DEPOT_CUSTOM_IMG_FILE = (
    "custom_components/mail_and_packages/no_deliveries_generic.jpg"
)
DEFAULT_AMAZON_DAYS = 3
DEFAULT_AMAZON_DOMAIN = "amazon.com"
DEFAULT_STORAGE = "custom_components/mail_and_packages/images/"

DEFAULT_ALLOW_FORWARDED_EMAILS = False
DEFAULT_FORWARDED_EMAILS = "(none)"
DEFAULT_FORWARDING_HEADER = "(none)"
DEFAULT_USPS_PLACEHOLDER = True

# Amazon
AMAZON_DOMAINS = [
    "amazon.com",
    "amazon.ca",
    "amazon.co.uk",
    "amazon.in",
    "amazon.de",
    "amazon.it",
    "amazon.com.au",
    "amazon.pl",
    "amazon.es",
    "amazon.fr",
    "amazon.ae",
    "amazon.nl",
    "amazon.se",
]
AMAZON_DELIVERED_SUBJECT = [
    "Delivered: ",
    "Your Amazon order has arrived!",
    "Consegna effettuata:",
    "Dostarczono:",
    "Geliefert:",
    "Livré",
    "Livrés",
    "Livraison",
    "Entregado:",
    "Bezorgd:",
    "Zugestellt:",
]
AMAZON_SHIPMENT_TRACKING = [
    "auto-confirm",
    "shipment-tracking",
    "order-update",
    "conferma-spedizione",
    "confirmar-envio",
    "versandbestaetigung",
    "confirmation-commande",
    "verzending-volgen",
    "update-bestelling",
    "pickup-point",
]
AMAZON_DELIVERING_SUBJECT = [
    "Out for delivery:",
    "In Zustellung:",
    "En cours de livraison",
]
AMAZON_SHIPMENT_SUBJECT = [
    "Shipped:",
    "Enviado:",
    "Spedito:",
    "Versandt:",
    "Versendet:",
    "Expédié",
    *AMAZON_DELIVERING_SUBJECT,
]
AMAZON_ORDERED_SUBJECT = [
    "Ordered:",
    "Pedido efetuado:",
    "Commandé",
]
AMAZON_EMAIL = [
    "order-update@",
    "update-bestelling@",
    "versandbestaetigung@",
    "verzending-volgen@",
    "auto-bevestiging@",
]
AMAZON_PACKAGES = "amazon_packages"
AMAZON_ORDER = "amazon_order"
AMAZON_DELIVERED = "amazon_delivered"
AMAZON_DELIVERING = "amazon_delivering"
AMAZON_IMG_LIST = [
    "us-prod-temp.s3.amazonaws.com",
    "gb-prod-temp.s3.eu-west-1.amazonaws.com",
]
AMAZON_IMG_PATTERN = (
    "(https://)([\\w_-]+(?:(?:\\.[\\w_-]+)+))([\\w.,@?^=%&:/~+#-;]*[\\w@?^=%&/~+#-;])?"
)
AMAZON_HUB = "amazon_hub"
AMAZON_HUB_CODE = "amazon_hub_code"
AMAZON_HUB_EMAIL = [
    "thehub@amazon.com",
    "order-update@amazon.com",
    "amazonlockers@amazon.com",
    "versandbestaetigung@amazon.de",
]
AMAZON_HUB_SUBJECT = ["ready for pickup from Amazon Hub Locker"]
AMAZON_HUB_SUBJECT_SEARCH = "(a package to pick up)(.*)(\\d{6})"
AMAZON_HUB_BODY = "(Your pickup code is <b>)(\\d{6})"
AMAZON_TIME_PATTERN = [
    "will arrive:",
    "estimated delivery date is:",
    "guaranteed delivery date is:",
    "Arriving:",
    "Arriverà:",
    "arriving:",
    "Arriving ",
    "Dostawa:",
    "Entrega:",
    "A chegar:",
    "Arrivée :",
    "Livraison :",
    "Arrive aujourd'hui",
    "Chega ",
    "Verwachte bezorgdatum:",
    "Votre date de livraison prévue est :",
    "In arrivo",
    "Zustellung:",
    "Ankunft",
]
AMAZON_TIME_PATTERN_END = [
    "Previously expected:",
    "This contains",
    "Track your",
    "Per tracciare il tuo pacco",
    "View or manage order",
    "Acompanhar",
    "Seguimiento",
    "Verfolge deine(n) Artikel",
    "Lieferung verfolgen",
    "Ihr Paket verfolgen",
    "Suivre",
    "Volg je pakket",
    "Je pakket volgen",
]
AMAZON_TIME_PATTERN_REGEX = [
    "Arriving (\\w+ \\d+) - (\\w+ \\d+)",
    "Arriving (\\w+ \\d+)",
    "Arriving (\\w+ ?\\d*)",
    "Arriving (\\w+)",
    "Zustellung:? (heute)",
    "Zustellung:? (\\w+ \\d+) - (\\w+ \\d+)",
    "Zustellung:? (\\w+ \\d+)",
    "Zustellung:? (\\w+ ?\\d*)",
    "Zustellung:? (\\w+)",
    "Ankunft:? (\\w+ \\d+) - (\\w+ \\d+)",
    "Ankunft:? (\\w+ \\d+)",
    "Ankunft:? (\\w+ ?\\d*)",
    "Ankunft:? (\\w+)",
    "Arriverà (\\w+ \\d+) - (\\w+ \\d+)",
    "Arriverà (\\w+ \\d+)",
    "Arriverà (\\w+ \\d*)",
    "Arrivée\\s*:?\\s*(heute|aujourd'hui)",
    "Arrivée\\s*:?\\s*(?:le )?(\\d+ \\w+)",
    "Arrivée\\s*:?\\s*(?:le )?(\\w+ \\d+) - (\\w+ \\d+)",
    "Arrivée\\s*:?\\s*(?:le )?(\\w+ \\d+)",
    "Arrivée\\s*:?\\s*(?:le )?(\\w+ \\d*)",
    "Arrivée\\s*:?\\s*(?:le )?(\\w+)",
    "Livraison\\s*:?\\s*(heute|aujourd'hui)",
    "Livraison\\s*:?\\s*(?:le )?(\\d+ \\w+)",
    "Livraison\\s*:?\\s*(?:le )?(\\w+ \\d+) - (\\w+ \\d+)",
    "Livraison\\s*:?\\s*(?:le )?(\\w+ \\d+)",
    "Livraison\\s*:?\\s*(?:le )?(\\w+ \\d*)",
    "Livraison\\s*:?\\s*(?:le )?(\\w+)",
    "Chega ((\\w+(-\\w+)?))",
    "Wordt bezorgd op (\\w+ \\d+ \\w+)",
    "Wordt bezorgd op (\\w+ \\d+)",
    "Wordt (\\w+) bezorgd",
    "In arrivo (\\w+ \\d+) - (\\w+ \\d+)",
    "In arrivo (\\w+ \\d+)",
    "In arrivo (\\w+ \\d*)",
    "In arrivo (\\w+)",
]
AMAZON_EXCEPTION_SUBJECT = "Delivery update:"
AMAZON_EXCEPTION_BODY = "running late"
AMAZON_EXCEPTION = "amazon_exception"
AMAZON_EXCEPTION_ORDER = "amazon_exception_order"
AMAZON_PATTERN = "[0-9]{3}-[0-9]{7}-[0-9]{7}"
AMAZON_OTP = "amazon_otp"
AMAZON_OTP_CODE = "amazon_otp_code"
AMAZON_OTP_REGEX = "(\n)(\\d{6})(\n)"
AMAZON_OTP_SUBJECT = "A one-time password is required for your Amazon delivery"

AMAZON_DELIEVERED_BY_OTHERS_SEARCH_TEXT = ["AMAZON"]

# Sensor Data
SENSOR_DATA = {
    # USPS
    "usps_delivered": {
        "email": ["auto-reply@usps.com", "auto-reply@tracking.usps.com"],
        "subject": ["Item Delivered"],
    },
    "usps_delivering": {
        "email": ["auto-reply@usps.com", "auto-reply@tracking.usps.com"],
        "subject": ["Expected Delivery on", "Out for Delivery"],
        "body": ["Your item is out for delivery"],
    },
    "usps_exception": {
        "email": ["auto-reply@usps.com", "auto-reply@tracking.usps.com"],
        "subject": ["Delivery Exception"],
    },
    "usps_packages": {
        "email": ["auto-reply@usps.com", "auto-reply@tracking.usps.com"],
        "subject": ["Expected Delivery by"],
    },
    "usps_pickup": {
        "email": ["auto-reply@usps.com"],
        "subject": ["USPS - Your Package Pickup Request"],
        "body": ["Total Packages: (\\d+)"],
        "body_count": True,
    },
    "usps_tracking": {"pattern": ["9[2345]\\d{15,26}"]},
    "usps_mail": {
        "email": [
            "USPSInformedDelivery@usps.gov",
            "USPSInformeddelivery@email.informeddelivery.usps.com",
            "USPSInformeddelivery@informeddelivery.usps.com",
            "USPS Informed Delivery",
        ],
        "subject": ["Your Daily Digest"],
    },
    "usps_mail_delivered": {
        "email": [
            "USPSInformedDelivery@usps.gov",
            "USPSInformeddelivery@email.informeddelivery.usps.com",
            "USPSInformeddelivery@informeddelivery.usps.com",
            "USPS Informed Delivery",
        ],
        "subject": ["Your Mail Was Delivered"],
    },
    # UPS
    "ups_delivered": {
        "email": ["mcinfo@ups.com", "pkginfo@ups.com"],
        "subject": [
            "Your UPS Package was delivered",
            "Your UPS Packages were delivered",
            "Your UPS Parcel was delivered",
            "Your UPS Parcels were delivered",
            "Votre colis UPS a été livré",
            "Paket wurde zugestellt",
        ],
    },
    "ups_delivering": {
        "email": ["mcinfo@ups.com", "pkginfo@ups.com"],
        "subject": [
            "UPS Update: Package Scheduled for Delivery Today",
            "UPS Update: Follow Your Delivery on a Live Map",
            "UPS Pre-Arrival: Your Driver is Arriving Soon! Follow on a Live Map",
            "UPS Update: Parcel Scheduled for Delivery Today",
            "Mise à jour UPS : Livraison du colis prévue demain",
            "Mise à jour UPS : Livraison du colis prévue aujourd'hui",
        ],
    },
    "ups_exception": {
        "email": ["mcinfo@ups.com"],
        "subject": ["UPS Update: New Scheduled Delivery Date"],
    },
    "ups_packages": {
        "email": ["mcinfo@ups.com", "pkginfo@ups.com"],
        "subject": ["UPS Ship Notification"],
    },
    "ups_tracking": {"pattern": ["1Z?[0-9A-Z]{16}"]},
    # FedEx
    "fedex_delivered": {
        "email": [
            "TrackingUpdates@fedex.com",
            "fedexcanada@fedex.com",
            "noreply@fedex.com",
        ],
        "subject": [
            "Your package has been delivered",
            "Your packages have been delivered",
            "Your shipment was delivered",
        ],
    },
    "fedex_delivering": {
        "email": [
            "TrackingUpdates@fedex.com",
            "fedexcanada@fedex.com",
            "noreply@fedex.com",
        ],
        "subject": [
            "Delivery scheduled for today",
            "Your package is scheduled for delivery today",
            "Your package is now out for delivery",
            "Your shipment is out for delivery today",
            "out for delivery today",
            "Ihre Sendung wird voraussichtlich heute zugestellt",
        ],
    },
    "fedex_packages": {
        "email": [
            "TrackingUpdates@fedex.com",
            "fedexcanada@fedex.com",
            "noreply@fedex.com",
        ],
        "subject": ["Your shipment is on the way"],
    },
    "fedex_exception": {
        "email": [
            "TrackingUpdates@fedex.com",
            "fedexcanada@fedex.com",
            "noreply@fedex.com",
        ],
        # Subject confirmed against a real FedEx delivery-exception
        # notification (From: trackingupdates@fedex.com, Subject:
        # "FedEx Delivery Exception"). IMAP SUBJECT search is a
        # case-insensitive substring match, mirroring usps_exception's
        # "Delivery Exception" fragment.
        "subject": ["FedEx Delivery Exception"],
    },
    "fedex_tracking": {"pattern": ["\\d{12,20}"]},
    # Canada Post
    "capost_delivered": {
        "email": [
            "donotreply@canadapost.postescanada.ca",
            "donotreply-nepasrepondre@notifications.canadapost-postescanada.ca",
        ],
        "subject": [
            "Delivery Notification",
        ],
    },
    "capost_delivering": {
        "email": [
            "donotreply-nepasrepondre@notifications.canadapost-postescanada.ca",
        ],
        "subject": [
            "Your parcel is out for delivery",
        ],
    },
    "capost_packages": {},
    "capost_tracking": {"pattern": ["\\d{16}"]},
    "capost_mail": {
        "email": ["donotreply-nepasrepondre@communications.canadapost-postescanada.ca"],
        "subject": ["You have mail on the way"],
        "body": ["\\sYou have (\\d) piece|pieces of mail\\s"],
        "body_count": True,
    },
    # DHL
    "dhl_delivered": {
        "email": [
            "donotreply_odd@dhl.com",
            "NoReply.ODD@dhl.com",
            "noreply@dhl.de",
            "no-reply@dhl.de",
            "pl.no.reply@dhl.com",
            "support@dhl.com",
            "noreply@dhlecommerce.nl",
            "noreply@dhl.nl",
        ],
        "subject": [
            "DHL On Demand Delivery",
            "Powiadomienie o przesyłce",
            "wurde zugestellt",
            "DHL Shipment Notification",
            "liegt am gewünschten Ablageort",
            "Ihre Sendung liegt im Briefkasten",
            "Sendung liegt im Briefkasten",
            "Zustellung an Ablageort",
            "Ablageort",
            "Sendung zugestellt",
            "Paket wurde zugestellt",
            "Ihre AliExpress Sendung liegt im Briefkasten",
            "succesvol bezorgd",
            "is bezorgd",
        ],
        "body": [
            "has been delivered",
            "została doręczona",
            "ist angekommen",
            'Notification for shipment event group "Delivered',
            " - Delivered - ",
            "liegt im Briefkasten",
            "zugestellt",
            "Zustellung",
            "wurde zugestellt",
            "succesvol bezorgd",
            "is bezorgd",
            "pakket is afgeleverd",
        ],
    },
    "dhl_delivering": {
        "email": [
            "donotreply_odd@dhl.com",
            "NoReply.ODD@dhl.com",
            "noreply@dhl.de",
            "no-reply@dhl.de",
            "pl.no.reply@dhl.com",
            "support@dhl.com",
            "noreply@dhlecommerce.nl",
            "noreply@dhl.nl",
        ],
        "subject": [
            "DHL On Demand Delivery",
            "Paket kommt heute",
            "kommt heute",
            "wird gleich zugestellt",
            "Powiadomienie o przesyłce",
            "DHL Shipment Notification",
            "vanavond voor de deur",
            "vandaag voor de deur",
            "pakket onderweg",
            "bezorging vandaag",
            "staan vandaag voor de deur",
            "staan vanavond voor de deur",
            "komen we bij je langs",
        ],
        "body": [
            "scheduled for delivery TODAY",
            "zostanie dziś do Państwa doręczona",
            "wird Ihnen heute",
            "wird Ihnen voraussichtlich",
            "heute zwischen",
            " - Shipment is out with courier for delivery - ",
            "Shipment is scheduled for delivery",
            "voraussichtlich innerhalb",
            "staan vandaag voor de deur",
            "staan vanavond voor de deur",
            "wordt vandaag bezorgd",
            "bezorger onderweg",
            "komen we bij je langs",
        ],
    },
    # Transit-only DHL DE subjects (not out-for-delivery).
    # Do NOT match "Jetzt Live verfolgen" here — OFD subjects also contain it.
    "dhl_packages": {
        "email": [
            "donotreply_odd@dhl.com",
            "NoReply.ODD@dhl.com",
            "noreply@dhl.de",
            "no-reply@dhl.de",
            "pl.no.reply@dhl.com",
            "support@dhl.com",
            "noreply@dhlecommerce.nl",
            "noreply@dhl.nl",
        ],
        "subject": [
            "ist unterwegs",
        ],
    },
    "dhl_tracking": {
        "pattern": [
            "(?:JJD\\d{18}|JVGL\\d{20}|MDP[A-Z0-9]{5,15}|00\\d{18}|(?<![0-9])\\d{10,11}(?![0-9]))",
        ],
    },
    # Hermes.co.uk
    "hermes_delivered": {
        "email": [
            "donotreply@myhermes.co.uk",
            "noreply@paketankuendigung.myhermes.de",
        ],
        "subject": [
            "Hermes has successfully delivered your",
            "wurde an deinen WunschAblageort zugestellt",
            "wurde zugestellt",
        ],
    },
    "hermes_delivering": {
        "email": [
            "donotreply@myhermes.co.uk",
            "noreply@paketankuendigung.myhermes.de",
        ],
        "subject": [
            "parcel is now with your local Hermes courier",
            "Ihre Hermes Sendung",
            "Deine Hermes Sendung",
            "Deine Sendung kommt heute",
        ],
        "body": [
            "Voraussichtliche Zustellung",
            "ist unterwegs",
        ],
    },
    "hermes_packages": {},
    "hermes_tracking": {"pattern": ["\\d{11,20}"]},
    # Royal Mail
    "royal_delivered": {
        "email": ["no-reply@royalmail.com"],
        "subject": ["has been delivered"],
    },
    "royal_delivering": {
        "email": ["no-reply@royalmail.com"],
        "subject": ["is on its way", "to be delivered today"],
    },
    "royal_packages": {},
    "royal_tracking": {"pattern": ["[A-Za-z]{2}[0-9]{9}GB"]},
    # Poczta Polska SA
    "poczta_polska_delivered": {},
    "poczta_polska_delivering": {
        "email": ["informacja@poczta-polska.pl", "powiadomienia@allegromail.pl"],
        "subject": ["Poczta Polska S.A. eINFO"],
    },
    "poczta_polska_packages": {},
    "poczta_polska_tracking": {
        # http://emonitoring.poczta-polska.pl/?numer=00359007738913296666
        "pattern": ["\\d{20}"],
    },
    # InPost.pl
    "inpost_pl_delivered": {
        "email": [
            "powiadomienia@inpost.pl",
            "info@paczkomaty.pl",
            "powiadomienia@allegromail.pl",
        ],
        "subject": [
            "InPost - Potwierdzenie odbioru",
            "InPost - Paczka umieszczona w Paczkomacie",
        ],
    },
    "inpost_pl_delivering": {
        "email": [
            "powiadomienia@inpost.pl",
            "info@paczkomaty.pl",
            "powiadomienia@allegromail.pl",
        ],
        "subject": [
            "Kurier InPost: Twoja paczka jest w drodze",
            "prawie u Ciebie",
        ],
    },
    "inpost_pl_packages": {},
    "inpost_pl_tracking": {
        # https://inpost.pl/sledzenie-przesylek?number=520113017830399002575123
        "pattern": ["\\d{24}"],
    },
    # DPD Poland
    "dpd_com_pl_delivered": {
        "email": [
            "KurierDPD0@dpd.com.pl",
            "KurierDPD1@dpd.com.pl",
            "KurierDPD2@dpd.com.pl",
            "KurierDPD3@dpd.com.pl",
            "KurierDPD4@dpd.com.pl",
            "KurierDPD5@dpd.com.pl",
            "KurierDPD6@dpd.com.pl",
            "KurierDPD7@dpd.com.pl",
            "KurierDPD8@dpd.com.pl",
            "KurierDPD9@dpd.com.pl",
            "KurierDPD10@dpd.com.pl",
            "powiadomienia@allegromail.pl",
        ],
        "subject": ["została doręczona"],
    },
    "dpd_com_pl_delivering": {
        "email": [
            "KurierDPD0@dpd.com.pl",
            "KurierDPD1@dpd.com.pl",
            "KurierDPD2@dpd.com.pl",
            "KurierDPD3@dpd.com.pl",
            "KurierDPD4@dpd.com.pl",
            "KurierDPD5@dpd.com.pl",
            "KurierDPD6@dpd.com.pl",
            "KurierDPD7@dpd.com.pl",
            "KurierDPD8@dpd.com.pl",
            "KurierDPD9@dpd.com.pl",
            "KurierDPD10@dpd.com.pl",
            "powiadomienia@allegromail.pl",
        ],
        "subject": [
            "Bezpieczne doręczenie",
            "przesyłka została nadana",
        ],
        "body": ["Dziś doręczamy", "DPD Polska"],
    },
    "dpd_com_pl_packages": {},
    "dpd_com_pl_tracking": {
        # https://tracktrace.dpd.com.pl/parcelDetails?p1=13490015284111
        "pattern": [
            "\\d{13}[A-Z0-9]{1,2}",
        ],
    },
    # DPD
    "dpd_delivered": {
        "email": [
            "noreply@service.dpd.de",
        ],
        "subject": [
            "Ihr Paket ist da!",
            "Die Abstellung Ihres DPD Pakets ist erfolgt",
        ],
    },
    "dpd_delivering": {
        "email": [
            "noreply@service.dpd.de",
        ],
        "subject": [
            "Bald ist ihr DPD Paket da",
            "kommt Ihr DPD Paket",
        ],
        "body": [
            "Paketnummer",
        ],
    },
    "dpd_packages": {},
    "dpd_tracking": {
        # https://tracktrace.dpd.com.pl/parcelDetails?p1=13490015284111
        "pattern": [
            "\\d{11,20}",
        ],
    },
    # GLS
    "gls_delivered": {
        "email": [
            "noreply@gls-group.eu",
            "powiadomienia@allegromail.pl",
            "no-reply@gls-pakete.de",
            "noreply@gls-group.nl",
            "noreply@gls.nl",
            "pakke-shop@pakkeshop.dk",
        ],
        "subject": [
            "informacja o dostawie",
            "wurde durch GLS",
            "bezorgd",
            "afgeleverd",
            "Du kan nu hente pakke",
        ],
        "body": [
            "została dzisiaj dostarczona",
            "Adresse erfolgreich zugestellt",
            "Am Wunschort abgestellt",
            "is bezorgd",
            "succesvol afgeleverd",
        ],
    },
    "gls_delivering": {
        "email": [
            "noreply@gls-group.eu",
            "powiadomienia@allegromail.pl",
            "no-reply@gls-pakete.de",
            "noreply@gls-group.nl",
            "noreply@gls.nl",
            "noreply@gls-denmark.com",
        ],
        "subject": [
            "paczka w drodze",
            "ist unterwegs",
            "kommt heute",
            "pakket onderweg",
            "bezorging vandaag",
            "GLS pakke",
        ],
        "body": [
            "Zespół GLS",
            "GLS-Team",
            "fast da",
            "wordt vandaag bezorgd",
            "Uw pakket wordt vandaag",
        ],
    },
    "gls_packages": {},
    "gls_tracking": {
        # https://gls-group.eu/GROUP/en/parcel-tracking?match=51687952111
        # https://gls-rtt.com/#/DE/de/95368751054
        "pattern": ["\\d{11,12}"],
    },
    # Australia Post
    "auspost_delivered": {
        "email": ["noreply@notifications.auspost.com.au"],
        "subject": ["Your shipment has been delivered"],
    },
    "auspost_delivering": {
        "email": ["noreply@notifications.auspost.com.au"],
        "subject": ["is on its way", "is coming today"],
    },
    "auspost_packages": {},
    "auspost_tracking": {"pattern": ["\\d{7,10,12}|[A-Za-z]{2}[0-9]{9}AU "]},
    # Evri
    "evri_delivered": {
        "email": ["do-not-reply@evri.com"],
        "subject": ["successfully delivered"],
    },
    "evri_delivering": {
        "email": ["do-not-reply@evri.com"],
        "subject": ["is now with your local Evri courier for delivery"],
    },
    "evri_packages": {},
    "evri_tracking": {"pattern": ["H[0-9A-Z]{15}"]},
    # DHL Parcel NL
    "dhl_parcel_nl_delivered": {
        "email": ["noreply@dhlparcel.nl"],
        "subject": ["Je pakket is bezorgd"],
    },
    "dhl_parcel_nl_delivering": {
        "email": ["noreply@dhlparcel.nl"],
        "subject": ["We staan vandaag", "We staan vanavond"],
    },
    "dhl_parcel_nl_packages": {},
    "dhl_parcel_nl_tracking": {"pattern": ["[0-9A-Z]{12,24}"]},
    # Bonshaw Distribution Network
    "bonshaw_distribution_network_delivered": {
        "email": ["parcel_tracking@bonshawdelivery.com"],
        "subject": ["Parcel Delivered! Commande Livrée!"],
    },
    "bonshaw_distribution_network_delivering": {
        "email": ["parcel_tracking@bonshawdelivery.com"],
        "subject": ["Parcel Out for Delivery! En attente de livraison!"],
    },
    "bonshaw_distribution_network_packages": {
        "email": ["parcel_tracking@bonshawdelivery.com"],
        "subject": ["Your package has been received!"],
    },
    "bonshaw_distribution_network_tracking": {"pattern": ["BNI[0-9]{9}"]},
    # Purolator
    "purolator_delivered": {
        "email": ["NotificationService@purolator.com"],
        "subject": [
            "Purolator - Your shipment is delivered",
            # 2026 format: "Purolator shipment <PIN>: Your package has been
            # delivered /Envoi de Purolator <PIN> : Votre colis a été livré"
            "Your package has been delivered",
        ],
    },
    "purolator_delivering": {
        "email": ["NotificationService@purolator.com"],
        "subject": [
            "Purolator - Your shipment is out for delivery",
            "Purolator - Your shipment is on its way",
            # 2026 format: "Purolator shipment <PIN>: Your package is now out
            # for delivery/ Envoi de Purolator <PIN> : Votre colis est en
            # cours de livraison"
            "Your package is now out for delivery",
        ],
    },
    "purolator_packages": {
        "email": ["NotificationService@purolator.com"],
        "subject": ["Purolator - Your shipment has been picked up"],
    },
    "purolator_tracking": {"pattern": ["(?:[A-Z]{3}\\d{9}|\\d{12,15})"]},
    # Intelcom
    "intelcom_delivered": {
        "email": [
            "notifications@intelcom.ca",
            "notifications@dragonflyshipping.ca",
            "notifications@dragonflyshipping.com",
            "notifications@nl.dragonflyinternational.com",
            "notifications@ca.dragonflyinternational.com",
        ],
        "subject": [
            "Your order has been delivered!",
            "Your package has been delivered",
            "Hooray! Your package is here",
            "Votre commande a été livrée!",
            "Votre colis a été livré!",
            "We hebben je pakket bezorgd!",
            "Hooray! Your package was delivered!",
        ],
    },
    "intelcom_delivering": {
        "email": [
            "notifications@intelcom.ca",
            "notifications@dragonflyshipping.ca",
            "notifications@dragonflyshipping.com",
            "notifications@nl.dragonflyinternational.com",
            "notifications@ca.dragonflyinternational.com",
        ],
        "subject": [
            "Your package is on the way!",
            "Your package is on its way",
            "Votre colis est en chemin!",
            "package is on its way",
            "Vandaag bezorgen we je pakket",
            "Your delivery is scheduled for today",
            "Your package will be there in the next hour!",
        ],
    },
    "intelcom_packages": {
        "email": [
            "notifications@intelcom.ca",
            "notifications@dragonflyshipping.ca",
            "notifications@dragonflyshipping.com",
            "notifications@nl.dragonflyinternational.com",
            "notifications@ca.dragonflyinternational.com",
        ],
        "subject": [
            "Your package has been received!",
            "We've received your package",
            "We've received your",
            "Je pakket is bij ons aangekomen",
        ],
    },
    "intelcom_tracking": {
        "pattern": ["(NSPRSO[0-9]{10}|AMZNL[0-9]{12}|INTLCMI[0-9]+)"]
    },
    # Etsy
    "etsy_delivered": {
        "email": [
            "no-reply@account.etsy.com",
            "noreply@account.etsy.com",
            "noreply@etsy.com",
        ],
        "subject": [
            # "It's here! Your order from <Shop> has been delivered."
            "has been delivered",
        ],
    },
    "etsy_delivering": {
        "email": [
            "no-reply@account.etsy.com",
            "noreply@account.etsy.com",
            "noreply@etsy.com",
            "email@email.etsy.com",
        ],
        "subject": [
            # "[Another package for] Your Etsy order is on the way (Receipt #N)"
            "your Etsy order is on the way",
            "Etsy Order dispatched",
            # "And it's off! <Carrier> has your order"
            "has your order",
            # App-nag template used for dispatch notices
            "Order updates are waiting in the app",
        ],
    },
    "etsy_packages": {},
    "etsy_tracking": {"pattern": ["(?:Receipt|Order)\\s*#(\\d{9,11})"]},
    # Walmart
    "walmart_delivering": {
        "email": ["help@walmart.com"],
        "subject": [
            "Out for delivery",
            "Your package should arrive by",
            "Your delivery should arrive by",
        ],
    },
    "walmart_delivered": {
        "email": ["help@walmart.com"],
        "subject": [
            "Your order was delivered",
            "Some of your items were delivered",
            "Delivered:",
            "Arrived:",
        ],
    },
    "walmart_packages": {
        "email": ["help@walmart.com"],
        "subject": ["Thanks for your delivery order"],
    },
    "walmart_exception": {
        "email": ["help@walmart.com"],
        "subject": ["delivery is delayed"],
    },
    "walmart_tracking": {"pattern": [r"\b#?[0-9]{7}-[0-9]{7,8}\b"]},
    # Home Depot
    "home_depot_delivering": {
        "email": ["homedepot@order.homedepot.com", "order.homedepot.com"],
        "subject": [
            "out for delivery",
            "arrives today",
        ],
    },
    "home_depot_delivered": {
        "email": ["homedepot@order.homedepot.com", "order.homedepot.com"],
        "subject": [
            "delivered",
            "has arrived",
        ],
    },
    "home_depot_packages": {
        "email": ["homedepot@order.homedepot.com", "order.homedepot.com"],
        "subject": [
            "Shipped:",
            "order shipped!",
            "on its way",
        ],
    },
    "home_depot_exception": {
        "email": ["homedepot@order.homedepot.com", "order.homedepot.com"],
        "subject": [
            "delayed",
            "delay",
        ],
    },
    "home_depot_tracking": {"pattern": [r"\bWK\d{8}\b"]},
    # Shopify (standard order-notification templates). Sender varies per
    # store; these cover Shopify's shared sending infrastructure. Stores
    # sending from their own domain need their sender added here.
    "shopify_delivered": {
        "email": [
            "t.shopifyemail.com",
            "no-reply@parcelpanel.net",
        ],
        "subject": ["has been delivered"],
    },
    "shopify_delivering": {
        "email": [
            "t.shopifyemail.com",
            "no-reply@parcelpanel.net",
        ],
        "subject": ["is out for delivery"],
    },
    "shopify_packages": {
        "email": [
            "t.shopifyemail.com",
            "no-reply@parcelpanel.net",
        ],
        "subject": ["is on the way"],
    },
    "shopify_tracking": {
        "pattern": ["shipment from order #?([A-Za-z0-9()\\-]+)"],
    },
    # BuildingLink
    "buildinglink_delivered": {
        "email": ["notify@buildinglink.com"],
        "subject": [
            "Your Amazon order has arrived",
            "delivery has arrived",
            "You have a package delivery",
            "You have a delivery at the front desk",
            "You have a DHL delivery",
            "You have an envelope",
        ],
    },
    "buildinglink_tracking": {},
    # Post NL
    "post_nl_delivering": {
        "email": [
            "noreply@notificatie.postnl.nl",
            "noreply@postnl.nl",
            "info@postnl.nl",
            "noreply@mypostnl.nl",
            "noreply@post.nl",
        ],
        "subject": [
            "Je pakket is onderweg",
            "De chauffer is onderweg",
            "onderweg",
            "wordt bezorgd",
            "bezorging vandaag",
            "verwacht tussen",
            "bezorger onderweg",
            "vandaag bezorgd",
        ],
        "body": [
            "onderweg naar",
            "wordt vandaag bezorgd",
            "verwacht tussen",
            "bezorger onderweg",
        ],
    },
    "post_nl_exception": {
        "email": ["noreply@notificatie.postnl.nl"],
        "subject": ["We hebben je gemist"],
    },
    "post_nl_delivered": {
        "email": [
            "noreply@notificatie.postnl.nl",
            "noreply@postnl.nl",
            "info@postnl.nl",
            "noreply@mypostnl.nl",
            "noreply@post.nl",
        ],
        "subject": [
            "Je pakket is bezorgd",
            "afgeleverd",
            "is bezorgd",
            "pakket bezorgd",
            "delivered",
            "succesvol bezorgd",
        ],
    },
    "post_nl_packages": {},
    "post_nl_tracking": {"pattern": ["3S[A-Z0-9]{10,18}"]},
    # Post DE
    "post_de_delivering": {},
    "post_de_delivered": {},
    "post_de_packages": {},
    "post_de_tracking": {},
    "post_de_mail": {
        "email": [
            "ankuendigung@brief.deutschepost.de",
        ],
        "subject": [
            "Ein Brief kommt in Kürze bei Ihnen an",
            "Ein Brief ist unterwegs zu Ihnen",
        ],
    },
    # Post Austria
    "post_at_delivering": {
        "email": ["MeineSendung@post.at"],
        "subject": ["Sendung ist in Zustellung"],
    },
    "post_at_exception": {},
    "post_at_delivered": {
        "email": ["MeineSendung@post.at"],
        "subject": ["Ihre Sendung wurde Zugestellt"],
    },
    "post_at_packages": {},
    "post_at_tracking": {"pattern": ["[0-9]{22}"]},
    # Rewe Lieferservice
    "rewe_lieferservice_delivering": {
        "email": ["reweshop@mailing.rewe.de"],
        "subject": ["Lieferschein zu deiner Bestellung beim REWE Lieferservice"],
        "body": ["Deine Lieferinformationen"],
    },
    "rewe_lieferservice_exception": {},
    "rewe_lieferservice_delivered": {
        "email": ["reweshop@mailing.rewe.de"],
        "subject": ["Deine Rechnung zu"],
        "body": ["Im Anhang dieser E-Mail kommt"],
    },
    # AliExpress
    "aliexpress_delivered": {
        "email": [
            "promotion@aliexpress.com",
            "transaction@notice.aliexpress.com",
            "chocieservice@aliexpress.com",
            "aebuyersservices@aliexpress.com",
        ],
        "subject": [
            "Package delivered",
            "Your package has been delivered",
            # 2026 format: "Package <ID> has been delivered"
            "has been delivered",
            "Sendung zugestellt",
        ],
        "body": [
            "delivered",
            "zugestellt",
        ],
    },
    "aliexpress_delivering": {
        "email": [
            "promotion@aliexpress.com",
            "transaction@notice.aliexpress.com",
            "chocieservice@aliexpress.com",
            "aebuyersservices@aliexpress.com",
        ],
        "subject": [
            "Package is on the way",
            "Your package is on the way",
            "Ihre Sendung ist unterwegs",
            "Sendung wird versandt",
            # 2026 formats: "Order <N>: <status>" and "Package <ID>: <status>"
            "order shipped",
            "collected by the carrier",
            "left the departure region",
            "at customs",
            "has cleared customs",
            "in your country/region",
            "in local transit",
            "with local carrier",
            "out for delivery",
        ],
        "body": [
            "on the way",
            "unterwegs",
            "wird versandt",
            "shipped",
            "carrier",
            "customs",
            "transit",
            "departure",
            "out for delivery",
        ],
    },
    "aliexpress_packages": {},
    "aliexpress_tracking": {
        "pattern": [
            "(?:[A-Z]{2}[0-9][0-9A-Z]{13,15}|[A-Z]{2}[0-9]{9}[A-Z]{2}|[0-9]{13}|[0-9]{20})"
        ],
    },
    # DPD Netherlands
    "dpd_nl_delivered": {
        "email": [
            "noreply@dpd.nl",
            "noreply@dpd.com",
            "noreply@dpdgroup.nl",
        ],
        "subject": ["bezorgd", "afgeleverd", "delivered"],
    },
    "dpd_nl_delivering": {
        "email": [
            "noreply@dpd.nl",
            "noreply@dpd.com",
            "noreply@dpdgroup.nl",
        ],
        "subject": [
            "pakket onderweg",
            "bezorging vandaag",
            "wordt vandaag bezorgd",
            "onderweg naar jou",
        ],
        "body": [
            "bezorger onderweg",
            "wordt vandaag bezorgd",
            "onze bezorger komt",
        ],
    },
    "dpd_nl_packages": {},
    "dpd_nl_tracking": {"pattern": ["\\d{14}"]},
    # bol.com (Netherlands)
    "bolcom_delivered": {
        "email": [
            "noreply@bol.com",
            "service@bol.com",
            "automail@bol.com",
        ],
        "subject": ["bezorgd", "afgeleverd", "delivered"],
    },
    "bolcom_delivering": {
        "email": [
            "noreply@bol.com",
            "service@bol.com",
            "automail@bol.com",
        ],
        "subject": [
            "verzonden",
            "onderweg",
            "wordt bezorgd",
            "meegegeven met",
            "bij PostNL",
            "bij DHL",
        ],
        "body": [
            "nu bij PostNL",
            "nu bij DHL",
            "meegegeven met",
            "bezorger onderweg",
        ],
    },
    "bolcom_packages": {},
    "bolcom_tracking": {"pattern": ["3S[A-Z0-9]{10,18}", "JJD\\d{14,25}", "\\d{14}"]},
    # PostNord (Sweden/Denmark)
    "postnord_delivered": {
        "email": [
            "no-reply@postnord.com",
            "avisering@postnord.se",
        ],
        "subject": [
            "finns att hämta",
            "finns att hamta",
            "har levererats",
            "Levererad",
            "klar til afhentning",
        ],
    },
    "postnord_delivering": {
        "email": [
            "no-reply@postnord.com",
            "avisering@postnord.se",
        ],
        "subject": [
            "Leverans på väg",
            "Leverans pa vag",
            "är på väg",
            "ar pa vag",
            "på väg till dig",
            "pa vag till dig",
            "Der er nyt om din PostNord-pakke",
        ],
    },
    "postnord_packages": {},
    "postnord_tracking": {
        "pattern": ["[0-9]{13,18}SE", "SE[0-9]{9}SE", "[0-9]{13,18}DK"]
    },
    # Bring (Sweden/Norway/Denmark)
    "bring_delivered": {
        "email": [
            "no-reply@bring.com",
            "notification@bring.com",
            "noreply@bring.com",
        ],
        "subject": [
            "paket att hämta",
            "paket att hamta",
            "har levererats",
            "Nu kan du hente din pakke fra",
        ],
    },
    "bring_delivering": {
        "email": [
            "no-reply@bring.com",
            "notification@bring.com",
            "noreply@bring.com",
        ],
        "subject": [
            "sändning är på väg",
            "sandning ar pa vag",
            "sändning har skickats",
            "sandning har skickats",
            "Paket på väg",
            "Paket pa vag",
            "er på vej",
        ],
    },
    "bring_packages": {},
    "bring_tracking": {"pattern": ["PARCEL[0-9A-Z]{10,20}", "CT[0-9]{9}NO"]},
    # DAO (Denmark)
    "dao_delivered": {
        "email": ["no-reply@dao.as"],
        "subject": ["Nu kan du hente din pakke fra"],
    },
    "dao_delivering": {
        "body": ["Forsendelsen sendes med: DAO-DK-DIREKTE"],
    },
    "dao_packages": {},
    "dao_tracking": {},
    # Budbee
    "budbee_delivering": {
        "email": ["no-reply@budbee.com"],
        "subject": ["er nu registreret hos Budbee"],
    },
    "budbee_delivered": {},
    "budbee_packages": {},
    "budbee_tracking": {},
    # Airmee
    "airmee_delivered": {
        "email": ["no-reply@airmee.com"],
        "subject": ["Airmee har leveret din pakke"],
    },
    "airmee_delivering": {
        "email": ["no-reply@airmee.com"],
        "subject": ["Levering booket av Amazon med Airmee"],
    },
    "airmee_packages": {},
    "airmee_tracking": {},
    # Burd Delivery
    "burd_delivered": {
        "email": ["support@burd.dk"],
        "subject": ["Din pakke er leveret"],
    },
    "burd_delivering": {
        "email": ["support@burd.dk"],
        "subject": ["Din pakke fra"],
    },
    "burd_packages": {},
    "burd_tracking": {},
    # DB Schenker (Sweden)
    "db_schenker_delivered": {
        "email": [
            "no-reply@dbschenker.com",
            "no-reply@dsv.com",
        ],
        "subject": [
            "finns nu att hämta",
            "finns nu att hamta",
            "har levererats",
        ],
    },
    "db_schenker_delivering": {
        "email": [
            "no-reply@dbschenker.com",
            "no-reply@dsv.com",
        ],
        "subject": [
            "Avisering om paket",
            "Leveransbesked",
            "är på väg",
            "ar pa vag",
        ],
    },
    "db_schenker_packages": {},
    "db_schenker_tracking": {"pattern": ["\\d{10,16}"]},
}

# Sensor definitions
SENSOR_TYPES: Final[dict[str, SensorEntityDescription]] = {
    "mail_updated": SensorEntityDescription(
        name="Mail Updated",
        icon="mdi:update",
        key="mail_updated",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    # USPS
    "usps_mail": SensorEntityDescription(
        name="Mail USPS Mail",
        native_unit_of_measurement="piece(s)",
        icon="mdi:mailbox-up",
        key="usps_mail",
    ),
    "usps_delivered": SensorEntityDescription(
        name="Mail USPS Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="usps_delivered",
    ),
    "usps_delivering": SensorEntityDescription(
        name="Mail USPS Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="usps_delivering",
    ),
    "usps_exception": SensorEntityDescription(
        name="Mail USPS Exception",
        native_unit_of_measurement="package(s)",
        icon="mdi:archive-alert",
        key="usps_exception",
    ),
    "usps_packages": SensorEntityDescription(
        name="Mail USPS Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="usps_packages",
    ),
    "usps_pickup": SensorEntityDescription(
        name="Mail USPS Scheduled Pickup",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-up",
        key="usps_pickup",
    ),
    # UPS
    "ups_delivered": SensorEntityDescription(
        name="Mail UPS Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="ups_delivered",
    ),
    "ups_delivering": SensorEntityDescription(
        name="Mail UPS Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="ups_delivering",
    ),
    "ups_exception": SensorEntityDescription(
        name="Mail UPS Exception",
        native_unit_of_measurement="package(s)",
        icon="mdi:archive-alert",
        key="ups_exception",
    ),
    "ups_packages": SensorEntityDescription(
        name="Mail UPS Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="ups_packages",
    ),
    # FedEx
    "fedex_delivered": SensorEntityDescription(
        name="Mail FedEx Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="fedex_delivered",
    ),
    "fedex_delivering": SensorEntityDescription(
        name="Mail FedEx Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="fedex_delivering",
    ),
    "fedex_packages": SensorEntityDescription(
        name="Mail FedEx Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="fedex_packages",
    ),
    "fedex_exception": SensorEntityDescription(
        name="Mail FedEx Exception",
        native_unit_of_measurement="package(s)",
        icon="mdi:archive-alert",
        key="fedex_exception",
    ),
    # Amazon
    "amazon_packages": SensorEntityDescription(
        name="Mail Amazon Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package",
        key="amazon_packages",
    ),
    "amazon_delivering": SensorEntityDescription(
        name="Mail Amazon Packages Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="amazon_delivering",
    ),
    "amazon_delivered": SensorEntityDescription(
        name="Mail Amazon Packages Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="amazon_delivered",
    ),
    "amazon_exception": SensorEntityDescription(
        name="Mail Amazon Exception",
        native_unit_of_measurement="package(s)",
        icon="mdi:archive-alert",
        key="amazon_exception",
    ),
    "amazon_hub": SensorEntityDescription(
        name="Mail Amazon Hub Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package",
        key="amazon_hub",
    ),
    "amazon_otp": SensorEntityDescription(
        name="Mail Amazon OTP Code",
        icon="mdi:counter",
        key="amazon_otp",
    ),
    # AliExpress
    "aliexpress_delivered": SensorEntityDescription(
        name="Mail AliExpress Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="aliexpress_delivered",
    ),
    "aliexpress_delivering": SensorEntityDescription(
        name="Mail AliExpress Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="aliexpress_delivering",
    ),
    "aliexpress_packages": SensorEntityDescription(
        name="Mail AliExpress Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="aliexpress_packages",
    ),
    # Canada Post
    "capost_delivered": SensorEntityDescription(
        name="Mail Canada Post Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="capost_delivered",
    ),
    "capost_delivering": SensorEntityDescription(
        name="Mail Canada Post Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="capost_delivering",
    ),
    "capost_mail": SensorEntityDescription(
        name="Mail Canada Post Mail",
        native_unit_of_measurement="piece(s)",
        icon="mdi:mailbox-up",
        key="capost_mail",
    ),
    "capost_packages": SensorEntityDescription(
        name="Mail Canada Post Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="capost_packages",
    ),
    # DHL
    "dhl_delivered": SensorEntityDescription(
        name="Mail DHL Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dhl_delivered",
    ),
    "dhl_delivering": SensorEntityDescription(
        name="Mail DHL Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="dhl_delivering",
    ),
    "dhl_packages": SensorEntityDescription(
        name="Mail DHL Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dhl_packages",
    ),
    # Hermes
    "hermes_delivered": SensorEntityDescription(
        name="Mail Hermes Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="hermes_delivered",
    ),
    "hermes_delivering": SensorEntityDescription(
        name="Mail Hermes Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="hermes_delivering",
    ),
    "hermes_packages": SensorEntityDescription(
        name="Mail Hermes Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="hermes_packages",
    ),
    # Royal Mail
    "royal_delivered": SensorEntityDescription(
        name="Mail Royal Mail Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="royal_delivered",
    ),
    "royal_delivering": SensorEntityDescription(
        name="Mail Royal Mail Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="royal_delivering",
    ),
    "royal_packages": SensorEntityDescription(
        name="Mail Royal Mail Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="royal_packages",
    ),
    # Australia Post
    "auspost_delivered": SensorEntityDescription(
        name="Mail AusPost Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="auspost_delivered",
    ),
    "auspost_delivering": SensorEntityDescription(
        name="Mail AusPost Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="auspost_delivering",
    ),
    "auspost_packages": SensorEntityDescription(
        name="Mail AusPost Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="auspost_packages",
    ),
    # Poczta Polska SA
    # "poczta_polska_delivered": SensorEntityDescription(
    #     name="Poczta Polska Delivered",
    #     native_unit_of_measurement="package(s)",
    #     icon="mdi:package-variant",
    #     key="poczta_polska_delivered",
    # ),
    "poczta_polska_delivering": SensorEntityDescription(
        name="Mail Poczta Polska Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="poczta_polska_delivering",
    ),
    "poczta_polska_packages": SensorEntityDescription(
        name="Mail Poczta Polska Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="poczta_polska_packages",
    ),
    # InPost.pl
    "inpost_pl_delivering": SensorEntityDescription(
        name="Mail InPost.pl Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="inpost_pl_delivering",
    ),
    "inpost_pl_delivered": SensorEntityDescription(
        name="Mail InPost.pl Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="inpost_pl_delivered",
    ),
    "inpost_pl_packages": SensorEntityDescription(
        name="Mail InPost.pl Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="inpost_pl_packages",
    ),
    # DPD Poland
    "dpd_com_pl_delivering": SensorEntityDescription(
        name="Mail DPD.com.pl Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="dpd_com_pl_delivering",
    ),
    "dpd_com_pl_delivered": SensorEntityDescription(
        name="Mail DPD.com.pl Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="dpd_com_pl_delivered",
    ),
    "dpd_com_pl_packages": SensorEntityDescription(
        name="Mail DPD.com.pl Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dpd_com_pl_packages",
    ),
    # DPD
    "dpd_delivering": SensorEntityDescription(
        name="Mail DPD Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="dpd_delivering",
    ),
    "dpd_delivered": SensorEntityDescription(
        name="Mail DPD Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="dpd_delivered",
    ),
    "dpd_packages": SensorEntityDescription(
        name="Mail DPD Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dpd_packages",
    ),
    # GLS
    "gls_delivering": SensorEntityDescription(
        name="Mail GLS Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="gls_delivering",
    ),
    "gls_delivered": SensorEntityDescription(
        name="Mail GLS Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="gls_delivered",
    ),
    "gls_packages": SensorEntityDescription(
        name="Mail GLS Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="gls_packages",
    ),
    # Evri
    "evri_delivered": SensorEntityDescription(
        name="Mail Evri Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="evri_delivered",
    ),
    "evri_delivering": SensorEntityDescription(
        name="Mail Evri Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="evri_delivering",
    ),
    "evri_packages": SensorEntityDescription(
        name="Mail Evri Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="evri_packages",
    ),
    # DHL Parcel NL
    "dhl_parcel_nl_delivering": SensorEntityDescription(
        name="DHL Parcel NL Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="dhl_parcel_nl_delivering",
    ),
    "dhl_parcel_nl_delivered": SensorEntityDescription(
        name="DHL Parcel NL Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="dhl_parcel_nl_delivered",
    ),
    "dhl_parcel_nl_packages": SensorEntityDescription(
        name="DHL Parcel NL Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dhl_parcel_nl_packages",
    ),
    # Bonshaw Distribution Network
    "bonshaw_distribution_network_delivered": SensorEntityDescription(
        name="Mail Bonshaw Distribution Network Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="bonshaw_distribution_network_delivered",
    ),
    "bonshaw_distribution_network_delivering": SensorEntityDescription(
        name="Mail Bonshaw Distribution Network Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="bonshaw_distribution_network_delivering",
    ),
    "bonshaw_distribution_network_packages": SensorEntityDescription(
        name="Mail Bonshaw Distribution Network Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="bonshaw_distribution_network_packages",
    ),
    # Purolator
    "purolator_delivered": SensorEntityDescription(
        name="Mail Purolator Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="purolator_delivered",
    ),
    "purolator_delivering": SensorEntityDescription(
        name="Mail Purolator Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="purolator_delivering",
    ),
    "purolator_packages": SensorEntityDescription(
        name="Mail Purolator Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="purolator_packages",
    ),
    # Intelcom
    "intelcom_delivered": SensorEntityDescription(
        name="Mail Intelcom Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="intelcom_delivered",
    ),
    "intelcom_delivering": SensorEntityDescription(
        name="Mail Intelcom Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="intelcom_delivering",
    ),
    "intelcom_packages": SensorEntityDescription(
        name="Mail Intelcom Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="intelcom_packages",
    ),
    # Walmart
    "walmart_delivering": SensorEntityDescription(
        name="Mail Walmart Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="walmart_delivering",
    ),
    "walmart_delivered": SensorEntityDescription(
        name="Mail Walmart Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="walmart_delivered",
    ),
    "walmart_packages": SensorEntityDescription(
        name="Mail Walmart Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="walmart_packages",
    ),
    "walmart_exception": SensorEntityDescription(
        name="Mail Walmart Exception",
        native_unit_of_measurement="package(s)",
        icon="mdi:archive-alert",
        key="walmart_exception",
    ),
    # Home Depot
    "home_depot_delivering": SensorEntityDescription(
        name="Mail Home Depot Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="home_depot_delivering",
    ),
    "home_depot_delivered": SensorEntityDescription(
        name="Mail Home Depot Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="home_depot_delivered",
    ),
    "home_depot_packages": SensorEntityDescription(
        name="Mail Home Depot Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="home_depot_packages",
    ),
    "home_depot_exception": SensorEntityDescription(
        name="Mail Home Depot Exception",
        native_unit_of_measurement="package(s)",
        icon="mdi:archive-alert",
        key="home_depot_exception",
    ),
    # Shopify
    "shopify_delivered": SensorEntityDescription(
        name="Mail Shopify Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="shopify_delivered",
    ),
    "shopify_delivering": SensorEntityDescription(
        name="Mail Shopify Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="shopify_delivering",
    ),
    "shopify_packages": SensorEntityDescription(
        name="Mail Shopify Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="shopify_packages",
    ),
    # BuildingLink
    "buildinglink_delivered": SensorEntityDescription(
        name="Mail BuildingLink Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="buildinglink_delivered",
    ),
    # Post NL
    "post_nl_delivering": SensorEntityDescription(
        name="Post NL Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="post_nl_delivering",
    ),
    "post_nl_exception": SensorEntityDescription(
        name="Post NL Missed Delivery",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-alert",
        key="post_nl_exception",
    ),
    "post_nl_delivered": SensorEntityDescription(
        name="Post NL Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="post_nl_delivered",
    ),
    "post_nl_packages": SensorEntityDescription(
        name="Post NL Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="post_nl_packages",
    ),
    # Post DE
    "post_de_delivering": SensorEntityDescription(
        name="Post DE Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="post_de_delivering",
    ),
    # "post_de_delivered": SensorEntityDescription(
    #    name="Post DE Delivered",
    #    native_unit_of_measurement="package(s)",
    #    icon="mdi:truck-delivery",
    #    key="post_de_delivered",
    # ),
    "post_de_packages": SensorEntityDescription(
        name="Post DE Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="post_de_packages",
    ),
    "post_de_mail": SensorEntityDescription(
        name="Mail Post DE Mail",
        native_unit_of_measurement="piece(s)",
        icon="mdi:mailbox-up",
        key="post_de_mail",
    ),
    # Post Austria
    "post_at_delivering": SensorEntityDescription(
        name="Post AT Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="post_at_delivering",
    ),
    "post_at_delivered": SensorEntityDescription(
        name="Post AT Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="post_at_delivered",
    ),
    "post_at_packages": SensorEntityDescription(
        name="Post AT Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="post_at_packages",
    ),
    # Rewe Lieferservice
    "rewe_lieferservice_delivering": SensorEntityDescription(
        name="Rewe Lieferservice Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="rewe_lieferservice_delivering",
    ),
    "rewe_lieferservice_delivered": SensorEntityDescription(
        name="Rewe Lieferservice Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="rewe_lieferservice_delivered",
    ),
    "rewe_lieferservice_packages": SensorEntityDescription(
        name="Rewe Lieferservice Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="rewe_lieferservice_packages",
    ),
    # DPD Netherlands
    "dpd_nl_delivering": SensorEntityDescription(
        name="Mail DPD NL Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="dpd_nl_delivering",
    ),
    "dpd_nl_delivered": SensorEntityDescription(
        name="Mail DPD NL Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="dpd_nl_delivered",
    ),
    "dpd_nl_packages": SensorEntityDescription(
        name="Mail DPD NL Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dpd_nl_packages",
    ),
    # bol.com (Netherlands)
    "bolcom_delivering": SensorEntityDescription(
        name="Mail bol.com Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="bolcom_delivering",
    ),
    "bolcom_delivered": SensorEntityDescription(
        name="Mail bol.com Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="bolcom_delivered",
    ),
    "bolcom_packages": SensorEntityDescription(
        name="Mail bol.com Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="bolcom_packages",
    ),
    # Etsy
    "etsy_delivered": SensorEntityDescription(
        name="Mail Etsy Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="etsy_delivered",
    ),
    "etsy_delivering": SensorEntityDescription(
        name="Mail Etsy Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="etsy_delivering",
    ),
    "etsy_packages": SensorEntityDescription(
        name="Mail Etsy Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="etsy_packages",
    ),
    # DAO
    "dao_delivering": SensorEntityDescription(
        name="Mail DAO Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="dao_delivering",
    ),
    "dao_delivered": SensorEntityDescription(
        name="Mail DAO Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="dao_delivered",
    ),
    "dao_packages": SensorEntityDescription(
        name="Mail DAO Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="dao_packages",
    ),
    # Budbee
    "budbee_delivering": SensorEntityDescription(
        name="Mail Budbee Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="budbee_delivering",
    ),
    "budbee_delivered": SensorEntityDescription(
        name="Mail Budbee Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="budbee_delivered",
    ),
    "budbee_packages": SensorEntityDescription(
        name="Mail Budbee Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="budbee_packages",
    ),
    # Airmee
    "airmee_delivering": SensorEntityDescription(
        name="Mail Airmee Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="airmee_delivering",
    ),
    "airmee_delivered": SensorEntityDescription(
        name="Mail Airmee Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="airmee_delivered",
    ),
    "airmee_packages": SensorEntityDescription(
        name="Mail Airmee Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="airmee_packages",
    ),
    # Burd Delivery
    "burd_delivering": SensorEntityDescription(
        name="Mail Burd Delivery Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="burd_delivering",
    ),
    "burd_delivered": SensorEntityDescription(
        name="Mail Burd Delivery Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="burd_delivered",
    ),
    "burd_packages": SensorEntityDescription(
        name="Mail Burd Delivery Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="burd_packages",
    ),
    ###
    # !!! Insert new sensors above these summary sensors !!!
    ###
    "zpackages_delivered": SensorEntityDescription(
        name="Mail Packages Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="zpackages_delivered",
    ),
    "zpackages_delivering": SensorEntityDescription(
        name="Mail Packages Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="zpackages_delivering",
    ),
    "zpackages_transit": SensorEntityDescription(
        name="Mail Packages In Transit",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="zpackages_transit",
    ),
}

BINARY_SENSORS: Final[dict[str, MailandPackagesBinarySensorEntityDescription]] = {
    "usps_update": MailandPackagesBinarySensorEntityDescription(
        name="USPS Image Updated",
        key="usps_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        selectable=False,
        entity_registry_enabled_default=False,
    ),
    "amazon_update": MailandPackagesBinarySensorEntityDescription(
        name="Amazon Image Updated",
        key="amazon_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        selectable=False,
        entity_registry_enabled_default=False,
    ),
    "post_de_update": MailandPackagesBinarySensorEntityDescription(
        name="Post DE Image Updated",
        key="post_de_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        selectable=False,
        entity_registry_enabled_default=False,
    ),
    "usps_mail_delivered": MailandPackagesBinarySensorEntityDescription(
        name="USPS Mail Delivered",
        key="usps_mail_delivered",
        entity_registry_enabled_default=False,
        selectable=True,
    ),
}


IMAGE_SENSORS: Final[dict[str, SensorEntityDescription]] = {
    "usps_mail_image_system_path": SensorEntityDescription(
        name="Mail Image System Path",
        icon="mdi:folder-multiple-image",
        key="usps_mail_image_system_path",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "usps_mail_image_url": SensorEntityDescription(
        name="Mail Image URL",
        icon="mdi:link-variant",
        key="usps_mail_image_url",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "usps_mail_grid_image_path": SensorEntityDescription(
        name="Mail Grid Image Path",
        icon="mdi:folder-multiple-image",
        key="usps_mail_grid_image_path",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}

# Name
CAMERA_DATA = {
    "usps_camera": ["Mail USPS Camera"],
    "ups_camera": ["Mail UPS Camera"],
    "amazon_camera": ["Mail Amazon Delivery Camera"],
    "walmart_camera": ["Mail Walmart Delivery Camera"],
    "home_depot_camera": ["Mail Home Depot Delivery Camera"],
    "fedex_camera": ["Mail FedEx Delivery Camera"],
    "generic_camera": ["Mail Generic Delivery Camera"],
    "post_de_camera": ["Mail Post DE Camera"],
}

# Configuration for shipper-specific image extraction parameters
# Only contains values that cannot be derived from shipper_name
CAMERA_EXTRACTION_CONFIG = {
    "ups": {
        "image_type": "jpeg",
        "cid_name": "deliveryPhoto",
    },
    "walmart": {
        "image_type": "png",
        "cid_name": "deliveryProofLabel",
    },
    "fedex": {
        "image_type": "jpeg",
        "attachment_filename_pattern": "delivery",
    },
    # PostNord
    "postnord_delivered": SensorEntityDescription(
        name="Mail PostNord Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="postnord_delivered",
    ),
    "postnord_delivering": SensorEntityDescription(
        name="Mail PostNord Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="postnord_delivering",
    ),
    "postnord_packages": SensorEntityDescription(
        name="Mail PostNord Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="postnord_packages",
    ),
    # Bring
    "bring_delivered": SensorEntityDescription(
        name="Mail Bring Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="bring_delivered",
    ),
    "bring_delivering": SensorEntityDescription(
        name="Mail Bring Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="bring_delivering",
    ),
    "bring_packages": SensorEntityDescription(
        name="Mail Bring Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="bring_packages",
    ),
    # DB Schenker
    "db_schenker_delivered": SensorEntityDescription(
        name="Mail DB Schenker Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="db_schenker_delivered",
    ),
    "db_schenker_delivering": SensorEntityDescription(
        name="Mail DB Schenker Delivering",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="db_schenker_delivering",
    ),
    "db_schenker_packages": SensorEntityDescription(
        name="Mail DB Schenker Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="db_schenker_packages",
    ),
}

# Sensor Index
SENSOR_NAME = 0
SENSOR_UNIT = 1
SENSOR_ICON = 2

# Marketplace shippers whose emails embed the physical carrier's tracking
# number in the body. Used to de-duplicate against carrier shippers: when the
# extracted number already appears in a carrier shipper's results, the
# marketplace entry is dropped so the package is only counted once.
# Regexes are applied case-insensitively to the email text parts; group 1 is
# the carrier tracking number.
MARKETPLACE_CARRIER_TRACKING = {
    "etsy": r"tracking number:?\s*#?([A-Za-z0-9]{8,34})",
    "shopify": r"tracking number:?\s*#?([A-Za-z0-9]{8,34})",
    "home_depot": r"Tracking ID:?\s*#?([A-Za-z0-9]{8,34})",
}

# For sensors with delivering and delivered statuses
SHIPPERS = [
    "aliexpress",
    "amazon",
    "capost",
    "dhl",
    "fedex",
    "ups",
    "usps",
    "walmart",
    "home_depot",
    "hermes",
    "royal",
    "auspost",
    "inpost_pl",
    "dpd_com_pl",
    "dpd",
    "gls",
    "dhl_parcel_nl",
    "bonshaw_distribution_network",
    "purolator",
    "intelcom",
    "etsy",
    "post_nl",
    "post_at",
    "rewe_lieferservice",
    "dpd_nl",
    "bolcom",
    "poczta_polska",
    "buildinglink",
    "post_de",
    "postnord",
    "bring",
    "db_schenker",
    "shopify",
]

# Authentication types
CONF_AUTH_TYPE = "auth_type"
AUTH_TYPE_PASSWORD = "password"
AUTH_TYPE_OAUTH_MICROSOFT = "oauth2_microsoft"
AUTH_TYPE_OAUTH_GOOGLE = "oauth2_google"
AUTH_TYPES = [AUTH_TYPE_PASSWORD, AUTH_TYPE_OAUTH_MICROSOFT, AUTH_TYPE_OAUTH_GOOGLE]

# OAuth2 scopes per provider
OAUTH_SCOPES = {
    AUTH_TYPE_OAUTH_MICROSOFT: "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
    AUTH_TYPE_OAUTH_GOOGLE: "https://mail.google.com/",
}

# OAuth2 provider IMAP defaults
OAUTH_IMAP_DEFAULTS = {
    AUTH_TYPE_OAUTH_MICROSOFT: {
        "host": "outlook.office365.com",
        "port": 993,
        "imap_security": "SSL",
    },
    AUTH_TYPE_OAUTH_GOOGLE: {
        "host": "imap.gmail.com",
        "port": 993,
        "imap_security": "SSL",
    },
}
