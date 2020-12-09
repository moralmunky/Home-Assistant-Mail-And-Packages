#!/usr/bin/env python

"""
Make sure you change the parameters - username, password, mailbox,
paths and options.
Based on @skalavala work at https://blog.kalavala.net/usps/homeassistant/mqtt/2018/01/12/usps.html
"""

import datetime
import email
import imaplib
import os
import re
import subprocess
import sys
import time
from datetime import timedelta
from shutil import copyfile

host = "imap.mail.com"
port = 993
username = "email@email.com"
password = "password"
folder = "Inbox"
image_output_path = "/home/homeassistant/.homeassistant/images/mail_and_packages/"

USPS_Email = "USPSInformedDelivery@usps.gov"
USPS_Mail_Subject = "Informed Delivery Daily Digest"
USPS_Delivering_Subject = "Expected Delivery on"
USPS_Delivered_Subject = "Item Delivered"

UPS_Email = "mcinfo@ups.com"
UPS_Delivering_Subject = "UPS Update: Package Scheduled for Delivery Today"
UPS_Delivered_Subject = "Your UPS Package was delivered"

FEDEX_Email = "TrackingUpdates@fedex.com"
FEDEX_Delivering_Subject = "Delivery scheduled for today"
FEDEX_Delivered_Subject = "Your package has been delivered"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
GIF_FILE_NAME = "mail_today_test.gif"
IMG_RESIZE_OPTIONS = "convert -resize 700x315\> "
GIF_MAKER_OPTIONS = (
    "convert -delay 300 -loop 0 -coalesce -fill white -dispose Background "
)

# Login Method
###############################################################################


def login():
    account = imaplib.IMAP4_SSL(host, port)

    try:
        rv, data = account.login(username, password)
        print("Logged into your email server successfully!")
    except imaplib.IMAP4.error:
        print(
            "Failed to authenticate using the given credentials. Check your username, password, host and port."
        )
        sys.exit(1)

    return account


# Select folder inside the mailbox
###############################################################################


def selectfolder(account, folder):
    (rv, mailboxes) = account.list()
    (rv, data) = account.select(folder)


# Returns today in specific format
###############################################################################


def get_formatted_date():
    return datetime.datetime.today().strftime("%d-%b-%Y")


# gets update time
###############################################################################


def update_time():
    updated = datetime.datetime.now().strftime("%b-%d-%Y %I:%M %p")

    return updated


# Creates GIF image based on the attachments in the inbox
###############################################################################


def get_mails(account):
    today = get_formatted_date()
    # Custom email date
    today = "21-Sep-2019"
    image_count = 0
    images = []
    imagesDelete = []

    print("Attempting to find Informed Delivery mail for {}".format(str(today)))

    # Check the mail piece for mail images
    rv, data = account.search(
        None,
        '(FROM "'
        + USPS_Email
        + '" SUBJECT "'
        + USPS_Mail_Subject
        + '" ON "'
        + today
        + '")',
    )

    # Get number of emails found
    messageIDsString = str(data[0], encoding="utf8")
    listOfSplitStrings = messageIDsString.split(" ")
    msg_count = len(listOfSplitStrings)
    print("Found emails: {}\n".format(str(msg_count)))

    if rv == "OK":
        for num in data[0].split():
            (rv, data) = account.fetch(num, "(RFC822)")
            msg = email.message_from_string(data[0][1].decode("utf-8"))

            # walking through the email parts to find images
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get("Content-Disposition") is None:
                    continue

                filepath = image_output_path + part.get_filename()
                print("Image found: {}.".format(str(filepath)))
                fp = open(filepath, "wb")
                fp.write(part.get_payload(decode=True))
                images.append(filepath)
                # print(*images, sep = "\n")
                # print ("\n")
                image_count = image_count + 1
                fp.close()

        print("Total mages found in email: {}. \n".format(str(image_count)))

        # Remove duplicate images
        print("Removing duplicate images.")
        images = list(dict.fromkeys(images))

        # Create copy of image list before checking for image-no-mailpieces image so we can delete them
        imagesDelete = images
        print("Images to delete.")
        print(*imagesDelete, sep="\n")
        print("\n")

        image_count = len(images)
        print("Found {} unique images total to generate gif.".format(str(image_count)))
        print(*images, sep="\n")
        print("\n")

        # Remove USPS announcement images
        print("Removing USPS announcement images.")
        remove_terms = ["mailerProvidedImage", "ra_0"]
        images = [
            el for el in images if not any(ignore in el for ignore in remove_terms)
        ]
        image_count = len(images)

        print("Found {} mail images total to generate gif.".format(str(image_count)))
        print(*images, sep="\n")
        print("\n")

        # Look for mail pieces without images image
        print("Checking for mail with no images.")
        html_text = str(msg)
        link_pattern = re.compile("image-no-mailpieces700.jpg")
        search = link_pattern.search(html_text)
        if search is not None:
            images.append(image_output_path + "image-no-mailpieces700.jpg")
            image_count = image_count + 1
            print("Image found: " + image_output_path + "image-no-mailpieces700.jpg.")
        else:
            print("No image-no-mailpieces700.jpg image found.\n")
        print("\n")

        # Creating the GIF
        if image_count > 0:
            all_images = ""

        # Convert to similar images sizes
        for image in images:
            try:
                os.system(IMG_RESIZE_OPTIONS + image + " " + image)
            except Exception as err:
                print("Error attempting to resize images: {}".format(str(err)))

        # Combine images into GIF
        for image in images:
            all_images = all_images + image + " "
        try:
            os.system(
                GIF_MAKER_OPTIONS + all_images + image_output_path + GIF_FILE_NAME
            )
            print("GIF of mail images generated.\n")

        except Exception as err:
            print("Error attempting to generate image: {}".format(str(err)))

        print("Deleting temporary images.")
        for image in imagesDelete:
            try:
                os.remove(image)
                print("Removed image: {}.".format(str(image)))
            except Exception as err:
                print("Error attempting to remove image: {}".format(str(err)))

        print("\n")

    if image_count == 0:
        try:
            os.remove(image_output_path + GIF_FILE_NAME)
            print("No mail GIF generated.\n")
        except Exception as err:
            print("Error attempting to remove image: {}".format(str(err)))

        try:
            copyfile(
                image_output_path + "mail_none.gif", image_output_path + GIF_FILE_NAME
            )
        except Exception as err:
            print("Error attempting to copy image: {}".format(str(err)))
        print("\n")

        return image_count


# Get Package Count
###############################################################################


def get_count(account, email, subject):
    count = 0
    today = get_formatted_date()

    (rv, data) = account.search(
        None, '(FROM "' + email + '" SUBJECT "' + subject + '" SINCE "' + today + '")'
    )

    if rv == "OK":
        count = len(data[0].split())

    return count


# Get Package Count
###############################################################################


def MailCheck():

    updated = update_time()
    print("Update Time '{}'".format(updated))


def USPS_Mail():

    account = login()
    selectfolder(account, folder)
    count = get_mails(account)
    print("USPS Mail 1/4: Found '{}' mail pieces being delivered".format(count))

    account = login()
    selectfolder(account, folder)
    count = get_count(account, USPS_Email, USPS_Mail_Subject)
    print("USPS Mail 2/4: Found '{}' USPS emails".format(count))


def USPS_Delivering():

    account = login()
    selectfolder(account, folder)
    count = get_count(account, USPS_Email, USPS_Delivering_Subject)
    print("USPS 3/4: Found '{}' USPS packages delivering".format(count))


def USPS_Delivered():

    account = login()
    selectfolder(account, folder)
    count = get_count(account, USPS_Email, USPS_Delivered_Subject)
    print("USPS 4/4: Found '{}' USPS packages delivered".format(count))


def UPS_Delivering():

    account = login()
    selectfolder(account, folder)
    count = get_count(account, UPS_Email, UPS_Delivering_Subject)
    print("UPS 1/2: Found '{}' UPS packages delivering".format(count))


def UPS_Delivered():

    account = login()
    selectfolder(account, folder)
    count = get_count(account, UPS_Email, UPS_Delivered_Subject)
    print("UPS 2/2: Found '{}' UPS packages delivered".format(count))


def FEDEX_Delivering():

    account = login()
    selectfolder(account, folder)
    count = get_count(account, FEDEX_Email, FEDEX_Delivering_Subject)
    print("FEDEX 1/2: Found '{}' FedEx packages delivering".format(count))


def FEDEX_Delivered():

    account = login()
    selectfolder(account, folder)
    count = get_count(account, FEDEX_Email, FEDEX_Delivered_Subject)
    print("FEDEX 2/2: Found '{}' FedEx packages delivered".format(count))


# Primary logic for the component starts here
###############################################################################
try:
    while True:
        try:
            account = login()
            selectfolder(account, folder)
        except Exception as exx:
            print("Error connecting logging into email server.")
            print(str(exx))
            sys.exit(1)

        MailCheck()
        USPS_Mail()
        USPS_Delivering()
        USPS_Delivered()
        UPS_Delivering()
        UPS_Delivered()
        FEDEX_Delivering()
        FEDEX_Delivered()

        print("Finished checking.")

        # For testing, running manually within the env
        sys.exit(1)

except Exception as e:
    print("Error occured while either processing email.")
    print(str(e))
    sys.exit(1)
