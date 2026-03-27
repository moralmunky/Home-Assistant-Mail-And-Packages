"""Date and time helpers for Mail and Packages."""

import datetime


def get_today() -> datetime.date:
    """Get today's date using system local timezone (Home Assistant's timezone).

    Returns date object using the system's local timezone.
    """
    return datetime.date.today()


def get_formatted_date() -> str:
    """Return today in specific format.

    Returns current timestamp as string
    """
    return get_today().strftime("%d-%b-%Y")


async def update_time() -> datetime.datetime:
    """Get update time.

    Returns current timestamp as datetime object.
    """
    return datetime.datetime.now(datetime.UTC)
