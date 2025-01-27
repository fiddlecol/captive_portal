# 1. IMPORTS
from flask import Flask, request, jsonify, render_template
import requests
import logging
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
import base64
import datetime

# Load environment variables from .env file
load_dotenv()

# 2. APP CONFIGURATION
app = Flask(__name__)

# Configuration values (use environment variables for sensitive info)
app.config['MPESA_CONSUMER_KEY'] = os.getenv('MPESA_CONSUMER_KEY')
app.config['MPESA_CONSUMER_SECRET'] = os.getenv('MPESA_CONSUMER_SECRET')
app.config['MPESA_AUTH_URL'] = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
app.config['MPESA_SHORTCODE'] = os.getenv('MPESA_SHORTCODE')
app.config['MPESA_PASSKEY'] = os.getenv('MPESA_PASSKEY')
app.config['MPESA_CALLBACK_URL'] = 'https://f7a6-2c0f-fe38-2326-38ac-4904-1811-35f5-11e1.ngrok-free.app/mpesa-callback'
if 'MPESA_CALLBACK_URL' in app.config:
    app.logger.info(f"MPESA Callback URL: {app.config['MPESA_CALLBACK_URL']}")
else:
    app.logger.error("MPESA_CALLBACK_URL is not set!")



# Setup logging
logging.basicConfig(level=logging.INFO)


# 3. UTILITY FUNCTIONS
def get_mpesa_access_token():
    """Fetch MPesa access token."""
    try:
        consumer_key = app.config['MPESA_CONSUMER_KEY']
        consumer_secret = app.config['MPESA_CONSUMER_SECRET']
        api_url = app.config['MPESA_AUTH_URL']

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
        app.logger.error(f"Failed to get MPesa access token: {e}")
        raise

def format_phone_number(phone_number):
    """Convert phone number to valid MPesa format."""
    app.logger.info(f"Formatting phone number: {phone_number}")
    if phone_number.startswith("+254"):
        formatted_phone = phone_number[1:]
    elif phone_number.startswith("254"):
        formatted_phone = phone_number
    elif phone_number.startswith("0") and len(phone_number) == 10:
        formatted_phone = "254" + phone_number[1:]
    else:
        app.logger.error(f"Invalid phone number format: {phone_number}")
        raise ValueError("Invalid phone number format")
    app.logger.info(f"Formatted phone number: {formatted_phone}")
    return formatted_phone


def initiate_stk_push(phone_number, amount, access_token):
    """Trigger MPesa STK Push."""
    try:
        app.logger.info("Starting STK Push process")

        # Logging before generating the timestamp
        app.logger.info("Generating timestamp and password...")
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        mpesa_shortcode = app.config.get('MPESA_SHORTCODE', 'NOT_SET')
        mpesa_passkey = app.config.get('MPESA_PASSKEY', 'NOT_SET')

        # Ensure the configs exist
        if mpesa_shortcode == 'NOT_SET' or mpesa_passkey == 'NOT_SET':
            app.logger.error("Missing MPesa credentials in app.config!")
            return {"status": "error", "message": "Missing MPesa credentials in app config."}

        # Generating password
        password = base64.b64encode(f"{mpesa_shortcode}{mpesa_passkey}{timestamp}".encode("utf-8")).decode("utf-8")
        app.logger.info("Timestamp and password generated successfully")

        try:
            # Validate and reformat phone number
            formatted_phone = format_phone_number(phone_number)
            app.logger.info(f"Validated and formatted phone number: {formatted_phone}")
            payload = {
                "BusinessShortCode": mpesa_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": formatted_phone,
                "PartyB": mpesa_shortcode,
                "PhoneNumber": formatted_phone,
                "CallBackURL": app.config['MPESA_CALLBACK_URL'],
                "AccountReference": "VoucherPurchase",
                "TransactionDesc": "BuyVoucher",
            }
            app.logger.info(f"Payload prepared: {payload}")
        except ValueError as e:
            app.logger.error(f"Phone number error: {e}")
            return {"status": "error", "message": str(e)}

        # Sending POST request to MPesa API
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {access_token}"}

        app.logger.info("Sending request to MPesa API...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        # Logging response
        app.logger.info(f"Received response from MPesa API: {response.status_code}")
        app.logger.info(f"Response body: {response.text}")

        # Check if response has failure
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        app.logger.error("Timeout occurred while trying to send a request to MPesa.")
        return {"status": "error", "message": "Timeout occurred during API call."}

    except Exception as e:
        app.logger.error(f"An error occurred: {e}")
        return {"status": "error", "message": "An unexpected error occurred.", "details": str(e)}


# 4. CLIENT ACTIVITIES / ROUTES

@app.route('/')
def home():
    """Home Page."""
    return render_template("login.html")


@app.route('/buy')
def buy_page():
    """Page for buying a voucher."""
    return render_template("buy.html")  # Assumes you have a `buy.html` file


@app.route('/buy-voucher', methods=['POST'])
def buy_voucher():
    """Buy voucher endpoint."""
    try:
        # Retrieve JSON data
        phone_number = request.json.get('phone_number')
        amount = request.json.get('amount')

        # Log inputs
        app.logger.info(f"Buy Voucher Request: phone_number={phone_number}, amount={amount}")

        # Get access token
        access_token = get_mpesa_access_token()
        app.logger.info(f"Access token: {access_token}")

        # Initiate STK Push
        response = initiate_stk_push(phone_number, amount, access_token)

        # Handle response
        if response and isinstance(response, dict):
            # Check for success in Safaricom's API response
            if response.get("ResponseCode") == "0":
                app.logger.info(f"STK Push successful: {response}")
                return jsonify({"message": "Voucher purchase successful!"}), 200
            else:
                app.logger.error(f"STK Push failed: {response}")
                return jsonify({"error": "Failed to initiate voucher purchase.", "details": response}), 400
        else:
            # Log unexpected response type or None
            app.logger.error(f"Unexpected response received: {response}")
            return jsonify({"error": "Unexpected response from STK Push request."}), 500

    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500


@app.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    # Get the JSON payload sent by MPesa
    callback_data = request.get_json()

    # Log the callback for debugging
    app.logger.info(f"Received MPesa Callback: {callback_data}")

    try:
        # Extract fields from the callback
        if "Body" in callback_data:
            stk_callback = callback_data["Body"].get("stkCallback", {})
            result_code = stk_callback.get("ResultCode", -1)
            result_desc = stk_callback.get("ResultDesc", "No description")
            merchant_request_id = stk_callback.get("MerchantRequestID", "")
            checkout_request_id = stk_callback.get("CheckoutRequestID", "")
            metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])

            # Default values
            amount = None
            receipt_number = None
            transaction_date = None
            phone_number = None

            # Parse metadata items
            for item in metadata:
                if item["Name"] == "Amount":
                    amount = item["Value"]
                elif item["Name"] == "MpesaReceiptNumber":
                    receipt_number = item["Value"]
                elif item["Name"] == "TransactionDate":
                    transaction_date = item["Value"]
                elif item["Name"] == "PhoneNumber":
                    phone_number = item["Value"]

            # Handle successful transactions
            if result_code == 0:
                app.logger.info(
                    f"Payment successful: Amount: {amount}, Receipt: {receipt_number}, "
                    f"Phone: {phone_number}, Date: {transaction_date}"
                )
                # TODO: Update the database to mark the transaction as successful
                # Example: Save receipt number and update user's voucher status
            else:
                app.logger.info(f"Payment failed: {result_desc}")
                # TODO: Handle failed transactions (e.g., notify the user)

        else:
            app.logger.error("Invalid callback data received")

    except Exception as e:
        app.logger.error(f"Error processing callback: {str(e)}")

    # Respond with status 200 OK to notify MPesa of successful receipt
    return jsonify({"ResultCode": 0, "ResultDesc": "Callback received successfully"}), 200


# 5. ERROR HANDLING

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 - Page Not Found."""
    return jsonify({"error": "Page not found"}), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 - Internal Server Error."""
    return jsonify({"error": "Internal server error"}), 500


# 6. APPLICATION ENTRY POINT
if __name__ == "__main__":
    app.run(host='0.0.0.0' , port=5000, debug=True)
