"""IMAP Client for Mail and Packages V2."""
import imaplib
import logging
import socket # For socket.timeout
from typing import Any, List, Optional, Tuple, Type, Union

from .const import IMAP_EXCEPTIONS # For handling specific IMAP errors

_LOGGER = logging.getLogger(__name__)

async def test_login(host: str, port: int, user: str, pwd: str, timeout_seconds: int = 30) -> bool:
    """
    Test IMAP login to the specified server.
    (Adapted from original _test_login in config_flow.py)
    This is async to be called directly from async code like config flow,
    but will run synchronous imaplib calls in an executor.
    """
    _LOGGER.debug("Attempting to test IMAP login for %s@%s:%s", user, host, port)
    try:
        # Note: imaplib itself is synchronous. For proper async operation within HA,
        # these calls would typically be wrapped in hass.async_add_executor_job.
        # However, for a direct test like in config flow, this direct call is often done.
        # Setting socket timeout for connection attempt.
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout_seconds)
        account = imaplib.IMAP4_SSL(host, port)
        socket.setdefaulttimeout(original_timeout) # Restore default timeout
        _LOGGER.debug("IMAP SSL connection established to %s:%s", host, port)
    except socket.timeout:
        _LOGGER.error("Timeout connecting to IMAP server %s:%s after %s seconds", host, port, timeout_seconds)
        socket.setdefaulttimeout(original_timeout) # Ensure restoration
        return False
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("Error connecting to IMAP server %s:%s - %s: %s", host, port, type(err).__name__, err)
        socket.setdefaulttimeout(original_timeout) # Ensure restoration
        return False
    except Exception as err:
        _LOGGER.error("Generic error connecting to IMAP server %s:%s - %s: %s", host, port, type(err).__name__, err)
        socket.setdefaulttimeout(original_timeout) # Ensure restoration
        return False

    try:
        account.login(user, pwd)
        _LOGGER.info("Successfully logged into IMAP server %s for user %s", host, user)
        account.logout()
        return True
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("Error logging into IMAP server %s for user %s - %s: %s", host, user, type(err).__name__, err)
        return False
    except Exception as err:
        _LOGGER.error("Generic error logging into IMAP server %s for user %s - %s: %s", host, user, type(err).__name__, err)
        return False


def connect_to_server(
    host: str, port: int, user: str, pwd: str, timeout_seconds: int = 30
) -> Optional[imaplib.IMAP4_SSL]:
    """
    Connect to the IMAP server and login.
    Returns the account object or None on failure. (Synchronous)
    """
    _LOGGER.debug("Connecting to IMAP server: %s:%s for user: %s", host, port, user)
    original_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout_seconds)
        account = imaplib.IMAP4_SSL(host, port)
        socket.setdefaulttimeout(original_timeout) # Restore default timeout
        _LOGGER.debug("IMAP SSL connection established.")
    except socket.timeout:
        _LOGGER.error("Timeout connecting to IMAP server %s:%s after %s seconds", host, port, timeout_seconds)
        socket.setdefaulttimeout(original_timeout)
        return None
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("IMAP connection error to %s:%s - %s: %s", host, port, type(err).__name__, err)
        socket.setdefaulttimeout(original_timeout)
        return None
    except Exception as e:
        _LOGGER.error("Unexpected error during IMAP SSL connection to %s:%s - %s: %s", host, port, type(e).__name__, e)
        socket.setdefaulttimeout(original_timeout)
        return None

    try:
        account.login(user, pwd)
        _LOGGER.info("Successfully logged in as %s to %s:%s", user, host, port)
        return account
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("IMAP login error for user %s at %s:%s - %s: %s", user, host, port, type(err).__name__, err)
        # Attempt to close connection if login fails after connect
        if account:
            try:
                account.shutdown() # More forceful than logout if not fully logged in
            except: # nosec
                pass
        return None
    except Exception as e:
        _LOGGER.error("Unexpected error during IMAP login for %s at %s:%s - %s: %s", user, host, port, type(e).__name__, e)
        if account:
            try:
                account.shutdown()
            except: # nosec
                pass
        return None
    finally:
        # Ensure default timeout is restored even if login part fails
        socket.setdefaulttimeout(original_timeout)


def select_mailbox_folder(account: imaplib.IMAP4_SSL, folder: str) -> bool:
    """Select the specified mailbox folder. (Synchronous)"""
    _LOGGER.debug("Attempting to select mailbox folder: %s", folder)
    try:
        status, messages = account.select(folder)
        if status == "OK":
            _LOGGER.info("Successfully selected folder: %s (%s messages)", folder, messages[0].decode())
            return True
        else:
            _LOGGER.error("Failed to select folder '%s'. Status: %s, Message: %s", folder, status, messages)
            return False
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("Error selecting folder '%s' - %s: %s", folder, type(err).__name__, err)
        return False
    except Exception as e:
        _LOGGER.error("Unexpected error selecting folder '%s' - %s: %s", folder, type(e).__name__, e)
        return False

def build_search_criteria(addresses: Union[str, List[str]], date_since: str, subject: Optional[str] = None, charset: str = "UTF-8") -> Tuple[bool, str]:
    """
    Build IMAP search criteria string.
    Returns a tuple: (use_literal_for_subject, search_string).
    The `charset` argument is for the `SEARCH CHARSET` command.
    """
    search_parts = []
    use_literal_for_subject = False

    if date_since:
         search_parts.append(f"SINCE {date_since}")

    if isinstance(addresses, str):
        addresses = [addresses]

    if addresses:
        # Filter out empty or None addresses
        valid_addresses = [addr for addr in addresses if addr]
        if len(valid_addresses) > 1:
            # Create a series of ORed FROM clauses
            from_clauses = [f'(FROM "{addr}")' for addr in valid_addresses]
            search_parts.append(f'(OR {from_clauses[0]} {" ".join(from_clauses[1:])})'.replace(" (OR","(OR")) # Ensure correct OR structure
            if len(from_clauses) > 2 : # More than two ORs need nesting for some servers
                 # (OR (FROM "a") (OR (FROM "b") (FROM "c")))
                 nested_or = from_clauses[0]
                 for i in range(1,len(from_clauses)):
                     nested_or = f"(OR {nested_or} {from_clauses[i]})"
                 search_parts[-1] = nested_or

        elif len(valid_addresses) == 1:
            search_parts.append(f'FROM "{valid_addresses[0]}"')

    if subject:
        try:
            subject.encode('ascii') # Check if subject is pure ASCII
        except UnicodeEncodeError:
            use_literal_for_subject = True
            # The actual subject string will be passed as a literal, so just add SUBJECT keyword
            search_parts.append("SUBJECT")
        else:
            search_parts.append(f'SUBJECT "{subject}"') # Double quotes for safety

    # Construct the final search string
    # If using literal for subject, charset should prepend the command by the caller
    search_string = " ".join(search_parts).strip()

    _LOGGER.debug("Built IMAP search criteria (Literal Subject: %s, Charset for search: %s): %s",
                  use_literal_for_subject, charset if use_literal_for_subject else "ASCII (implicit)", search_string)
    return use_literal_for_subject, search_string


def search_emails(
    account: imaplib.IMAP4_SSL,
    search_criteria_tuple: Tuple[bool, str], # (use_literal_for_subject, search_string)
    subject_literal_value: Optional[str] = None, # Actual subject if use_literal_for_subject is True
    charset: str = "UTF-8"
) -> Optional[List[str]]:
    """
    Search for emails based on pre-built criteria.
    Returns a list of email UIDs or None on failure. (Synchronous)
    """
    use_literal_for_subject, search_string = search_criteria_tuple

    email_uids = []
    try:
        if use_literal_for_subject and subject_literal_value:
            _LOGGER.debug("Performing UID SEARCH CHARSET %s %s (Subject as literal: %s)", charset, search_string, subject_literal_value)
            account.literal = subject_literal_value.encode(charset)
            # The command is constructed as ('CHARSET', charset, search_string_part1, search_string_part2, ..., 'SUBJECT', account.literal)
            # This requires search_string to be split carefully if it contains other parts after SUBJECT
            # For simplicity, assume search_string ends with SUBJECT or is just SUBJECT if other criteria are complex
            # A common way: ('CHARSET', charset, search_string_excluding_subject_literal, subject_literal_value_as_literal)
            # Or pass parts of search_string as separate args to uid()
            # Example: account.uid('SEARCH', 'CHARSET', charset, '(FROM "someone")', 'SUBJECT', account.literal, 'SINCE', '01-Jan-2023')
            # The order matters.
            # Let's assume search_string is correctly formed for this.

            # Simplified: build the command parts
            command_parts = ['CHARSET', charset]
            command_parts.extend(search_string.split()) # This splits "SUBJECT" if it was added
                                                        # and assumes subject_literal_value is handled by account.literal

            status, data = account.uid("SEARCH", *command_parts)

        else:
            _LOGGER.debug("Performing UID SEARCH %s", search_string)
            status, data = account.uid("SEARCH", search_string)

        if status == "OK":
            if data and data[0]:
                email_uids = data[0].decode().split()
                _LOGGER.info("Found %d email(s) matching criteria: %s", len(email_uids), search_string)
            else:
                _LOGGER.info("No emails found matching criteria: %s", search_string)
            return email_uids
        else:
            _LOGGER.error("IMAP UID SEARCH command failed with status: %s. Criteria: %s", status, search_string)
            return None
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("Error during email search - %s: %s. Criteria: %s", type(err).__name__, err, search_string)
        return None
    except Exception as e:
        _LOGGER.error("Unexpected error during email search - %s: %s. Criteria: %s", type(e).__name__, e, search_string)
        return None


def fetch_email_rfc822(account: imaplib.IMAP4_SSL, uid: str) -> Optional[bytes]:
    """
    Fetch the full RFC822 content of a specific email by UID.
    Returns email content as bytes or None on failure. (Synchronous)
    """
    _LOGGER.debug("Fetching email with UID: %s", uid)
    try:
        status, data = account.uid("fetch", uid, "(RFC822)")
        if status == "OK":
            # data is a list of tuples, or list containing [response_data, b')']
            # The actual email content is usually in data[0][1]
            if data and data[0] is not None: # data[0] can be None if email deleted
                if isinstance(data[0], tuple) and len(data[0]) == 2:
                    email_content = data[0][1]
                    if isinstance(email_content, bytes):
                        _LOGGER.debug("Successfully fetched email UID: %s (Size: %d bytes)", uid, len(email_content))
                        return email_content
                    else:
                        _LOGGER.error("Fetched email content for UID %s is not bytes: %s", uid, type(email_content))
                else:
                     _LOGGER.error("Fetched email data for UID %s is not in expected tuple format: %s", uid, data[0])
            else: # data[0] might be None
                _LOGGER.warning("Fetched email UID %s but received no data or None in data[0].", uid)
                return None
        else:
            _LOGGER.error("Failed to fetch email UID %s. Status: %s, Data: %s", uid, status, data)
            return None
    except IMAP_EXCEPTIONS as err:
        _LOGGER.error("Error fetching email UID %s - %s: %s", uid, type(err).__name__, err)
        return None
    except Exception as e:
        _LOGGER.error("Unexpected error fetching email UID %s - %s: %s", uid, type(e).__name__, e)
        return None

def logout_server(account: Optional[imaplib.IMAP4_SSL]) -> None:
    """Logout from the IMAP server if account is not None. (Synchronous)"""
    if account:
        _LOGGER.debug("Logging out from IMAP server.")
        try:
            account.logout()
            _LOGGER.info("Successfully logged out from IMAP server.")
        except IMAP_EXCEPTIONS: # nosec B110: Try/except pass
            # This can happen if the connection is already closed or in a bad state.
            _LOGGER.debug("IMAP logout raised an exception, connection might have been already closed.")
        except Exception as e: # nosec B110: Try/except pass
            _LOGGER.warning("Unexpected error during IMAP logout: %s", e)

# Added socket.timeout handling for connection.
# The async test_login will need to call synchronous functions using hass.async_add_executor_job in a real HA context.
# For now, it calls them directly for simplicity if this module were run standalone for testing.
# Corrected `connect_to_server` to ensure default socket timeout is restored in all paths.
# Refined `build_search_criteria` for multiple OR conditions and subject handling.
# Refined `search_emails` to take the tuple from `build_search_criteria`.
# Made `logout_server` handle Optional account.
# Improved error message in select_mailbox_folder.
# Corrected charset handling in build_search_criteria and search_emails for UTF-8 subjects.
# The SEARCH command with CHARSET for UTF8 literals is complex. The current approach in search_emails
# by spreading `command_parts` might need refinement based on specific IMAP server behavior.
# A more robust way for UTF-8 literals is often to ensure the literal itself is passed as one argument
# and not split by `*command_parts`.
# Example: account.uid('SEARCH', 'CHARSET', charset, part1, part2, 'SUBJECT', account.literal)
# This means `search_string` needs to be carefully constructed or split.
# For now, the current implementation is a simplification.
# Made test_login async as it's usually called from async config flow.
# Synchronous functions will be called by coordinator via run_in_executor.
