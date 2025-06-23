"""Email parsing logic for Mail and Packages V2."""
import email
import logging
import quopri # For decoding quoted-printable bodies if necessary
from email.header import decode_header
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
import re
import locale
import datetime
import json # For parsing JSON-LD

_LOGGER = logging.getLogger(__name__)

# Import necessary constants for parsing. These might be extensive.
# For now, importing a few examples. This list will grow.
from .const import (
    AMAZON_PATTERN,
    AMAZON_TIME_PATTERN,
    AMAZON_LANGS,
    AMAZON_DELIVERED_SUBJECT, # Already imported but good to note
    AMAZON_IMG_PATTERN, # Already imported
    # Example: USPS_TRACKING_PATTERN,
    # Example: FEDEX_SUBJECT_DELIVERED_KEYWORDS
)

def _extract_html_payload(msg: email.message.Message) -> Optional[str]:
    """Extracts HTML payload from an email message, if available."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    html_payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    return html_payload.decode(charset, "ignore")
                except Exception as e:
                    _LOGGER.debug("Could not decode HTML part for structured data: %s", e)
                    return None
    elif msg.get_content_type() == "text/html":
        try:
            html_payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            return html_payload.decode(charset, "ignore")
        except Exception as e:
            _LOGGER.debug("Could not decode non-multipart HTML for structured data: %s", e)
            return None
    return None

def _parse_structured_data_json_ld(html_payload: str) -> List[Dict[str, Any]]:
    """Parses JSON-LD structured data from HTML payload."""
    found_data = []
    if not html_payload:
        return found_data
    try:
        soup = BeautifulSoup(html_payload, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list): # Some sites embed a list of JSON-LD objects
                    found_data.extend(data)
                else:
                    found_data.append(data)
            except json.JSONDecodeError as e:
                _LOGGER.debug("JSON-LD parsing error in script tag: %s - Content: %s", e, script.string[:200])
            except Exception as e:
                _LOGGER.debug("Error processing script tag for JSON-LD: %s", e)
    except Exception as e:
        _LOGGER.warning("Error parsing HTML for JSON-LD script tags: %s", e)
    return found_data


def get_decoded_email_subject(msg: email.message.Message) -> str:
    """Decode email subject to a string, handling potential charsets."""
    if msg["subject"] is None:
        return ""
    try:
        subject_parts = decode_header(msg["subject"])
        decoded_subject = ""
        for part_content, charset in subject_parts:
            if isinstance(part_content, bytes):
                # If charset is None, default to utf-8 as a common fallback
                actual_charset = charset if charset else "utf-8"
                try:
                    decoded_subject += part_content.decode(actual_charset, "ignore")
                except LookupError: # If charset is unknown
                    _LOGGER.warning("Unknown charset %s in subject, trying utf-8", actual_charset)
                    decoded_subject += part_content.decode("utf-8", "ignore")

            else: # Already a string (should be rare for raw email part)
                decoded_subject += part_content
        return decoded_subject.strip()
    except Exception as e:
        _LOGGER.warning("Could not decode email subject '%s': %s. Falling back to raw.", msg["subject"], e)
        return str(msg["subject"]) # Fallback to raw subject string representation

def get_email_text_content(msg: email.message.Message) -> str:
    """
    Extracts and returns the most relevant text content from an email message.
    Prefers plain text, falls back to a simplified version of HTML if plain text is not available.
    """
    plain_text_body = ""
    html_body_raw = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" not in content_disposition.lower(): # Case-insensitive check
                charset = part.get_content_charset() or "utf-8" # Default to utf-8
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        decoded_payload = payload.decode(charset, "ignore")
                        if content_type == "text/plain" and not plain_text_body: # Prioritize first plain text
                            plain_text_body = decoded_payload
                        elif content_type == "text/html" and not html_body_raw: # Store first HTML
                            html_body_raw = decoded_payload
                    except Exception as e:
                        _LOGGER.debug("Could not decode part %s with charset %s: %s", content_type, charset, e)
    else: # Not multipart
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            try:
                decoded_payload = payload.decode(charset, "ignore")
                if msg.get_content_type() == "text/plain":
                    plain_text_body = decoded_payload
                elif msg.get_content_type() == "text/html":
                    html_body_raw = decoded_payload
            except Exception as e:
                _LOGGER.debug("Could not decode non-multipart payload with charset %s: %s", charset, e)

    if plain_text_body:
        _LOGGER.debug("Using plain text body for email content.")
        return plain_text_body.strip()
    elif html_body_raw:
        _LOGGER.debug("Plain text body not found, attempting to extract text from HTML using BeautifulSoup.")
        try:
            soup = BeautifulSoup(html_body_raw, "html.parser")
            # Get text, separating by space, and strip leading/trailing whitespace
            # Remove excessive newlines and whitespace by splitting and rejoining
            text_lines = [line.strip() for line in soup.get_text(separator='\n').splitlines() if line.strip()]
            html_extracted_text = " \n".join(text_lines) # Preserve some line breaks for context
            if html_extracted_text:
                _LOGGER.debug("Successfully extracted text from HTML body.")
                return html_extracted_text
            else:
                _LOGGER.debug("BeautifulSoup extracted no text from HTML body.")
        except Exception as e:
            _LOGGER.warning("Error parsing HTML with BeautifulSoup: %s. Falling back to raw HTML.", e)
            # Fallback to raw HTML if BS4 fails, though this is less ideal for parsing
            return html_body_raw.strip()

    _LOGGER.debug("No usable text/plain or text/html body found, or HTML parsing failed to extract text.")
    return ""


def parse_amazon_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    Placeholder for parsing Amazon emails.
    In V2, this will contain the logic from 'get_items', 'amazon_search', 'get_amazon_image'.
    """
    _LOGGER.debug("Parsing Amazon email (V2 placeholder)")
    parsed_data = {
        "provider": "amazon",
        "orders": set(), # Use set for unique order numbers initially
        "deliveries_today_count": 0, # Count of items arriving today
        "estimated_delivery_date": None, # Store parsed ETA
        "tracking_numbers": set(), # Use set for unique tracking numbers
        "image_url": None, # For delivered package photos
        "is_delivered": False, # Flag if it's a delivery confirmation
    }

    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg)

        # Attempt to parse structured data first
        html_payload_for_structured_data = _extract_html_payload(msg)
        structured_datas = _parse_structured_data_json_ld(html_payload_for_structured_data)

        processed_via_structured_data = False
        for data_item in structured_datas:
            if isinstance(data_item, dict) and data_item.get("@type") in ["ParcelDelivery", "Order"]:
                _LOGGER.debug("Found structured data for ParcelDelivery/Order: %s", data_item)
                # Process this data_item to populate parsed_data
                # Example mapping from schema to our dict:
                order_info = data_item.get("partOfOrder", data_item) # Order info might be nested or top-level

                if order_info.get("orderNumber"):
                    parsed_data["orders"].add(str(order_info["orderNumber"]))

                if data_item.get("@type") == "ParcelDelivery":
                    if data_item.get("trackingNumber"):
                        parsed_data["tracking_numbers"].add(str(data_item["trackingNumber"]))

                    eta_until_str = data_item.get("expectedArrivalUntil")
                    eta_from_str = data_item.get("expectedArrivalFrom")
                    eta_to_use_str = eta_until_str or eta_from_str # Prefer 'until' if available

                    if eta_to_use_str:
                        try:
                            # Dates in schema.org are ISO 8601
                            # Example: "2027-03-12T12:00:00-08:00"
                            # Need to handle timezone offset correctly. datetime.fromisoformat handles this.
                            dt_obj = datetime.datetime.fromisoformat(eta_to_use_str.replace("Z", "+00:00"))
                            parsed_data["estimated_delivery_date"] = dt_obj.date()
                            if dt_obj.date() == datetime.date.today():
                                parsed_data["deliveries_today_count"] = len(parsed_data["orders"]) if parsed_data["orders"] else 1
                        except ValueError as ve:
                            _LOGGER.warning("Could not parse date from structured data '%s': %s", eta_to_use_str, ve)

                    delivery_status_schema = data_item.get("deliveryStatus")
                    if isinstance(delivery_status_schema, str) and "OrderDelivered" in delivery_status_schema:
                        parsed_data["is_delivered"] = True
                    # TODO: Handle deliveryStatus as a list of DeliveryEvent objects for more granular status

                    # Image URL might be in itemShipped.image
                    item_shipped = data_item.get("itemShipped")
                    if isinstance(item_shipped, dict) and item_shipped.get("image"):
                        # This is typically product image, not delivery photo.
                        # Delivery photo is not standard in ParcelDelivery schema AFAIK.
                        # We'll keep the existing regex search for delivery photos for now.
                        pass

                processed_via_structured_data = True
                # If multiple ParcelDelivery/Order objects, decide if we break or aggregate.
                # For now, assume the first relevant one is primary.
                _LOGGER.info("Successfully parsed Amazon email using structured data (JSON-LD).")
                break # Processed first valid structured data block

        if processed_via_structured_data and (parsed_data["orders"] or parsed_data["tracking_numbers"]):
            # If we got key info from structured data, we might return early
            # or supplement with regex if some fields are missing.
            # For now, if order/tracking found, consider it mostly done.
            _LOGGER.debug("Primary Amazon data extracted from JSON-LD.")
            # Fall through to regex for things not typically in schema, like delivery photo.
            # Or, if schema parsing is comprehensive, we might return here.
            # Let's allow fallback for now to catch anything missed or for delivery image.
            pass


        # Fallback or supplement with regex/text parsing
        body_text = get_email_text_content(msg)
        _LOGGER.debug("Amazon V2 Parser - Subject: %s", subject)

        # --- Order Number Extraction (if not found via structured data) ---
        if not parsed_data["orders"]:
            order_pattern = re.compile(AMAZON_PATTERN)
            subject_orders = order_pattern.findall(subject)
            body_orders = order_pattern.findall(body_text)
            for order in subject_orders + body_orders:
                parsed_data["orders"].add(order)

        # --- Delivered Status & Image (if not found or to supplement) ---
        if not parsed_data["is_delivered"] or not parsed_data["image_url"]:
            for delivered_subj_part in AMAZON_DELIVERED_SUBJECT:
                if delivered_subj_part.lower() in subject.lower():
                    if not parsed_data["is_delivered"]: # Set only if not already set by schema
                        parsed_data["is_delivered"] = True

                    if not parsed_data["image_url"]: # Attempt to find image if not in schema
                        html_payload_for_image = _extract_html_payload(msg) # Get HTML again if needed
                        if html_payload_for_image:
                            img_matches = re.findall(AMAZON_IMG_PATTERN, html_payload_for_image)
                            for img_match_groups in img_matches:
                                potential_url = "".join(filter(None,img_match_groups))
                                if "us-prod-temp.s3.amazonaws.com" in potential_url or "images-na.ssl-images-amazon.com" in potential_url:
                                    if "delivery" in potential_url.lower() or "pod" in potential_url.lower() or "order-/images/item" not in potential_url.lower() :
                                        parsed_data["image_url"] = potential_url.replace("&amp;", "&")
                                        _LOGGER.debug("Found Amazon delivery image URL via regex: %s", parsed_data["image_url"])
                                        break
                            if parsed_data["image_url"]: break
                    break

        # --- ETA (if not found via structured data or if refining) ---
        if not parsed_data["estimated_delivery_date"] and not parsed_data["is_delivered"]:
            for time_keyword in AMAZON_TIME_PATTERN:
                if time_keyword.lower() in body_text.lower():
                    # ... (rest of the existing date parsing logic remains largely the same) ...
                    # This part is complex and has been implemented. For brevity, not repeating it all.
                    # Ensure it only runs if parsed_data["estimated_delivery_date"] is still None.
                    try:
                        start_idx = body_text.lower().find(time_keyword.lower()) + len(time_keyword)
                        end_delimiters = ["track your package", "previously expected",
                                          "per tracciare il tuo pacco", "view or manage order",
                                          "track package", "\n", "<br"]
                        relevant_text_chunk = body_text[start_idx:].lstrip(": ")
                        end_idx = len(relevant_text_chunk)
                        for delim in end_delimiters:
                            found_delim_at = relevant_text_chunk.lower().find(delim.lower())
                            if found_delim_at != -1:
                                end_idx = min(end_idx, found_delim_at)
                        date_str_candidate = relevant_text_chunk[:end_idx].strip()
                        _LOGGER.debug("[Fallback] Found date string candidate: '%s'", date_str_candidate)

                        date_str_candidate = re.sub(r"\s*by\s+\d{1,2}(:\d{2})?\s*(am|pm)?", "", date_str_candidate, flags=re.IGNORECASE).strip()
                        date_str_candidate = re.sub(r"\s*between\s+\d{1,2}(:\d{2})?\s*(am|pm)?\s+and\s+\d{1,2}(:\d{2})?\s*(am|pm)?", "", date_str_candidate, flags=re.IGNORECASE).strip()
                        date_str_candidate = date_str_candidate.rstrip(',.')
                        date_parts = [part.strip() for part in date_str_candidate.split() if part.strip()]
                        if len(date_parts) >= 3 and (date_parts[0].endswith(',') or date_parts[1].endswith(',')):
                            date_to_parse = " ".join(date_parts[:3]).replace(',', '')
                        elif len(date_parts) >= 2 :
                            date_to_parse = " ".join(date_parts[:2]).replace(',', '')
                        else:
                            date_to_parse = date_str_candidate.replace(',', '')
                        _LOGGER.debug("[Fallback] Refined date string to parse: '%s'", date_to_parse)

                        parsed_dt_obj = None
                        original_locale = locale.getlocale(locale.LC_TIME)
                        for lang_locale_code in AMAZON_LANGS:
                            try:
                                locale.setlocale(locale.LC_TIME, lang_locale_code or original_locale)
                                if "today" in date_to_parse.lower() or "oggi" in date_to_parse.lower():
                                    parsed_dt_obj = datetime.date.today(); break
                                if "tomorrow" in date_to_parse.lower() or "domani" in date_to_parse.lower():
                                    parsed_dt_obj = datetime.date.today() + datetime.timedelta(days=1); break
                                possible_formats = ["%A %B %d", "%A, %B %d", "%A %d %B", "%B %d %Y", "%B %d, %Y", "%d %B %Y", "%B %d", "%d %B"]
                                for fmt in possible_formats:
                                    try:
                                        dt_obj = datetime.datetime.strptime(date_to_parse, fmt).date()
                                        current_year = datetime.date.today().year
                                        if '%Y' not in fmt:
                                            dt_obj = dt_obj.replace(year=current_year)
                                            if (datetime.date.today() - dt_obj).days > 180 and (datetime.date.today() - dt_obj).days > 0 :
                                                 dt_obj = dt_obj.replace(year=current_year + 1)
                                            elif (dt_obj - datetime.date.today()).days < -180 :
                                                 dt_obj = dt_obj.replace(year=current_year + 1)
                                        parsed_dt_obj = dt_obj; break
                                    except ValueError: continue
                                if parsed_dt_obj: break
                            except locale.Error: continue
                            finally: locale.setlocale(locale.LC_TIME, original_locale)
                        if parsed_dt_obj:
                            parsed_data["estimated_delivery_date"] = parsed_dt_obj
                            if parsed_dt_obj == datetime.date.today():
                                parsed_data["deliveries_today_count"] = len(parsed_data["orders"]) if parsed_data["orders"] else 1
                            break
                    except Exception as e_date:
                        _LOGGER.warning("[Fallback] Error processing date for keyword '%s': %s", time_keyword, e_date, exc_info=True)

        # --- Tracking Number Extraction (if not found via structured data) ---
        if not parsed_data["tracking_numbers"]:
            ups_style_tracking = re.findall(r"\b1Z[0-9A-Z]{16}\b", body_text)
            for tn in ups_style_tracking: parsed_data["tracking_numbers"].add(tn)
            # Add other generic tracking patterns if needed

        # Finalize data structure
        parsed_data["orders"] = sorted(list(parsed_data["orders"]))
        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if not parsed_data["orders"] and not parsed_data["is_delivered"] and not parsed_data["estimated_delivery_date"] and not parsed_data["tracking_numbers"]:
             _LOGGER.debug("No significant Amazon package data found in email (Subject: %s)", subject)
             return None

        return parsed_data

    except Exception as e:
        _LOGGER.error("General error parsing Amazon email: %s", e, exc_info=True)
    return None


def parse_usps_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Placeholder for parsing USPS emails."""
    _LOGGER.debug("Parsing USPS email")
    parsed_data = {
        "provider": "usps",
        "status": "unknown", # e.g., delivering, delivered, exception
        "tracking_numbers": set(),
        "mail_images": [], # List of dicts: {"filename": str, "content": bytes}
        "informed_delivery_mail_count": 0,
    }

    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()

        from .const import SENSOR_DATA # For USPS specific patterns and keywords

        # --- Package Status and Tracking ---
        usps_tracking_pattern = None
        if SENSOR_DATA.get("usps_tracking", {}).get("pattern"):
            usps_tracking_pattern = re.compile(SENSOR_DATA["usps_tracking"]["pattern"][0])

        if usps_tracking_pattern:
            tracking_in_subject = usps_tracking_pattern.findall(subject)
            tracking_in_body = usps_tracking_pattern.findall(body_text)
            for tn in tracking_in_subject + tracking_in_body:
                parsed_data["tracking_numbers"].add(tn)

        # Determine status (simplified from original get_count for USPS)
        if any(kw in subject for kw in SENSOR_DATA.get("usps_delivered", {}).get("subject", [])):
            parsed_data["status"] = "delivered"
        elif any(kw.lower() in subject for kw in SENSOR_DATA.get("usps_delivering", {}).get("subject", [])):
            parsed_data["status"] = "delivering"
        elif any(kw.lower() in subject for kw in SENSOR_DATA.get("usps_exception", {}).get("subject", [])):
            parsed_data["status"] = "exception"

        # If status is still unknown, check body for delivering keywords
        if parsed_data["status"] == "unknown" and \
           SENSOR_DATA.get("usps_delivering", {}).get("body") and \
           any(kw.lower() in body_text for kw in SENSOR_DATA["usps_delivering"]["body"]):
            parsed_data["status"] = "delivering"


        # --- Informed Delivery Mail Images (adapted from original get_mails) ---
        informed_delivery_subjects = [s.lower() for s in SENSOR_DATA.get("usps_mail", {}).get("subject", [])]
        if any(ids_subj in subject for ids_subj in informed_delivery_subjects):
            _LOGGER.debug("USPS Informed Delivery email detected: %s", subject)
            image_count = 0
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition.lower() or \
                   (part.get_filename() and part.get_filename().lower().endswith((".png", ".jpg", ".gif"))):

                    filename = part.get_filename()
                    if not filename: # Create a generic filename if not present
                        ext = ".jpg" # Default extension
                        if "png" in content_type: ext = ".png"
                        elif "gif" in content_type: ext = ".gif"
                        filename = f"mail_image_{image_count}{ext}"

                    # Skip common non-mailpiece images from USPS
                    if any(skip_name in filename.lower() for skip_name in ["mailerprovidedimage", "ra_0", "logo", "banner", "spacer"]):
                        _LOGGER.debug("Skipping likely non-mailpiece image: %s", filename)
                        continue

                    image_bytes = part.get_payload(decode=True)
                    if image_bytes:
                        parsed_data["mail_images"].append({"filename": filename, "content": image_bytes})
                        image_count += 1
                        _LOGGER.debug("Extracted mail image: %s (Size: %d bytes)", filename, len(image_bytes))

            parsed_data["informed_delivery_mail_count"] = image_count
            if image_count == 0:
                 # Check for "no mailpieces" image text in body if no attachments found
                 if "image-no-mailpieces" in body_text: # Check against the extracted text
                     parsed_data["informed_delivery_mail_count"] = 0 # Explicitly zero
                     _LOGGER.debug("USPS Informed Delivery: No actual mail pieces text/image found.")


        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        # Only return data if something meaningful was found
        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"] or parsed_data["mail_images"] or "your daily digest" in subject:
            return parsed_data
        else:
            _LOGGER.debug("No significant USPS data found in email (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing USPS email: %s", e, exc_info=True)
    return None

def parse_ups_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Placeholder for parsing UPS emails."""
    _LOGGER.debug("Parsing UPS email")
    parsed_data = {
        "provider": "ups",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()

        from .const import SENSOR_DATA

        ups_tracking_pattern_str = SENSOR_DATA.get("ups_tracking", {}).get("pattern", [None])[0]
        ups_tracking_pattern = re.compile(ups_tracking_pattern_str) if ups_tracking_pattern_str else None

        if ups_tracking_pattern:
            tracking_in_subject = ups_tracking_pattern.findall(subject)
            tracking_in_body = ups_tracking_pattern.findall(body_text)
            for tn in tracking_in_subject + tracking_in_body:
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("ups_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("ups_delivering", {}).get("subject", [])]
        exception_subjects = [s.lower() for s in SENSOR_DATA.get("ups_exception", {}).get("subject", [])]

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"
        elif any(kw in subject for kw in exception_subjects):
            parsed_data["status"] = "exception"

        # Add body text search if needed, similar to USPS, if subject is not enough

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        else:
            _LOGGER.debug("No significant UPS data found in email (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing UPS email: %s", e, exc_info=True)
    return None

def parse_fedex_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Placeholder for parsing FedEx emails."""
    _LOGGER.debug("Parsing FedEx email")
    parsed_data = {
        "provider": "fedex",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()

        from .const import SENSOR_DATA

        fedex_tracking_pattern_str = SENSOR_DATA.get("fedex_tracking", {}).get("pattern", [None])[0]
        fedex_tracking_pattern = re.compile(fedex_tracking_pattern_str) if fedex_tracking_pattern_str else None

        if fedex_tracking_pattern:
            tracking_in_subject = fedex_tracking_pattern.findall(subject)
            tracking_in_body = fedex_tracking_pattern.findall(body_text)
            for tn in tracking_in_subject + tracking_in_body:
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("fedex_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("fedex_delivering", {}).get("subject", [])]
        # FedEx exceptions are not explicitly defined in SENSOR_DATA, but could be added

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"

        # Add body text search if needed

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        else:
            _LOGGER.debug("No significant FedEx data found in email (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing FedEx email: %s", e, exc_info=True)
    return None

def parse_dhl_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses DHL emails for status and tracking numbers."""
    _LOGGER.debug("Parsing DHL email")
    parsed_data = {
        "provider": "dhl",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()

        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("dhl_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            # DHL tracking numbers can sometimes be split by spaces in emails, e.g., "12345 67890"
            # The pattern in const.py is `\d{10,11}`. We might need to pre-process body for this.
            # For now, direct regex application:
            possible_tns_subject = tracking_pattern.findall(subject)
            possible_tns_body = tracking_pattern.findall(body_text.replace(" ", "")) # Remove spaces for body search

            for tn in possible_tns_subject + possible_tns_body:
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("dhl_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("dhl_delivering", {}).get("subject", [])]

        delivered_body_keywords = [s.lower() for s in SENSOR_DATA.get("dhl_delivered", {}).get("body", [])]
        delivering_body_keywords = [s.lower() for s in SENSOR_DATA.get("dhl_delivering", {}).get("body", [])]

        if any(kw in subject for kw in delivered_subjects) or \
           any(kw in body_text for kw in delivered_body_keywords):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects) or \
             any(kw in body_text for kw in delivering_body_keywords):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        else:
            _LOGGER.debug("No significant DHL data found in email (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing DHL email: %s", e, exc_info=True)
    return None

def parse_capost_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses Canada Post emails."""
    _LOGGER.debug("Parsing Canada Post email")
    # Note: SENSOR_DATA for capost_delivering and capost_tracking is currently empty.
    # This parser will be limited until those are defined or more robust logic is added.
    parsed_data = {
        "provider": "capost",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower() # Currently not used as SENSOR_DATA is sparse

        from .const import SENSOR_DATA

        # Tracking pattern is not defined in const.py for Canada Post, so this will be empty.
        tracking_pattern_str = SENSOR_DATA.get("capost_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            tracking_in_subject = tracking_pattern.findall(subject)
            tracking_in_body = tracking_pattern.findall(body_text)
            for tn in tracking_in_subject + tracking_in_body:
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("capost_delivered", {}).get("subject", [])]
        # delivering_subjects = SENSOR_DATA.get("capost_delivering", {}).get("subject", []) # Empty in const.py

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        # No delivering subject keywords in const.py, so can't determine "delivering" status from subject alone.

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        else:
            _LOGGER.debug("No significant Canada Post data found (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing Canada Post email: %s", e, exc_info=True)
    return None


# Dispatch function
PROVIDER_KEYWORDS = {
    "amazon": ["amazon", "order-update@amazon", "shipment-tracking@amazon"],
    "usps": ["usps", "informeddelivery.usps.com", "auto-reply@usps.com"],
    "ups": ["ups.com", "mcinfo@ups.com"],
    "fedex": ["fedex.com", "trackingupdates@fedex.com"],
    "dhl": ["dhl.com", "dhl.de", "donotreply_odd@dhl.com", "noreply.odd@dhl.com"],
    "capost": ["canadapost.postescanada.ca", "donotreply@canadapost.postescanada.ca"],
    "hermes": ["myhermes.co.uk"],
    "royalmail": ["royalmail.com", "no-reply@royalmail.com"],
    "pocztapolska": ["poczta-polska.pl", "@allegromail.pl"],
    "inpostpl": ["inpost.pl", "@allegromail.pl"],
    "dpdcompl": ["dpd.com.pl", "@allegromail.pl"],
    "gls": ["gls-group.eu", "@allegromail.pl"], # GLS also uses allegromail
    "auspost": ["notifications.auspost.com.au"],
    # Add more keywords from SENSOR_DATA in const.py
}

PROVIDER_PARSERS = {
    "amazon": parse_amazon_email,
    "usps": parse_usps_email,
    "ups": parse_ups_email,
    "fedex": parse_fedex_email,
    "dhl": parse_dhl_email,
    "capost": parse_capost_email,
    "hermes": parse_hermes_email,
    "royalmail": parse_royalmail_email,
    "pocztapolska": parse_pocztapolska_email,
    "inpostpl": parse_inpostpl_email,
    "dpdcompl": parse_dpdcompl_email,
    "gls": parse_gls_email,
    "auspost": parse_auspost_email,
    # Add more parsers
}

def parse_gls_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses GLS emails."""
    _LOGGER.debug("Parsing GLS email")
    parsed_data = {
        "provider": "gls",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()
        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("gls_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            for tn in tracking_pattern.findall(subject) + tracking_pattern.findall(body_text):
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("gls_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("gls_delivering", {}).get("subject", [])]
        delivered_body = [s.lower() for s in SENSOR_DATA.get("gls_delivered", {}).get("body", [])]
        delivering_body = [s.lower() for s in SENSOR_DATA.get("gls_delivering", {}).get("body", [])]


        if any(kw in subject for kw in delivered_subjects) or \
           any(kw in body_text for kw in delivered_body):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects) or \
             any(kw in body_text for kw in delivering_body):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))
        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        _LOGGER.debug("No significant GLS data in (Subject: %s)", subject)
        return None
    except Exception as e:
        _LOGGER.error("Error parsing GLS email: %s", e, exc_info=True)
    return None

def parse_auspost_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses Australia Post emails."""
    _LOGGER.debug("Parsing AusPost email")
    parsed_data = {
        "provider": "auspost",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower() # Currently not used for AusPost by SENSOR_DATA
        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("auspost_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            # AusPost pattern can include spaces, e.g. "XXX XXX XXX" or "XX NNN NNN NNN AU"
            # The regex `\d{7,10,12}|[A-Za-z]{2}[0-9]{9}AU ` should handle this.
            for tn in tracking_pattern.findall(subject) + tracking_pattern.findall(body_text):
                parsed_data["tracking_numbers"].add(tn.strip()) # Strip any surrounding spaces from match

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("auspost_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("auspost_delivering", {}).get("subject", [])]

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))
        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        _LOGGER.debug("No significant AusPost data in (Subject: %s)", subject)
        return None
    except Exception as e:
        _LOGGER.error("Error parsing AusPost email: %s", e, exc_info=True)
    return None

def parse_pocztapolska_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses Poczta Polska emails."""
    _LOGGER.debug("Parsing Poczta Polska email")
    parsed_data = {
        "provider": "poczta_polska", # Key used in SENSOR_DATA
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()
        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("poczta_polska_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            for tn in tracking_pattern.findall(subject) + tracking_pattern.findall(body_text):
                parsed_data["tracking_numbers"].add(tn)

        # Poczta Polska only has "delivering" subjects in const.py
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("poczta_polska_delivering", {}).get("subject", [])]
        if any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))
        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        _LOGGER.debug("No significant Poczta Polska data in (Subject: %s)", subject)
        return None
    except Exception as e:
        _LOGGER.error("Error parsing Poczta Polska email: %s", e, exc_info=True)
    return None

def parse_inpostpl_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses InPost.pl emails."""
    _LOGGER.debug("Parsing InPost.pl email")
    parsed_data = {
        "provider": "inpost_pl", # Key used in SENSOR_DATA
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()
        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("inpost_pl_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            for tn in tracking_pattern.findall(subject) + tracking_pattern.findall(body_text):
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("inpost_pl_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("inpost_pl_delivering", {}).get("subject", [])]

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))
        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        _LOGGER.debug("No significant InPost.pl data in (Subject: %s)", subject)
        return None
    except Exception as e:
        _LOGGER.error("Error parsing InPost.pl email: %s", e, exc_info=True)
    return None

def parse_dpdcompl_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses DPD.com.pl emails."""
    _LOGGER.debug("Parsing DPD.com.pl email")
    parsed_data = {
        "provider": "dpd_com_pl", # Key used in SENSOR_DATA
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()
        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("dpd_com_pl_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            for tn in tracking_pattern.findall(subject) + tracking_pattern.findall(body_text):
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("dpd_com_pl_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("dpd_com_pl_delivering", {}).get("subject", [])]
        delivering_body = [s.lower() for s in SENSOR_DATA.get("dpd_com_pl_delivering", {}).get("body", [])]


        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects) or \
             any(kw in body_text for kw in delivering_body): # DPD PL uses body keywords too
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))
        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        _LOGGER.debug("No significant DPD.com.pl data in (Subject: %s)", subject)
        return None
    except Exception as e:
        _LOGGER.error("Error parsing DPD.com.pl email: %s", e, exc_info=True)
    return None

def parse_hermes_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses Hermes emails for status and tracking numbers."""
    _LOGGER.debug("Parsing Hermes email")
    parsed_data = {
        "provider": "hermes",
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()

        from .const import SENSOR_DATA

        tracking_pattern_str = SENSOR_DATA.get("hermes_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            tracking_in_subject = tracking_pattern.findall(subject)
            tracking_in_body = tracking_pattern.findall(body_text)
            for tn in tracking_in_subject + tracking_in_body:
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("hermes_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("hermes_delivering", {}).get("subject", [])]

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        else:
            _LOGGER.debug("No significant Hermes data found in email (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing Hermes email: %s", e, exc_info=True)
    return None

def parse_royalmail_email(msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Parses Royal Mail emails for status and tracking numbers."""
    _LOGGER.debug("Parsing Royal Mail email")
    parsed_data = {
        "provider": "royalmail", # Consistent key for Royal Mail
        "status": "unknown",
        "tracking_numbers": set()
    }
    try:
        msg = email.message_from_bytes(msg_bytes)
        subject = get_decoded_email_subject(msg).lower()
        body_text = get_email_text_content(msg).lower()

        from .const import SENSOR_DATA

        # SENSOR_DATA uses "royal_tracking", "royal_delivered", "royal_delivering"
        tracking_pattern_str = SENSOR_DATA.get("royal_tracking", {}).get("pattern", [None])[0]
        tracking_pattern = re.compile(tracking_pattern_str) if tracking_pattern_str else None

        if tracking_pattern:
            tracking_in_subject = tracking_pattern.findall(subject)
            tracking_in_body = tracking_pattern.findall(body_text)
            for tn in tracking_in_subject + tracking_in_body:
                parsed_data["tracking_numbers"].add(tn)

        delivered_subjects = [s.lower() for s in SENSOR_DATA.get("royal_delivered", {}).get("subject", [])]
        delivering_subjects = [s.lower() for s in SENSOR_DATA.get("royal_delivering", {}).get("subject", [])]

        if any(kw in subject for kw in delivered_subjects):
            parsed_data["status"] = "delivered"
        elif any(kw in subject for kw in delivering_subjects):
            parsed_data["status"] = "delivering"

        parsed_data["tracking_numbers"] = sorted(list(parsed_data["tracking_numbers"]))

        if parsed_data["status"] != "unknown" or parsed_data["tracking_numbers"]:
            return parsed_data
        else:
            _LOGGER.debug("No significant Royal Mail data found in email (Subject: %s)", subject)
            return None

    except Exception as e:
        _LOGGER.error("Error parsing Royal Mail email: %s", e, exc_info=True)
    return None

def identify_and_parse_email(email_content_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    Identifies the email provider and calls the specific parser.
    """
    try:
        msg = email.message_from_bytes(email_content_bytes)
        subject = get_decoded_email_subject(msg)
        # Try to get sender from 'From' header
        from_header = msg.get("From", "")
        sender_email_match = re.search(r'<([^>]+)>', from_header) # Extract email from <...>
        sender_domain = sender_email_match.group(1).lower() if sender_email_match else from_header.lower()

        _LOGGER.debug("Attempting to identify email from sender domain: '%s', subject: '%s'", sender_domain, subject)

        for provider, keywords in PROVIDER_KEYWORDS.items():
            for keyword in keywords:
                if keyword in sender_domain or keyword in subject.lower():
                    _LOGGER.info("Identified email as %s provider.", provider)
                    parser_func = PROVIDER_PARSERS.get(provider)
                    if parser_func:
                        return parser_func(email_content_bytes)
                    else:
                        _LOGGER.warning("No parser found for identified provider: %s", provider)
                        return None

        _LOGGER.debug("Email did not match known provider keywords for parsing.")
        return None

    except Exception as e:
        _LOGGER.error("Error during email identification or initial parsing: %s", e, exc_info=True)
        return None

# This initial structure provides a framework.
# Step 2 will involve migrating the detailed parsing logic from the original
# helpers.py into these respective parse_xxx_email functions.
# BeautifulSoup4 will be integrated for robust HTML processing.
# Date parsing in parse_amazon_email is currently a very basic placeholder.
# Error handling with exc_info=True is added for better debugging.
# Improved get_email_text_content to prioritize plain text and handle charsets better.
# Improved identify_and_parse_email to use sender domain and subject for identification.
