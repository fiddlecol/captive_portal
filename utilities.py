import base64
import datetime
import requests
from requests.auth import HTTPBasicAuth
from flask import current_app


def some_utility_function():
    config_value = current_app.config["SOME_VALUE"]
    print(f"The config value is: {config_value}")  # Using config_value
    return config_value  # Returning the value


# 3. UTILITY FUNCTIONS
def get_mpesa_access_token():
    """Fetch MPesa access token."""
    try:
        consumer_key = current_app.config['MPESA_CONSUMER_KEY']
        consumer_secret = current_app.config['MPESA_CONSUMER_SECRET']
        api_url = current_app.config['MPESA_AUTH_URL']

        if not consumer_key or not consumer_secret:
            raise ValueError("Consumer key or secret not configured properly.")

        # Request token
        response = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
        response.raise_for_status()  # Raise an exception for HTTP error codes

        access_token = response.json().get("access_token")
        if not access_token:
            raise ValueError("Access token not found in response.")

        return access_token
    except Exception as e:
        current_app.logger.error(f"Failed to get MPesa access token: {e}")
        raise

def format_phone_number(phone_number):
    """Convert phone number to valid MPesa format."""
    current_app.logger.info(f"Formatting phone number: {phone_number}")
    if phone_number.startswith("+254"):
        formatted_phone = phone_number[1:]
    elif phone_number.startswith("254"):
        formatted_phone = phone_number
    elif phone_number.startswith("0") and len(phone_number) == 10:
        formatted_phone = "254" + phone_number[1:]
    else:
        current_app.logger.error(f"Invalid phone number format: {phone_number}")
        raise ValueError("Invalid phone number format")
    current_app.logger.info(f"Formatted phone number: {formatted_phone}")
    return formatted_phone


def initiate_stk_push(phone_number, amount, access_token):
    """Trigger MPesa STK Push."""
    try:
        current_app.logger.info("Starting STK Push process")

        # Logging before generating the timestamp
        current_app.logger.info("Generating timestamp and password...")
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        mpesa_shortcode = current_app.config.get('MPESA_SHORTCODE', 'NOT_SET')
        mpesa_passkey = current_app.config.get('MPESA_PASSKEY', 'NOT_SET')

        # Ensure the configs exist
        if mpesa_shortcode == 'NOT_SET' or mpesa_passkey == 'NOT_SET':
            current_app.logger.error("Missing MPesa credentials in current_app.config!")
            return {"status": "error", "message": "Missing MPesa credentials in app config."}

        # Generating password
        password = base64.b64encode(f"{mpesa_shortcode}{mpesa_passkey}{timestamp}".encode("utf-8")).decode("utf-8")
        current_app.logger.info("Timestamp and password generated successfully")

        try:
            # Validate and reformat phone number
            formatted_phone = format_phone_number(phone_number)
            current_app.logger.info(f"Validated and formatted phone number: {formatted_phone}")
            payload = {
                "BusinessShortCode": mpesa_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": formatted_phone,
                "PartyB": mpesa_shortcode,
                "PhoneNumber": formatted_phone,
                "CallBackURL": current_app.config['MPESA_CALLBACK_URL'],
                "AccountReference": "VoucherPurchase",
                "TransactionDesc": "BuyVoucher",
            }
            current_app.logger.info(f"Payload prepared: {payload}")
        except ValueError as e:
            current_app.logger.error(f"Phone number error: {e}")
            return {"status": "error", "message": str(e)}

        # Sending POST request to MPesa API
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {access_token}"}

        current_app.logger.info("Sending request to MPesa API...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        # Logging response
        current_app.logger.info(f"Received response from MPesa API: {response.status_code}")
        current_app.logger.info(f"Response body: {response.text}")

        # Check if response has failure
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        current_app.logger.error("Timeout occurred while trying to send a request to MPesa.")
        return {"status": "error", "message": "Timeout occurred during API call."}

    except Exception as e:
        current_app.logger.error(f"An error occurred: {e}")
        return {"status": "error", "message": "An unexpected error occurred.", "details": str(e)}
