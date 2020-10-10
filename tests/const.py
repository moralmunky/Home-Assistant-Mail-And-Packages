""" Constants for tests. """

FAKE_CONFIG_DATA_BAD = {
    "folder": '"INBOX"',
    "generate_mp4": "false",
    "gif_duration": 5,
    "host": None,
    "image_name": "mail_today.gif",
    "image_path": "/config/www/mail_and_packages/",
    "image_security": "true",
    "password": "suchfakemuchpassword",
    "port": 993,
    "resources": [
        "amazon_packages",
        "fedex_delivered",
        "fedex_delivering",
        "fedex_packages",
        "mail_updated",
        "ups_delivered",
        "ups_delivering",
        "ups_packages",
        "usps_delivered",
        "usps_delivering",
        "usps_mail",
        "usps_packages",
        "zpackages_delivered",
        "zpackages_transit",
        "dhl_delivered",
        "dhl_delivering",
        "dhl_packages",
        "amazon_delivered",
    ],
    "scan_interval": 20,
    "username": "user@fake.email",
}

FAKE_CONFIG_DATA = {
    "amazon_fwds": ["fakeuser@fake.email"],
    "folder": '"INBOX"',
    "generate_mp4": False,
    "gif_duration": 5,
    "host": "imap.test.email",
    "image_name": "mail_today.gif",
    "image_path": "/config/www/mail_and_packages/",
    "image_security": False,
    "password": "suchfakemuchpassword",
    "port": 993,
    "resources": [
        "amazon_delivered",
        "amazon_hub",
        "amazon_packages",
        "capost_delivered",
        "capost_delivering",
        "capost_packages",
        "dhl_delivered",
        "dhl_delivering",
        "dhl_packages",
        "fedex_delivered",
        "fedex_delivering",
        "fedex_packages",
        "mail_updated",
        "ups_delivered",
        "ups_delivering",
        "ups_packages",
        "usps_delivered",
        "usps_delivering",
        "usps_mail",
        "usps_packages",
        "zpackages_delivered",
        "zpackages_transit",
    ],
    "scan_interval": 20,
    "username": "user@fake.email",
}

FAKE_CONFIG_DATA_NO_RND = {
    "amazon_fwds": ["fakeuser@fake.email"],
    "folder": '"INBOX"',
    "generate_mp4": False,
    "gif_duration": 5,
    "host": "imap.test.email",
    "image_name": "mail_today.gif",
    "image_path": "/config/www/mail_and_packages/",
    "image_security": False,
    "password": "suchfakemuchpassword",
    "port": 993,
    "resources": [
        "amazon_delivered",
        "amazon_hub",
        "amazon_packages",
        "capost_delivered",
        "capost_delivering",
        "capost_packages",
        "dhl_delivered",
        "dhl_delivering",
        "dhl_packages",
        "fedex_delivered",
        "fedex_delivering",
        "fedex_packages",
        "mail_updated",
        "ups_delivered",
        "ups_delivering",
        "ups_packages",
        "usps_delivered",
        "usps_delivering",
        "usps_mail",
        "usps_packages",
        "zpackages_delivered",
        "zpackages_transit",
    ],
    "scan_interval": 20,
    "username": "user@fake.email",
}

FAKE_CONFIG_DATA_MP4 = {
    "amazon_fwds": "fakeuser@fake.email",
    "folder": '"INBOX"',
    "generate_mp4": True,
    "gif_duration": 5,
    "host": "imap.test.email",
    "image_name": "mail_today.gif",
    "image_path": "/config/www/mail_and_packages/",
    "image_security": True,
    "password": "suchfakemuchpassword",
    "port": 993,
    "resources": [
        "amazon_delivered",
        "amazon_packages",
        "capost_delivered",
        "capost_delivering",
        "capost_packages",
        "dhl_delivered",
        "dhl_delivering",
        "dhl_packages",
        "fedex_delivered",
        "fedex_delivering",
        "fedex_packages",
        "mail_updated",
        "ups_delivered",
        "ups_delivering",
        "ups_packages",
        "usps_delivered",
        "usps_delivering",
        "usps_mail",
        "usps_packages",
        "zpackages_delivered",
        "zpackages_transit",
    ],
    "scan_interval": 20,
    "username": "user@fake.email",
}

FAKE_UPDATE_DATA = {
    "image_name": "mail_today.gif",
    "mail_updated": "Sep-18-2020 06:29 PM",
    "usps_mail": 6,
    "usps_delivered": 3,
    "usps_delivering": 3,
    "usps_packages": 3,
    "usps_tracking": ["92123456789012345"],
    "ups_delivered": 1,
    "ups_delivering": 1,
    "ups_packages": 1,
    "ups_tracking": ["1Z123456789"],
    "fedex_delivered": 0,
    "fedex_delivering": 2,
    "fedex_packages": 2,
    "fedex_tracking": ["1234567890"],
    "amazon_packages": 7,
    "amazon_delivered": 2,
    "amazon_order": ["#123-4567890"],
    "amazon_hub": 2,
    "amazon_hub_code": 123456,
    "capost_delivered": 1,
    "capost_delivering": 1,
    "capost_packages": 2,
    "dhl_delivered": 0,
    "dhl_delivering": 1,
    "dhl_packages": 2,
    "dhl_tracking": ["1234567890"],
    "zpackages_delivered": 7,
    "zpackages_transit": 8,
}
