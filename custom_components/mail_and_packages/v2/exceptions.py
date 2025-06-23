"""Custom exceptions for Mail and Packages V2."""
from homeassistant.exceptions import HomeAssistantError

class MailAndPackagesError(HomeAssistantError):
    """Base class for Mail and Packages V2 errors."""
    pass

class UpdateFailed(MailAndPackagesError):
    """Error to indicate an update failed. Typically wraps a lower-level exception."""
    pass

class ImapConnectError(MailAndPackagesError):
    """Error to indicate an IMAP connection failed."""
    pass

class ImapLoginError(MailAndPackagesError):
    """Error to indicate an IMAP login failed."""
    pass

class ImapFolderError(MailAndPackagesError):
    """Error to indicate an IMAP folder operation (e.g., select) failed."""
    pass

class ImapSearchError(MailAndPackagesError):
    """Error to indicate an IMAP search operation failed."""
    pass

class ImapFetchError(MailAndPackagesError):
    """Error to indicate an IMAP fetch operation failed."""
    pass

class EmailParsingError(MailAndPackagesError):
    """Error to indicate email parsing failed for a specific email."""
    pass

class ApiError(MailAndPackagesError):
    """Error related to an external API (e.g., 17track)."""
    pass

class ConfigurationError(MailAndPackagesError):
    """Error related to component configuration not being valid."""
    pass

class FileOperationError(MailAndPackagesError):
    """Error related to file operations (e.g., creating image directory, saving image)."""
    pass
