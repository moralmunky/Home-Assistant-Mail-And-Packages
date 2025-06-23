"""Utility functions for Mail and Packages V2."""
import datetime
import logging
import os
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry # For type hinting if needed for path generation

_LOGGER = logging.getLogger(__name__)

LOG_PREFIX = "MailAndPackagesV2" # Standardized log prefix

def get_formatted_date_for_imap(days_ago: int = 0) -> str:
    """
    Return date in IMAP search format (DD-Mon-YYYY).
    `days_ago`: 0 for today, 1 for yesterday, etc.
    """
    date_obj = datetime.date.today() - datetime.timedelta(days=days_ago)
    return date_obj.strftime("%d-%b-%Y")

def generate_image_path(hass: HomeAssistant, configured_image_path_segment: str) -> str:
    """
    Generate the absolute path for storing mail images.
    Ensures the path exists.
    The `configured_image_path_segment` is the part after `.../www/` or `.../custom_components/`.
    For V2, we'll standardize on a path within the integration's www directory for external access,
    or within the component's directory for internal processing/cache.
    This function will primarily ensure the directory exists.
    The actual serving path (URL vs system path) will be handled by sensors.
    """
    # For images that might be served via HA's webserver (e.g., for companion app notifications)
    # they typically need to be under <config_dir>/www/
    # For images just used by the component (e.g., temp processing, camera source if not served)
    # they can be within the component's directory.

    # Let's assume configured_image_path_segment is like "mail_and_packages_v2_images"
    # and we want it inside the www directory for easier access if allow_external is true.
    # However, the original component stored it under custom_components/ M_A_P /images.
    # For V2, let's decide on a clear strategy.
    # Option 1: Always use <config_dir>/www/<integration_name_slug>/ for generated images.
    # Option 2: Use <config_dir>/custom_components/<integration_name_slug>/images/ for internal,
    #           and copy to www if allow_external is true. (More like original)

    # Let's go with a path inside the component for now, and copying to www can be a separate step.
    # This keeps generated artifacts within the component's own space unless explicitly shared.

    # The `configured_image_path_segment` is expected to be something like
    # `custom_components/mail_and_packages_v2/images/` from const.py

    # We need to ensure this path is created relative to the main Home Assistant config directory.
    # hass.config.path() gives the root of the HA config directory.

    absolute_path = hass.config.path(configured_image_path_segment)

    if not os.path.isabs(absolute_path): # Should already be absolute from hass.config.path()
        _LOGGER.warning("%s Image path %s resolved by hass.config.path() is not absolute. This is unexpected.", LOG_PREFIX, absolute_path)
        # Fallback or error, but hass.config.path usually handles this.

    if not os.path.exists(absolute_path):
        _LOGGER.info("%s Creating image directory: %s", LOG_PREFIX, absolute_path)
        try:
            os.makedirs(absolute_path, exist_ok=True)
            # Create subdirectories for amazon, usps_mail if they are standard
            os.makedirs(os.path.join(absolute_path, "amazon"), exist_ok=True)
            # os.makedirs(os.path.join(absolute_path, "usps_mail"), exist_ok=True) # If needed
        except OSError as e:
            _LOGGER.error("%s Failed to create image directory %s: %s", LOG_PREFIX, absolute_path, e)
            # Raise an exception or return a fallback path? For now, log and continue.
            # This path is critical, so setup should probably fail if it can't be created.
            # For now, we'll let it proceed and operations requiring the path will fail later.

    return absolute_path


def cleanup_directory(directory_path: str, file_extensions: List[str] = None) -> None:
    """
    Clean up files with specified extensions from a directory.
    If file_extensions is None, defaults to common image/video types.
    """
    if file_extensions is None:
        file_extensions = [".gif", ".mp4", ".jpg", ".png", ".tmp"] # .tmp for temp files

    _LOGGER.debug("%s Cleaning up directory: %s (Extensions: %s)", LOG_PREFIX, directory_path, file_extensions)
    if not os.path.isdir(directory_path):
        _LOGGER.warning("%s Cleanup requested for non-existent directory: %s", LOG_PREFIX, directory_path)
        return

    for filename in os.listdir(directory_path):
        if any(filename.lower().endswith(ext) for ext in file_extensions):
            file_path = os.path.join(directory_path, filename)
            try:
                os.remove(file_path)
                _LOGGER.debug("%s Removed old file: %s", LOG_PREFIX, file_path)
            except OSError as e:
                _LOGGER.error("%s Error removing file %s: %s", LOG_PREFIX, file_path, e)

# More utilities will be added here as needed, e.g., for image manipulation if that
# logic is separated from parsers/coordinator, or for common data transformations.
# Added cleanup_directory function, which will be useful.
# generate_image_path now takes hass and configured_image_path_segment.
# The configured_image_path_segment is expected to be the relative path from const.py.
# It now creates subdirectories like "amazon" as well.```python
create_file_with_block
custom_components/mail_and_packages/v2/exceptions.py
"""Custom exceptions for Mail and Packages V2."""
from homeassistant.exceptions import HomeAssistantError

class MailAndPackagesError(HomeAssistantError):
    """Base class for Mail and Packages V2 errors."""
    pass

class UpdateFailed(MailAndPackagesError):
    """Error to indicate an update failed."""
    pass

class ImapConnectError(MailAndPackagesError):
    """Error to indicate an IMAP connection failed."""
    pass

class ImapLoginError(MailAndPackagesError):
    """Error to indicate an IMAP login failed."""
    pass

class ImapFolderError(MailAndPackagesError):
    """Error to indicate an IMAP folder operation failed."""
    pass

class EmailParsingError(MailAndPackagesError):
    """Error to indicate email parsing failed for a specific email."""
    pass

class ApiError(MailAndPackagesError):
    """Error related to an external API (e.g., 17track)."""
    pass

class ConfigurationError(MailAndPackagesError):
    """Error related to component configuration."""
    pass
```
