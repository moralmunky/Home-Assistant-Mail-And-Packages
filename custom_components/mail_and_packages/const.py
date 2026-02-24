"""Constants for Mail and Packages."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "mail_and_packages"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "1.0.4"  # Now updated by release workflow
ISSUE_URL = "http://github.com/moralmunky/Home-Assistant-Mail-And-Packages"
PLATFORM = "sensor"
PLATFORMS = ["camera", "sensor"]
DATA = "data"
OVERLAY = ["overlay.png", "vignette.png", "white.png"]
SERVICE_UPDATE_FILE_PATH = "update_file_path"

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

# Advanced tracking attributes
ATTR_UNIVERSAL_TRACKING = "universal_tracking"
ATTR_17TRACK_FORWARDED = "forwarded_to_17track"
ATTR_AMAZON_COOKIE_TRACKING = "amazon_cookie_tracking"
ATTR_LLM_ANALYZED = "llm_analyzed"

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

# Package Tracking Registry
CONF_REGISTRY_ENABLED = "registry_enabled"
CONF_REGISTRY_DELIVERED_DAYS = "registry_delivered_days"
CONF_REGISTRY_DETECTED_DAYS = "registry_detected_days"

# Advanced Tracking - Universal Email Scanner
CONF_SCAN_ALL_EMAILS = "scan_all_emails"

# Advanced Tracking - Tracking Service Forwarding (generic, supports multiple backends)
CONF_TRACKING_FORWARD_ENABLED = "tracking_forward_enabled"
CONF_TRACKING_SERVICE = "tracking_service"
CONF_TRACKING_SERVICE_ENTRY_ID = "tracking_service_entry_id"

# Legacy aliases (backward compat with v5 configs)
CONF_17TRACK_ENABLED = "seventeen_track_enabled"
CONF_17TRACK_ENTRY_ID = "seventeen_track_entry_id"

# Advanced Tracking - LLM Analysis (privacy: off by default, explicit opt-in)
CONF_LLM_ENABLED = "llm_enabled"
CONF_LLM_PROVIDER = "llm_provider"
CONF_LLM_ENDPOINT = "llm_endpoint"
CONF_LLM_API_KEY = "llm_api_key"
CONF_LLM_MODEL = "llm_model"

# Advanced Tracking - Amazon Cookie Scraping
CONF_AMAZON_COOKIES_ENABLED = "amazon_cookies_enabled"
CONF_AMAZON_COOKIES = "amazon_cookies"
CONF_AMAZON_COOKIE_DOMAIN = "amazon_cookie_domain"

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
DEFAULT_AMAZON_FWDS = '""'
DEFAULT_ALLOW_EXTERNAL = False
DEFAULT_CUSTOM_IMG = False
DEFAULT_CUSTOM_IMG_FILE = "custom_components/mail_and_packages/images/mail_none.gif"
DEFAULT_AMAZON_DAYS = 3

# Package Tracking Registry Defaults
DEFAULT_REGISTRY_ENABLED = False
DEFAULT_REGISTRY_DELIVERED_DAYS = 3
DEFAULT_REGISTRY_DETECTED_DAYS = 14

# Advanced Tracking Defaults
DEFAULT_SCAN_ALL_EMAILS = False
DEFAULT_TRACKING_FORWARD_ENABLED = False
DEFAULT_TRACKING_SERVICE = "seventeentrack"
DEFAULT_TRACKING_SERVICE_ENTRY_ID = ""
# Legacy defaults (backward compat)
DEFAULT_17TRACK_ENABLED = False
DEFAULT_17TRACK_ENTRY_ID = ""
DEFAULT_LLM_ENABLED = False
DEFAULT_LLM_PROVIDER = "ollama"
DEFAULT_LLM_ENDPOINT = "http://localhost:11434"
DEFAULT_LLM_API_KEY = ""
DEFAULT_LLM_MODEL = ""
DEFAULT_AMAZON_COOKIES_ENABLED = False
DEFAULT_AMAZON_COOKIES = ""
DEFAULT_AMAZON_COOKIE_DOMAIN = "amazon.com"
LLM_PROVIDERS = ["ollama", "anthropic", "openai"]

# Supported tracking service integrations for forwarding
# Each entry defines how to call the integration's add-tracking service
TRACKING_SERVICES: Final[dict[str, dict[str, Any]]] = {
    "seventeentrack": {
        "name": "17track",
        "domain": "seventeentrack",
        "service": "add_package",
        "needs_entry_id": True,
        "params": {
            "entry_id_key": "config_entry_id",
            "tracking_key": "package_tracking_number",
            "name_key": "package_friendly_name",
        },
    },
    "aftership": {
        "name": "AfterShip",
        "domain": "aftership",
        "service": "add_tracking",
        "needs_entry_id": False,
        "params": {
            "tracking_key": "tracking_number",
            "name_key": "title",
        },
    },
    "aliexpress_package_tracker": {
        "name": "AliExpress Package Tracker",
        "domain": "aliexpress_package_tracker",
        "service": "add_tracking",
        "needs_entry_id": False,
        "params": {
            "tracking_key": "tracking_number",
            "name_key": "title",
        },
    },
}
TRACKING_SERVICE_OPTIONS = list(TRACKING_SERVICES.keys())

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
]
AMAZON_DELIVERED_SUBJECT = [
    "Delivered: Your",
    "Consegna effettuata:",
    "Dostarczono:",
    "Geliefert:",
]
AMAZON_SHIPMENT_TRACKING = ["shipment-tracking", "conferma-spedizione"]
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
    "",
]

# Universal tracking number patterns (for scanning all emails)
# These are deliberately MORE SPECIFIC than per-carrier patterns to reduce
# false positives when scanning arbitrary emails. Carriers with overly generic
# patterns (pure digit sequences < 20 digits) are excluded or tightened.
UNIVERSAL_TRACKING_PATTERNS: Final[dict[str, dict[str, str]]] = {
    "usps": {
        # USPS: starts with 92/93/94/95, 17-28 digits total (distinctive prefix)
        "pattern": r"(?:^|\b)(9[2345]\d{15,26})(?:\b|$)",
        "name": "USPS",
    },
    "ups": {
        # UPS: starts with 1Z followed by 16 alphanumeric chars (very distinctive)
        "pattern": r"(?:^|\b)(1Z[0-9A-Z]{16})(?:\b|$)",
        "name": "UPS",
    },
    "fedex": {
        # FedEx: exactly 12, 15, or 20 digits (not a range to avoid matching
        # credit card numbers, phone numbers, etc.)
        "pattern": r"(?:^|\b)(\d{12}|\d{15}|\d{20})(?:\b|$)",
        "name": "FedEx",
    },
    "dhl": {
        # DHL Express: JJD/JD prefix followed by digits (distinctive prefix avoids
        # matching arbitrary 10-11 digit numbers like phone numbers)
        "pattern": r"(?:^|\b)((?:JJD|JD)\d{8,18})(?:\b|$)",
        "name": "DHL",
    },
    "royal_mail": {
        # Royal Mail: 2 letters + 9 digits + GB suffix (very distinctive)
        "pattern": r"(?:^|\b)([A-Za-z]{2}[0-9]{9}GB)(?:\b|$)",
        "name": "Royal Mail",
    },
    "australia_post": {
        # Australia Post: 2 letters + 9 digits + AU suffix (very distinctive)
        "pattern": r"(?:^|\b)([A-Za-z]{2}[0-9]{9}AU)(?:\b|$)",
        "name": "Australia Post",
    },
    "poczta_polska": {
        # Poczta Polska: exactly 20 digits (long enough to be distinctive)
        "pattern": r"(?:^|\b)(\d{20})(?:\b|$)",
        "name": "Poczta Polska",
    },
    "inpost": {
        # InPost: exactly 24 digits (very long, very distinctive)
        "pattern": r"(?:^|\b)(\d{24})(?:\b|$)",
        "name": "InPost",
    },
    "dpd": {
        # DPD: 13 digits + 1-2 alphanumeric chars (mixed format is distinctive)
        "pattern": r"(?:^|\b)(\d{13}[A-Z0-9]{1,2})(?:\b|$)",
        "name": "DPD",
    },
    # NOTE: Hermes (\d{16}), Canada Post (\d{16}), and GLS (\d{11}) are
    # intentionally excluded from universal scanning because their patterns
    # (pure digit sequences) match credit card numbers, phone numbers, and
    # other common numeric strings. These carriers are still detected via
    # their sender-specific email matching in SENSOR_DATA.
}

# Context keywords for reducing false positives in universal email scanning.
# A tracking number candidate from a non-carrier email is only accepted if
# one of these keywords appears nearby in the email text.
TRACKING_CONTEXT_KEYWORDS: Final[list[str]] = [
    "tracking",
    "track your",
    "shipment",
    "shipped",
    "shipping",
    "delivery",
    "deliver",
    "package",
    "parcel",
    "carrier",
    "in transit",
    "out for delivery",
    "dispatched",
    "consignment",
    "przesyłka",
    "nadanie",
    "wysłano",
    "śledzenie",
    "paczka",
    "zustellung",
    "sendungsverfolgung",
    "spedizione",
    "tracciamento",
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
        ],
    },
    "ups_delivering": {
        "email": ["mcinfo@ups.com"],
        "subject": [
            "UPS Update: Package Scheduled for Delivery Today",
            "UPS Update: Follow Your Delivery on a Live Map",
            "UPS Pre-Arrival: Your Driver is Arriving Soon! Follow on a Live Map",
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
        "email": ["donotreply@canadapost.postescanada.ca"],
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
        ],
        "body": ["has been delivered", "została doręczona"],
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
            "paket kommt heute",
            "Powiadomienie o przesyłce",
        ],
        "body": ["scheduled for delivery TODAY", "zostanie dziś do Państwa doręczona"],
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
    "auspost_tracking": {"pattern": ["\\d{7,12}|[A-Za-z]{2}[0-9]{9}AU"]},
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
        key="gls_delivered",
    ),
    "gls_packages": SensorEntityDescription(
        name="Mail GLS Packages",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="gls_packages",
    ),
    # Universal Email Tracking (opt-in)
    "email_tracking_numbers": SensorEntityDescription(
        name="Mail Email Tracking Numbers",
        native_unit_of_measurement="tracking #(s)",
        icon="mdi:email-search",
        key="email_tracking_numbers",
    ),
    # Tracking Service Forwarded (opt-in, supports 17track/AfterShip/AliExpress)
    "tracking_service_forwarded": SensorEntityDescription(
        name="Mail Tracking Forwarded",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed-plus",
        key="tracking_service_forwarded",
    ),
    # Amazon Order Tracking via cookies (opt-in)
    "amazon_cookie_packages": SensorEntityDescription(
        name="Mail Amazon Order Tracking",
        native_unit_of_measurement="package(s)",
        icon="mdi:package",
        key="amazon_cookie_packages",
    ),
    # Package Tracking Registry sensors (opt-in)
    "registry_tracked": SensorEntityDescription(
        name="Mail Packages Tracked",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed-check",
        key="registry_tracked",
    ),
    "registry_in_transit": SensorEntityDescription(
        name="Mail Packages In Transit (Registry)",
        native_unit_of_measurement="package(s)",
        icon="mdi:truck-delivery",
        key="registry_in_transit",
    ),
    "registry_delivered": SensorEntityDescription(
        name="Mail Packages Delivered (Registry)",
        native_unit_of_measurement="package(s)",
        icon="mdi:package-variant-closed",
        key="registry_delivered",
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
# Maps carrier sensor suffix to registry status for reconciliation
SENSOR_STATUS_MAP: Final[dict[str, str]] = {
    "_delivered": "delivered",
    "_delivering": "in_transit",
    "_exception": "exception",
}

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
]
