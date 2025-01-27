import base64
import logging
from datetime import datetime

import requests
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy

from config import *

# Initialize Flask App and Database
app = Flask(__name__)
app.debug = True
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Logging Configuration
logging.basicConfig(level=logging.DEBUG)

# Constants
CALLBACK_URL = "https://965d-196-96-89-46.ngrok-free.app/mpesa_callback"


# --- DATABASE MODELS ---
class Voucher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_used = db.Column(db.Boolean, default=False)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(100), unique=True, nullable=False)
    voucher_id = db.Column(db.Integer, db.ForeignKey('voucher.id'))


# --- UTILITY FUNCTIONS ---
def validate_phone(phone_number):
    """Validate and sanitize phone number (254XXXXXXXXX format)."""
    if not phone_number:
        return None
    phone_number = phone_number.lstrip("+")
    if not phone_number.startswith("254"):
        if phone_number.startswith("0"):
            phone_number = "254" + phone_number[1:]
        else:
            return None
    return phone_number if len(phone_number) == 12 and phone_number.isdigit() else None


def validate_amount(amount):
    """Validate if the amount is a positive number."""
    try:
        return float(amount) > 0
    except (ValueError, TypeError):
        return False


def get_mpesa_credentials():
    """Retrieve MPesa consumer key and secret."""
    return (
        "Dq9O5LhoZgGLs1A2Ir7sjzpUTBM4oqoWlnJBvuW9rVIK3U40",
        "G2oZY5FRzaceYXoCPbiKcGXGgpUdAy5MRUnAq9DJ3vwuEAYDDME8DhWuffKqKzyj",
    )


import base64
import requests


def get_mpesa_access_token():
    consumer_key = "YOUR_CONSUMER_KEY"
    consumer_secret = "YOUR_CONSUMER_SECRET"
    api_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"  # Sandbox URL

    try:
        # Form the authorization header
        basic_auth = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {basic_auth}"}

        # Make the API call and add logging
        response = requests.get(api_URL, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")  # Log status code
        print(f"Response: {response.text}")  # Log full response from MPesa server

       # Check response and extract the access token
        response.raise_for_status()  # Raise exception for HTTP errors
        access_token = response.json().get("access_token")
        if not access_token:
            raise ValueError("Failed to retrieve access_token from API response")

        return access_token

    except requests.exceptions.RequestException as e:
        print(f"RequestException: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def generate_stk_password():
    """Generate MPesa STK Push password."""
    timestamp = get_current_timestamp()
    raw_password = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(raw_password.encode("utf-8")).decode("utf-8")


def get_current_timestamp():
    """Get the current timestamp in the format required by MPesa."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def initiate_stk_push(phone_number, amount, access_token):
    """Initiate MPesa STK Push for payment."""
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": generate_stk_password(),
        "Timestamp": get_current_timestamp(),
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "VoucherPurchase",
        "TransactionDesc": "Purchase Voucher",
    }
    try:
        response = requests.post(api_url, json=payload, headers={"Authorization": f"Bearer {access_token}"})
        return response.json()
    except Exception as e:
        app.logger.error("Error in STK Push: %s", str(e))
        return {"status": "error", "message": "Failed to process STK Push request"}


# --- ROUTES ---
@app.route('/', methods=["GET"])
def index():
    """Display homepage with options for login or buying vouchers."""
    return render_template('login.html')


@app.route('/buy', methods=["GET"])
def display_buy_page():
    """Render voucher purchase page."""
    return render_template('buy.html')


def get_cached_mpesa_token():
    pass


@app.route('/buy-voucher', methods=["POST"])
def buy_voucher():
    try:
        app.logger.info("Processing /buy-voucher request")

        # Validate incoming JSON
        if not request.is_json:
            app.logger.warning("Invalid request: Not JSON")
            return jsonify({"status": "error", "message": "Invalid request format"}), 400

        data = request.get_json()
        phone_number = data.get("phone_number")
        amount = data.get("amount")
        app.logger.info(f"Received phone_number: {phone_number}, amount: {amount}")

        if not phone_number or not amount:
            app.logger.warning("Missing phone_number or amount in request")
            return jsonify({"status": "error", "message": "phone_number and amount are required"}), 400

        # Fetch MPesa access token
        access_token = get_cached_mpesa_token()
        if not access_token:
            app.logger.error("Failed to retrieve MPesa access token")
            return jsonify({"status": "error", "message": "Failed to retrieve access token"}), 500

        # Attempt STK Push
        response = initiate_stk_push(phone_number, amount, access_token)
        app.logger.info(f"STK Push Response: {response}")
        if response.get("ResponseCode") == "0":
            return jsonify({"status": "success", "message": "STK Push initiated successfully"}), 200

        # Log error response from MPesa
        error_message = response.get("errorMessage", "Failed to initiate STK Push")
        app.logger.error(f"MPesa API Error: {error_message}")
        return jsonify({"status": "error", "message": error_message}), 500

    except Exception as e:
        # Log exceptions for debugging
        app.logger.exception("An unexpected error occurred in /buy-voucher")
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500


@app.route('/mpesa_callback', methods=["POST"])
def mpesa_callback():
    """Handle MPesa transaction confirmation callback."""
    try:
        data = request.json
        if data['Body']['stkCallback']['ResultCode'] == 0:  # Payment successful
            transaction_id = data['Body']['stkCallback']['CallbackMetadata']['Item'][1]['Value']
            # Generate and save a voucher
            new_voucher = Voucher(code=transaction_id, price=50)
            db.session.add(new_voucher)
            db.session.commit()
            return jsonify({"status": "success", "message": "Voucher generated"}), 200
        return jsonify({"status": "error", "message": "Payment failed"}), 400
    except Exception as e:
        app.logger.exception("Exception occurred in /mpesa_callback")
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500


@app.route('/login', methods=["POST"])
def login():
    """Authenticate user using voucher code."""
    try:
        voucher_code = request.form['voucher']
        mac_address = request.remote_addr
        voucher_record = Voucher.query.filter_by(code=voucher_code, is_used=False).first()
        if voucher_record:
            voucher_record.is_used = True
            db.session.commit()
            return jsonify({"status": "success", "message": "Login successful"}), 200
        return jsonify({"status": "error", "message": "Invalid or used voucher"}), 400
    except Exception as e:
        app.logger.exception("Exception occurred in /login")
        return jsonify({"status": "error", "message": "An unexpected error occurred"}), 500


# --- APPLICATION ENTRY POINT ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
