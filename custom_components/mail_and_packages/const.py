"""Constants for Mail and Packages."""
from __future__ import annotations

from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.helpers.entity import EntityCategory

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

# Attributes
ATTR_AMAZON_IMAGE = "amazon_image"
ATTR_COUNT = "count"
ATTR_CODE = "code"
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
ATTR_PATTERN = "pattern"
ATTR_USPS_MAIL = "usps_mail"

# Configuration Properties
CONF_ALLOW_EXTERNAL = "allow_external"
CONF_CAMERA_NAME = "camera_name"
CONF_CUSTOM_IMG = "custom_img"
CONF_CUSTOM_IMG_FILE = "custom_img_file"
CONF_FOLDER = "folder"
CONF_PATH = "image_path"
CONF_DURATION = "gif_duration"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_IMAGE_SECURITY = "image_security"
CONF_IMAP_TIMEOUT = "imap_timeout"
CONF_GENERATE_MP4 = "generate_mp4"
CONF_AMAZON_FWDS = "amazon_fwds"
CONF_AMAZON_DAYS = "amazon_days"

# Defaults
DEFAULT_CAMERA_NAME = "Mail USPS Camera"
DEFAULT_NAME = "Mail And Packages"
DEFAULT_PORT = "993"
DEFAULT_FOLDER = '"INBOX"'
DEFAULT_PATH = "custom_components/mail_and_packages/images/"
DEFAULT_IMAGE_SECURITY = True
DEFAULT_IMAP_TIMEOUT = 30
DEFAULT_GIF_DURATION = 5
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_GIF_FILE_NAME = "mail_today.gif"
DEFAULT_AMAZON_FWDS = "(none)"
DEFAULT_ALLOW_EXTERNAL = False
DEFAULT_CUSTOM_IMG = False
DEFAULT_CUSTOM_IMG_FILE = "custom_components/mail_and_packages/images/mail_none.gif"
DEFAULT_AMAZON_DAYS = 3

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
]
AMAZON_DELIVERED_SUBJECT = [
    "Delivered: Your",
    "Consegna effettuata:",
    "Dostarczono:",
    "Geliefert:",
    "Livré",
]
AMAZON_SHIPMENT_TRACKING = [
    "shipment-tracking",
    "conferma-spedizione",
    "confirmar-envio",
    "versandbestaetigung",
    "confirmation-commande",
]
AMAZON_EMAIL = "order-update@"
AMAZON_PACKAGES = "amazon_packages"
AMAZON_ORDER = "amazon_order"
AMAZON_DELIVERED = "amazon_delivered"
AMAZON_IMG_PATTERN = (
    "(https://)([\\w_-]+(?:(?:\\.[\\w_-]+)+))([\\w.,@?^=%&:/~+#-;]*[\\w@?^=%&/~+#-;])?"
)
AMAZON_HUB = "amazon_hub"
AMAZON_HUB_CODE = "amazon_hub_code"
AMAZON_HUB_EMAIL = ["thehub@amazon.com", "order-update@amazon.com"]
AMAZON_HUB_SUBJECT = "ready for pickup from Amazon Hub Locker"
AMAZON_HUB_SUBJECT_SEARCH = "(You have a package to pick up)(.*)(\\d{6})"
AMAZON_HUB_BODY = "(Your pickup code is <b>)(\\d{6})"
AMAZON_TIME_PATTERN = [
    "will arrive:",
    "estimated delivery date is:",
    "guaranteed delivery date is:",
    "Arriving:",
    "Arriverà:",
    "arriving:",
    "Dostawa:",
    "Zustellung:",
    "Entrega:",
    "A chegar:",
    "Arrivée :",
]
AMAZON_EXCEPTION_SUBJECT = "Delivery update:"
AMAZON_EXCEPTION_BODY = "running late"
AMAZON_EXCEPTION = "amazon_exception"
AMAZON_EXCEPTION_ORDER = "amazon_exception_order"
AMAZON_PATTERN = "[0-9]{3}-[0-9]{7}-[0-9]{7}"
AMAZON_LANGS = [
    "it_IT",
    "it_IT.UTF-8",
    "pl_PL",
    "pl_PL.UTF-8",
    "de_DE",
    "de_DE.UTF-8",
    "es_ES",
    "es_ES.UTF-8",
    "pt_PT",
    "pt_PT.UTF-8",
    "pt_BR",
    "pt_BR.UTF-8",
    "",
]

# Sensor Data
SENSOR_DATA = {
    # USPS
    "usps_delivered": {
        "email": ["auto-reply@usps.com"],
        "subject": ["Item Delivered"],
    },
    "usps_delivering": {
        "email": ["auto-reply@usps.com"],
        "subject": ["Expected Delivery on", "Out for Delivery"],
        "body": ["Your item is out for delivery"],
    },
    "usps_exception": {
        "email": ["auto-reply@usps.com"],
        "subject": ["Delivery Exception"],
    },
    "usps_packages": {},
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
    # UPS
    "ups_delivered": {
        "email": ["mcinfo@ups.com"],
        "subject": [
            "Your UPS Package was delivered",
            "Your UPS Packages were delivered",
            "Your UPS Parcel was delivered",
            "Your UPS Parcels were delivered",
        ],
    },
    "ups_delivering": {
        "email": ["mcinfo@ups.com"],
        "subject": [
            "UPS Update: Package Scheduled for Delivery Today",
            "UPS Update: Follow Your Delivery on a Live Map",
            "UPS Pre-Arrival: Your Driver is Arriving Soon! Follow on a Live Map",
            "UPS Update: Parcel Scheduled for Delivery Today",
        ],
    },
    "ups_exception": {
        "email": ["mcinfo@ups.com"],
        "subject": ["UPS Update: New Scheduled Delivery Date"],
    },
    "ups_packages": {},
    "ups_tracking": {"pattern": ["1Z?[0-9A-Z]{16}"]},
    # FedEx
    "fedex_delivered": {
        "email": ["TrackingUpdates@fedex.com", "fedexcanada@fedex.com"],
        "subject": [
            "Your package has been delivered",
            "Your packages have been delivered",
        ],
    },
    "fedex_delivering": {
        "email": ["TrackingUpdates@fedex.com", "fedexcanada@fedex.com"],
        "subject": [
            "Delivery scheduled for today",
            "Your package is scheduled for delivery today",
            "Your package is now out for delivery",
            "out for delivery today",
        ],
    },
    "fedex_packages": {},
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
    "capost_delivering": {},
    "capost_packages": {},
    "capost_tracking": {},
    # DHL
    "dhl_delivered": {
        "email": [
            "donotreply_odd@dhl.com",
            "NoReply.ODD@dhl.com",
            "noreply@dhl.de",
            "pl.no.reply@dhl.com",
        ],
        "subject": [
            "DHL On Demand Delivery",
            "Powiadomienie o przesyłce",
            "Ihr DHL Paket wurde zugestellt",
        ],
        "body": [
            "has been delivered",
            "została doręczona",
            "ist angekommen",
        ],
    },
    "dhl_delivering": {
        "email": [
            "donotreply_odd@dhl.com",
            "NoReply.ODD@dhl.com",
            "noreply@dhl.de",
            "pl.no.reply@dhl.com",
        ],
        "subject": [
            "DHL On Demand Delivery",
            "Ihr DHL Paket kommt heute",
            "Powiadomienie o przesyłce",
        ],
        "body": [
            "scheduled for delivery TODAY",
            "zostanie dziś do Państwa doręczona",
            "wird Ihnen heute",
        ],
    },
    "dhl_packages": {},
    "dhl_tracking": {"pattern": ["\\d{10,11}"]},
    # Hermes.co.uk
    "hermes_delivered": {
        "email": ["donotreply@myhermes.co.uk"],
        "subject": ["Hermes has successfully delivered your"],
    },
    "hermes_delivering": {
        "email": ["donotreply@myhermes.co.uk"],
        "subject": ["parcel is now with your local Hermes courier"],
    },
    "hermes_packages": {},
    "hermes_tracking": {"pattern": ["\\d{16}"]},
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
        "pattern": ["\\d{20}"]
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
        "pattern": ["\\d{24}"]
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
        "pattern": ["\\d{13}[A-Z0-9]{1,2}"],
    },
    # GLS
    "gls_delivered": {
        "email": [
            "noreply@gls-group.eu",
            "powiadomienia@allegromail.pl",
        ],
        "subject": [
            "informacja o dostawie",
        ],
        "body": ["została dzisiaj dostarczona"],
    },
    "gls_delivering": {
        "email": [
            "noreply@gls-group.eu",
            "powiadomienia@allegromail.pl",
        ],
        "subject": ["paczka w drodze"],
        "body": ["Zespół GLS"],
    },
    "gls_packages": {},
    "gls_tracking": {
        # https://gls-group.eu/GROUP/en/parcel-tracking?match=51687952111
        "pattern": ["\\d{11}"]
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
   # Purolator
    "purolator_delivered": {
        "email": ["NotificationService@purolator.com"],
        "subject": ["Purolator - Your shipment is delivered"],
    },
    "purolator_delivering": {
        "email": ["NotificationService@purolator.com"],
        "subject": ["Purolator - Your shipment is out for delivery"],
    },
    "purolator_packages": {
        "email": ["NotificationService@purolator.com"],
        "subject": ["Purolator - Your shipment has been picked up"],
    },
    "purolator_tracking": {"pattern": ["\\d{12,15}"]},
    # Intelcom
    "intelcom_delivered": {
        "email": ["notifications@intelcom.ca"],
        "subject": ["Your order has been delivered!"],
    },
    "intelcom_delivering": {
        "email": ["notifications@intelcom.ca"],
        "subject": ["Your package is on the way!"],
    },
    "intelcom_packages": {
        "email": ["notifications@intelcom.ca"],
        "subject": ["Your package has been received!"],
    },
    "intelcom_tracking": {"pattern": ["INTLCMD[0-9]{9}"]},    
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
    # Amazon
    "amazon_packages": SensorEntityDescription(
        name="Mail Amazon Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package",
        key="amazon_packages",
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
        key="dpd_com_pl_delivered",
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
    ###
    # !!! Insert new sensors above these two !!!
    ###
    "zpackages_delivered": SensorEntityDescription(
        name="Mail Packages Delivered",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant",
        key="zpackages_delivered",
    ),
    "zpackages_transit": SensorEntityDescription(
        name="Mail Packages In Transit",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="zpackages_transit",
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
}

BINARY_SENSORS: Final[dict[str, BinarySensorEntityDescription]] = {
    "usps_update": BinarySensorEntityDescription(
        name="USPS Image Updated",
        key="usps_update",
        device_class=BinarySensorDeviceClass.UPDATE,
    ),
    "amazon_update": BinarySensorEntityDescription(
        name="Amazon Image Updated",
        key="amazon_update",
        device_class=BinarySensorDeviceClass.UPDATE,
    ),
}

# Name
CAMERA_DATA = {
    "usps_camera": ["Mail USPS Camera"],
    "amazon_camera": ["Mail Amazon Delivery Camera"],
}

# Sensor Index
SENSOR_NAME = 0
SENSOR_UNIT = 1
SENSOR_ICON = 2

# For sensors with delivering and delivered statuses
SHIPPERS = [
    "capost",
    "dhl",
    "fedex",
    "ups",
    "usps",
    "hermes",
    "royal",
    "auspost",
    "poczta_polska",
    "inpost_pl",
    "dpd_com_pl",
    "gls",
    "dhl_parcel_nl",
    "purolator",
    "intelcom",    
]
