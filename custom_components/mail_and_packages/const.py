DOMAIN = "mail_and_packages"

PLATFORMS = ["sensor", "camera"]
REQUIRED_FILES = ["const.py", , "manifest.json", "sensor.py", "config_flow.py", "camera.py"]
VERSION = "0.0.3"
ISSUE_URL = "http://github.com/moralmunky/Home-Assistant-Mail"

STARTUP = """
-------------------------------------------------------------------
{name}
Version: {version}
This is a custom component
If you have any issues with this you need to open an issue here:
{issueurl}
-------------------------------------------------------------------
"""

DATA_CONF = "mail_and_packages.conf"

DEFAULT_NAME = "Mail And Packages"
DEFAULT_PORT = '993'
DEFAULT_FOLDER = 'Inbox'
DEFAULT_PATH = '/home/homeassistant/.homeassistant/www/mail_and_packages/'