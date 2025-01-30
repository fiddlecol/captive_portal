from flask import current_app
from datetime import datetime
import base64


def get_timestamp():
    """
    Generate the current timestamp in the required format (YYYYMMDDHHMMSS).
    """
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_password():
    """
    Generate a security password required for Mpesa STK Push.

    Combines BusinessShortCode, Passkey, and Timestamp, then encodes it using Base64.
    """

    business_short_code = current_app.config.get("174379")
    passkey = current_app.config.get("bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919")
    timestamp = get_timestamp()

    # Combine and encode
    data_to_encode = business_short_code + passkey + timestamp
    encoded_password = base64.b64encode(data_to_encode.encode()).decode()

    return encoded_password
