"""Tests for email_parser.py in V2."""
import unittest
from unittest.mock import MagicMock, patch
import email # Python's built-in email module

# Assuming the new v2 path for these modules:
from custom_components.mail_and_packages.v2.email_parser import (
    get_decoded_email_subject,
    get_email_text_content,
    parse_amazon_email,
    _extract_html_payload, # For testing structured data extraction helper
    _parse_structured_data_json_ld # For testing structured data extraction helper
)
from custom_components.mail_and_packages.v2.const import AMAZON_TIME_PATTERN, AMAZON_LANGS, AMAZON_PATTERN

# Helper to load .eml files
TEST_EMAIL_DIR = "tests/test_emails" # Relative to repo root

def load_eml_file(filename: str) -> email.message.Message:
    """Loads an .eml file and returns an email.message.Message object."""
    eml_path = f"{TEST_EMAIL_DIR}/{filename}"
    with open(eml_path, 'rb') as f:
        return email.message_from_bytes(f.read())

def load_eml_as_bytes(filename: str) -> bytes:
    """Loads an .eml file and returns its byte content."""
    eml_path = f"{TEST_EMAIL_DIR}/{filename}"
    with open(eml_path, 'rb') as f:
        return f.read()

class TestEmailParserUtils(unittest.TestCase):
    """Test utility functions in email_parser."""

    def test_get_decoded_email_subject(self):
        """Test decoding of email subjects."""
        msg = email.message.Message()

        # Test ASCII subject
        msg.replace_header("Subject", "Simple Subject")
        self.assertEqual(get_decoded_email_subject(msg), "Simple Subject")

        # Test UTF-8 encoded subject (common case)
        # "Package Update – 25"
        msg.replace_header("Subject", "=?UTF-8?B?UMOkY2thZ2UgVXBkYXRlIOKAkSAyNQ==?=")
        self.assertEqual(get_decoded_email_subject(msg), "Package Update – 25")

        # Test ISO-8859-1 encoded subject
        # "Prüfung abgeschlossen"
        msg.replace_header("Subject", "=?ISO-8859-1?Q?Pr=FCfung_abgeschlossen?=")
        self.assertEqual(get_decoded_email_subject(msg), "Prüfung abgeschlossen")

        # Test subject with multiple encoded parts
        # "Re: Hallo world"
        msg.replace_header("Subject", "=?UTF-8?B?UmU6IA==?= =?UTF-8?B?SGFsbG8gd29ybGQ=?=")
        self.assertEqual(get_decoded_email_subject(msg), "Re: Hallo world")

        # Test empty subject
        msg.replace_header("Subject", "")
        self.assertEqual(get_decoded_email_subject(msg), "")

        # Test None subject (header not present)
        del msg["Subject"] # Remove header
        self.assertEqual(get_decoded_email_subject(msg), "")

    def test_get_email_text_content_plain_text(self):
        """Test extraction of plain text content."""
        msg = email.message.Message()
        plain_body = "This is a plain text body.\nWith two lines."
        # Set payload with specific charset encoding
        msg.set_payload(plain_body.encode('utf-8'), charset='utf-8')
        # msg.set_type("text/plain") # set_payload with charset implies text/*
        del msg["Content-Type"] # Remove default before setting new one
        msg["Content-Type"] = 'text/plain; charset="utf-8"'

        self.assertEqual(get_email_text_content(msg), plain_body)

    @patch('custom_components.mail_and_packages.v2.email_parser.BeautifulSoup')
    def test_get_email_text_content_html_only(self, mock_bs):
        """Test extraction from HTML content using BeautifulSoup."""
        msg = email.message.Message()
        html_content = "<html><body><p>Hello <b>World</b>!</p><div>Another line.</div></body></html>"
        msg.set_payload(html_content.encode('utf-8'), charset='utf-8')
        del msg["Content-Type"]
        msg["Content-Type"] = 'text/html; charset="utf-8"'

        mock_soup_instance = MagicMock()
        # Simulate BeautifulSoup's get_text behavior
        mock_soup_instance.get_text.return_value = "Hello World!\nAnother line."
        mock_bs.return_value = mock_soup_instance

        self.assertEqual(get_email_text_content(msg), "Hello World! \nAnother line.")
        mock_bs.assert_called_once_with(html_content, "html.parser")
        # get_text is called with separator='\n', then lines are stripped and joined with " \n"
        mock_soup_instance.get_text.assert_called_once_with(separator='\n')


    @patch('custom_components.mail_and_packages.v2.email_parser.BeautifulSoup')
    def test_get_email_text_content_multipart_prefer_plain(self, mock_bs):
        """Test multipart email prefers plain text."""
        msg = email.message.Message()
        msg.set_type("multipart/alternative")

        plain_part = email.message.Message()
        plain_body = "Plain text version."
        plain_part.set_payload(plain_body.encode('utf-8'), charset='utf-8')
        del plain_part["Content-Type"]
        plain_part["Content-Type"] = 'text/plain; charset="utf-8"'
        msg.attach(plain_part)

        html_part = email.message.Message()
        html_part.set_payload("<html><body><p>HTML version.</p></body></html>".encode('utf-8'), charset='utf-8')
        del html_part["Content-Type"]
        html_part["Content-Type"] = 'text/html; charset="utf-8"'
        msg.attach(html_part)

        self.assertEqual(get_email_text_content(msg), plain_body)
        mock_bs.assert_not_called() # BeautifulSoup should not be called if plain text is found

    @patch('custom_components.mail_and_packages.v2.email_parser.BeautifulSoup')
    def test_get_email_text_content_multipart_html_fallback(self, mock_bs):
        """Test multipart email falls back to HTML if no plain text."""
        msg = email.message.Message()
        msg.set_type("multipart/alternative")

        html_content = "<html><body>HTML <b>only</b> here.</body></html>"
        html_part = email.message.Message()
        html_part.set_payload(html_content.encode('utf-8'), charset='utf-8')
        del html_part["Content-Type"]
        html_part["Content-Type"] = 'text/html; charset="utf-8"'
        msg.attach(html_part)

        mock_soup_instance = MagicMock()
        mock_soup_instance.get_text.return_value = "HTML\nonly\nhere."
        mock_bs.return_value = mock_soup_instance

        self.assertEqual(get_email_text_content(msg), "HTML \nonly \nhere.")
        mock_bs.assert_called_once_with(html_content, "html.parser")
        mock_soup_instance.get_text.assert_called_once_with(separator='\n')

    def test_get_email_text_content_no_text_parts(self):
        """Test email with no text/plain or text/html parts."""
        msg = email.message.Message()
        msg.set_type("multipart/mixed")

        img_part = email.message.Message()
        img_part.set_type("image/jpeg")
        img_part.add_header("Content-Disposition", "attachment", filename="image.jpg")
        # Setting a dummy payload for the image part
        img_part.set_payload(b"dummyimagedata")
        msg.attach(img_part)

        self.assertEqual(get_email_text_content(msg), "")

class TestAmazonParser(unittest.TestCase):
    """Test the Amazon email parser."""

    def test_parse_amazon_shipped_email_regex_fallback(self):
        """Test parsing a standard Amazon shipped email (regex fallback)."""
        # This email (amazon_shipped.eml) does not contain JSON-LD structured data,
        # so it will test the regex/text parsing fallback.
        email_bytes = load_eml_as_bytes("amazon_shipped.eml")
        parsed_data = parse_amazon_email(email_bytes)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data["provider"], "amazon")
        self.assertIn("123-1234567-1234567", parsed_data["orders"]) # From subject
        self.assertIn("113-5838173-8241820", parsed_data["orders"]) # From body in this specific test file

        # Expected date from "Friday, September 11"
        # Assuming current year is not 2020, this will be handled by year adjustment.
        # For consistent testing, we mock datetime.date.today().
        # The email is from Sep 2020. Let's assume "today" is also in Sep 2020 for this test.
        with patch('custom_components.mail_and_packages.v2.email_parser.datetime.date') as mock_date:
            mock_date.today.return_value = datetime.date(2020, 9, 10) # Day before delivery
            mock_date.side_effect = lambda *args, **kwargs: datetime.date(*args, **kwargs) # Allow date constructor

            # Re-parse with mocked date if parser uses today() for year context
            # Note: parse_amazon_email itself doesn't directly call today() for year if year is absent in strptime,
            # but the logic for "today" keyword does. This email doesn't use "today" keyword.
            # The year adjustment logic (if year == 1900) is the main part affected.

            # Re-running parsing inside mock if it's essential for the tested logic path
            # For this specific email, the date "Friday, September 11" should parse okay
            # but year handling can be tricky. If it assumes current year, test might fail in future.
            # The parser's year adjustment logic tries to handle this.
            # Let's assume the parser's year logic is robust enough for now, or refine it.
            # If year is parsed as 1900, it's replaced with today's year.
            # If current year is 2024, "September 11" becomes "September 11, 2024".
            # This is fine if we are just checking a date is found.
            # For specific date match:
            # For "Friday, September 11" from a 2020 email:
            # If we run test in 2024, it will parse as Sep 11, 2024.
            # If we want to assert datetime.date(2020, 9, 11), the parser would need awareness of email date
            # or the test must mock 'today' to be in 2020.

            # Let's test the actual parsed date based on how the current parser logic works
            # without specific mocking of 'today' for this particular regex test,
        # The email is from Sep 2020.
        # To test date parsing accurately, especially year handling, mock datetime.date.today().
        with patch('custom_components.mail_and_packages.v2.email_parser.datetime.date') as mock_date:
            mock_date.today.return_value = datetime.date(2020, 9, 10)  # Set "today" to be just before the email's date
            mock_date.side_effect = lambda *args, **kwargs: datetime.date(*args, **kwargs) # Allow date constructor

            # Re-parse with the mocked date
            email_bytes_reloaded = load_eml_as_bytes("amazon_shipped.eml")
            parsed_data_reloaded = parse_amazon_email(email_bytes_reloaded)

            self.assertIsNotNone(parsed_data_reloaded)
            self.assertEqual(parsed_data_reloaded["estimated_delivery_date"], datetime.date(2020, 9, 11))
            self.assertEqual(parsed_data_reloaded["deliveries_today_count"], 0) # Not for mocked 'today'
            self.assertFalse(parsed_data_reloaded["is_delivered"])
        self.assertIsNone(parsed_data["image_url"])
        # This basic email doesn't have explicit non-Amazon tracking numbers
        self.assertEqual(len(parsed_data.get("tracking_numbers", [])), 0)


    def test_parse_amazon_delivered_email_regex_fallback(self):
        """Test parsing a standard Amazon delivered email (regex fallback)."""
        email_bytes = load_eml_as_bytes("amazon_delivered.eml")
        parsed_data = parse_amazon_email(email_bytes)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data["provider"], "amazon")
        self.assertIn("123-1234567-1234567", parsed_data["orders"])
        self.assertTrue(parsed_data["is_delivered"])
        self.assertIsNotNone(parsed_data["image_url"])
        self.assertTrue("us-prod-temp.s3.amazonaws.com" in parsed_data["image_url"])
        self.assertEqual(parsed_data["deliveries_today_count"], 0) # is_delivered, so not an ETA for today
        self.assertIsNone(parsed_data["estimated_delivery_date"]) # No ETA in delivered emails typically

    def test_parse_amazon_shipped_italian_regex_fallback(self):
        """Test Italian Amazon shipped email (regex fallback)."""
        email_bytes = load_eml_as_bytes("amazon_shipped_it.eml")
        # Mock datetime.date.today for consistent year handling if needed, e.g. for 2020 emails
        # with patch('custom_components.mail_and_packages.v2.email_parser.datetime.date') as mock_date:
        #     mock_date.today.return_value = datetime.date(2020, 11, 28) # A date before Dec 1 2020
        #     mock_date.side_effect = lambda *args, **kwargs: datetime.date(*args, **kwargs) # Allow date constructor
        parsed_data = parse_amazon_email(email_bytes)

        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data["provider"], "amazon")
        self.assertIn("405-5236882-9395563", parsed_data["orders"])
        self.assertIsNotNone(parsed_data["estimated_delivery_date"])
        # Expected: "martedì 01 dicembre" -> date(YEAR, 12, 1)
        # self.assertEqual(parsed_data["estimated_delivery_date"], datetime.date(2020, 12, 1)) # If mocking date
        # _LOGGER.debug("Italian Shipped Parsed Date: %s", parsed_data["estimated_delivery_date"])


    def create_mock_json_ld_email(self, json_ld_data_list, subject="Test Subject with JSON-LD") -> bytes:
        """Creates a mock email with embedded JSON-LD."""
        msg = email.message.Message()
        msg["Subject"] = subject
        msg["From"] = "sender@example.com"
        msg["To"] = "receiver@example.com"

        scripts_html = ""
        for json_ld_data in json_ld_data_list:
            scripts_html += f'<script type="application/ld+json">{json.dumps(json_ld_data)}</script>\n'

        html_body = f"""
        <html>
          <head>{scripts_html}</head>
          <body>
            <p>This email contains structured data.</p>
            <p>Order Number: 789-0123456-7890123</p> <!-- Fallback data -->
            <p>Arriving: tomorrow</p> <!-- Fallback data -->
          </body>
        </html>
        """
        # Create a multipart/alternative message
        multi_part_msg = email.message.Message()
        multi_part_msg.set_type("multipart/alternative")
        multi_part_msg["Subject"] = subject
        multi_part_msg["From"] = "sender@example.com"
        multi_part_msg["To"] = "receiver@example.com"

        # Plain text part (can be minimal)
        plain_part = email.message.Message()
        plain_part.set_payload("This email contains structured data. Order 789-0123456-7890123. Arriving tomorrow.".encode('utf-8'), charset='utf-8')
        del plain_part["Content-Type"]
        plain_part["Content-Type"] = 'text/plain; charset="utf-8"'
        multi_part_msg.attach(plain_part)

        # HTML part
        html_part_msg = email.message.Message()
        html_part_msg.set_payload(html_body.encode('utf-8'), charset='utf-8')
        del html_part_msg["Content-Type"]
        html_part_msg["Content-Type"] = 'text/html; charset="utf-8"'
        multi_part_msg.attach(html_part_msg)

        return multi_part_msg.as_bytes()

    @patch('custom_components.mail_and_packages.v2.email_parser.datetime')
    def test_parse_amazon_with_json_ld_parcel_delivery(self, mock_dt):
        """Test parsing Amazon email with ParcelDelivery JSON-LD."""
        # Mock datetime.date.today() to control date-dependent logic
        mock_dt.date.today.return_value = datetime.date(2024, 7, 14) # Today is July 14
        mock_dt.datetime.strptime = datetime.datetime.strptime # Ensure strptime still works
        mock_dt.date = datetime.date # Ensure date constructor works

        parcel_data = {
            "@context": "http://schema.org",
            "@type": "ParcelDelivery",
            "deliveryAddress": {"@type": "PostalAddress", "streetAddress": "123 Main St", "addressLocality": "Anytown", "addressRegion": "CA", "postalCode": "90210", "addressCountry": "US"},
            "expectedArrivalUntil": "2024-07-15T17:00:00-07:00", # July 15 (tomorrow)
            "carrier": {"@type": "Organization", "name": "Amazon Logistics"},
            "itemShipped": {"@type": "Product", "name": "Test Product"},
            "trackingNumber": "TBA123456789012",
            "partOfOrder": {"@type": "Order", "orderNumber": "111-2222222-3333333"}
        }
        email_bytes = self.create_mock_json_ld_email([parcel_data], subject="Your Amazon.com order 111-2222222-3333333")

        parsed_data = parse_amazon_email(email_bytes)
        self.assertIsNotNone(parsed_data)
        self.assertEqual(parsed_data["provider"], "amazon")
        self.assertIn("111-2222222-3333333", parsed_data["orders"])
        self.assertIn("TBA123456789012", parsed_data["tracking_numbers"])
        self.assertEqual(parsed_data["estimated_delivery_date"], datetime.date(2024, 7, 15))
        self.assertEqual(parsed_data["deliveries_today_count"], 0) # ETA is tomorrow

    @patch('custom_components.mail_and_packages.v2.email_parser.datetime')
    def test_parse_amazon_with_json_ld_order_containing_parcel(self, mock_dt):
        """Test JSON-LD where ParcelDelivery is part of an Order schema."""
        mock_dt.date.today.return_value = datetime.date(2024, 7, 15) # Today is July 15
        mock_dt.datetime.strptime = datetime.datetime.strptime
        mock_dt.date = datetime.date


        order_data_with_parcel = {
            "@context": "http://schema.org",
            "@type": "Order",
            "orderNumber": "777-8888888-9999999",
            "merchant": {"@type": "Organization", "name": "Amazon.com"},
            "acceptedOffer": { "@type": "Offer", "itemOffered": {"@type": "Product", "name": "Product in Order"} },
            "partOfOrder": { # This is a common way to nest ParcelDelivery
                "@type": "ParcelDelivery",
                "trackingNumber": "PD777888999",
                "expectedArrivalUntil": "2024-07-15T12:00:00-07:00", # Today
                "carrier": {"@type": "Organization", "name": "AMZN_US"}
            }
        }
        email_bytes = self.create_mock_json_ld_email([order_data_with_parcel])
        parsed_data = parse_amazon_email(email_bytes)

        self.assertIsNotNone(parsed_data)
        self.assertIn("777-8888888-9999999", parsed_data["orders"])
        self.assertIn("PD777888999", parsed_data["tracking_numbers"])
        self.assertEqual(parsed_data["estimated_delivery_date"], datetime.date(2024, 7, 15))
        self.assertEqual(parsed_data["deliveries_today_count"], 1) # Order 777... has 1 item for today


    @patch('custom_components.mail_and_packages.v2.email_parser.datetime')
    def test_amazon_fallback_if_json_ld_missing_fields(self, mock_dt):
        """Test fallback if JSON-LD is present but missing key fields like date/tracking."""
        mock_dt.date.today.return_value = datetime.date(2024, 7, 16) # Today is July 16
        mock_dt.datetime.strptime = datetime.datetime.strptime
        mock_dt.date = datetime.date

        json_ld_data = {
            "@context": "http://schema.org",
            "@type": "ParcelDelivery", # Correct type
            "partOfOrder": {"@type": "Order", "orderNumber": "REG-EXFALLBACK-ORDER"},
            # Missing expectedArrivalUntil and trackingNumber
        }
        # Email body will contain info for regex fallback
        # Ensure a clear keyword for date parsing that the regex part uses
        today_str_for_body = mock_dt.date.today().strftime("%B %d") # e.g., "July 16"

        html_body_with_fallback_info = f"""
        <html><head><script type="application/ld+json">{json.dumps(json_ld_data)}</script></head>
        <body>
            <p>Your package REG-EXFALLBACK-ORDER</p>
            <p>Arriving: {today_str_for_body}</p>
            <p>Shipped with SomeCarrier, tracking # FALLBACK12345</p>
        </body></html>
        """
        # Create a proper multipart email for robustness
        multi_msg = email.message.Message()
        multi_msg.set_type("multipart/alternative")
        multi_msg["Subject"] = "Test Fallback"

        plain_part = email.message.Message()
        plain_text = f"Your package REG-EXFALLBACK-ORDER Arriving: {today_str_for_body} Tracking: FALLBACK12345"
        plain_part.set_payload(plain_text.encode('utf-8'), charset='utf-8')
        del plain_part["Content-Type"]; plain_part["Content-Type"] = 'text/plain; charset="utf-8"'
        multi_msg.attach(plain_part)

        html_part_msg = email.message.Message()
        html_part_msg.set_payload(html_body_with_fallback_info.encode('utf-8'), charset='utf-8')
        del html_part_msg["Content-Type"]; html_part_msg["Content-Type"] = 'text/html; charset="utf-8"'
        multi_msg.attach(html_part_msg)

        email_bytes = multi_msg.as_bytes()

        parsed_data = parse_amazon_email(email_bytes)
        self.assertIsNotNone(parsed_data, "Parser should return data")
        self.assertIn("REG-EXFALLBACK-ORDER", parsed_data["orders"], "Order number from JSON-LD or text should be found")
        self.assertEqual(parsed_data["estimated_delivery_date"], datetime.date(2024, 7, 16), "Date from regex fallback not parsed correctly")
        self.assertIn("FALLBACK12345", parsed_data["tracking_numbers"], "Tracking from regex fallback not found")
        self.assertEqual(parsed_data["deliveries_today_count"], 1, "Deliveries today count incorrect after fallback")


# We will add TestUspsParser, TestUpsParser etc. in subsequent steps.

if __name__ == '__main__':
    unittest.main()
