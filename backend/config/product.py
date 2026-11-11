import os


BRAND_NAME = os.environ.get("ALONG_BRAND_NAME", "Along")
TAGLINE = os.environ.get("ALONG_TAGLINE", "Good company. Great experiences.")
COUNTRY_CODE = os.environ.get("ALONG_COUNTRY_CODE", "BD")
CURRENCY_CODE = os.environ.get("ALONG_CURRENCY_CODE", "BDT")
TIME_ZONE = os.environ.get("ALONG_TIME_ZONE", "Asia/Dhaka")
LAUNCH_CITY = os.environ.get("ALONG_LAUNCH_CITY", "Dhaka")


def default_country_code():
    return COUNTRY_CODE


def default_currency_code():
    return CURRENCY_CODE


def default_time_zone():
    return TIME_ZONE
