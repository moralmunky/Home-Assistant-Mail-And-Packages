"""Example Load Platform integration."""
# from homeassistant.components.sensor import PLATFORM_SCHEMA
# import voluptuous as vol
# import homeassistant.helpers.config_validation as cv
# from homeassistant.const import (
#     CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_FOLDER,
#     CONF_IMAGE_OUTPUT_PATH)

# PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
#     vol.Required(CONF_HOST): cv.string,
#     vol.Required(CONF_PORT): cv.string,
#     vol.Required(CONF_USERNAME): cv.string,
#     vol.Required(CONF_PASSWORD): cv.string,
#     vol.Required(CONF_FOLDER): cv.string,
#     vol.Required(CONF_IMAGE_OUTPUT_PATH): cv.string,
# })

DOMAIN = 'mail_and_packages'

def setup(hass, config):
    """Your controller/hub specific code."""
    # Data that you want to share with your platforms
#     hass.data[DOMAIN] = {
#       'temperature': 23,
# 	  'host' = conf[CONF_HOST],
# 	  'port' = conf[CONF_PORT],
# 	  'username' = conf[CONF_USERNAME],
# 	  'password' = conf[CONF_PASSWORD],
# 	  'folder' = conf[CONF_FOLDER],
# 	  'image_output_path' = conf[CONF_IMAGE_OUTPUT_PATH]
#     }

    hass.helpers.discovery.load_platform('sensor', DOMAIN, {}, config)

    return True