import requests
from flask import current_app
from datetime import datetime
import base64


def initiate_mpesa_payment(phone_number, amount):
    access_token = current_app.config.get("MPESA_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN_PLACEHOLDER")

    # Prepare credentials
    business_short_code = "YOUR_SHORTCODE"  # Paybill or Till number
    passkey = "YOUR_PASSKEY"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode()

    # STK push endpoint
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

    # Payload
    payload = {
        "BusinessShortCode": business_short_code,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": business_short_code,
        "PhoneNumber": phone_number,
        "CallBackURL": "https://yourdomain.com/mpesa-callback",
        "AccountReference": "YOUR_REFERENCE",
        "TransactionDesc": "Payment of goods"
    }

    # Headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Perform the STK push
    response = requests.post(api_url, json=payload, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        # Handle errors
        return {
            "error": "Failed to initiate STK push",
            "details": response.json()
        }


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
    import base64

    business_short_code = current_app.config.get("MPESA_BUSINESS_SHORT_CODE")
    passkey = current_app.config.get("MPESA_PASSKEY")
    timestamp = get_timestamp()

    # Combine and encode
    data_to_encode = business_short_code + passkey + timestamp
    encoded_password = base64.b64encode(data_to_encode.encode()).decode()

    return encoded_password
