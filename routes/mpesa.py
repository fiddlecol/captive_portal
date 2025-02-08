import re
import time
import requests
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
from config import SHORTCODE, CALLBACK_URL, STK_PUSH_URL
from database.models import PaymentTransaction, db, Voucher, Client
from utilities import get_access_token, get_password_and_timestamp

mpesa_bp = Blueprint("mpesa", __name__)


def sanitize_phone_number(phone_number):
    current_app.logger.info(f"Raw Phone Input: {phone_number}")
    if not phone_number:
        raise ValueError("Phone number is required.")

    phone_number = phone_number.strip().replace(" ", "").replace("-", "")

    if phone_number.startswith("0"):
        phone_number = "254" + phone_number[1:]
    elif phone_number.startswith("+254"):
        phone_number = phone_number[1:]

    if not re.fullmatch(r"2547\d{8}", phone_number):
        raise ValueError("Invalid phone number format. Must be in '2547XXXXXXXX' format.")

    return phone_number


@mpesa_bp.route('/buy-voucher', methods=['POST'])
def buy_voucher():
    raw_data = request.get_json()

    try:
        phone_number = sanitize_phone_number(raw_data.get('phone_number'))
        amount = raw_data.get('amount')
        voucher_data = raw_data.get('voucher_data', "DefaultVoucher")
        voucher_duration = raw_data.get('voucher_duration')

        if not amount or not voucher_data or not voucher_duration:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        current_app.logger.info(f"MPesa STK Push Request: {raw_data}")

        password, timestamp = get_password_and_timestamp()
        access_token = get_access_token()
        current_app.logger.info(f"Access Token: {access_token}")

        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": CALLBACK_URL,
            "AccountReference": f"Voucher_{voucher_data}",
            "TransactionDesc": f"Buying {voucher_data} for {voucher_duration}",
        }
        current_app.logger.info(f"STK Push Payload: {payload}")

        # Send request with timeout
        start_time = time.time()
        response = requests.post(STK_PUSH_URL, headers={"Authorization": f"Bearer {access_token}"}, json=payload,
                                 timeout=30)
        end_time = time.time()

        current_app.logger.info(f"STK Push completed in {end_time - start_time} seconds")

        # Handle response
        try:
            json_response = response.json()
        except ValueError:
            current_app.logger.error(f"Invalid JSON response: {response.text}")
            return jsonify({"status": "error", "message": "Invalid response from M-Pesa"}), 500

        if response.status_code == 200 and json_response.get("ResponseCode") == "0":
            transaction = PaymentTransaction(
                checkout_request_id=json_response.get("CheckoutRequestID"),
                merchant_request_id=json_response.get("MerchantRequestID"),
                phone_number=phone_number,
                amount=float(amount),
                status="PENDING",
                description=f"Voucher for {voucher_data} ({voucher_duration})"
            )
            db.session.add(transaction)
            db.session.commit()
            current_app.logger.info(f"Transaction saved: ID {transaction.id}")
            return jsonify({"status": "success", "stk_response": json_response}), 200
        else:
            error_message = json_response.get("errorMessage", "Unknown error")
            current_app.logger.error(f"STK Push failed: {error_message}")
            return jsonify({"status": "error", "message": error_message}), 400

    except requests.RequestException as req_ex:
        current_app.logger.error(f"RequestException during STK Push: {req_ex}")
        return jsonify({"status": "error", "message": "STK Push request failed"}), 500
    except Exception as e:
        current_app.logger.exception("Unexpected error during buy-voucher")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@mpesa_bp.route('/mpesa_callback', methods=['POST'])
def mpesa_callback():
    """Handle callbacks from MPesa."""
    callback_data = request.get_json()
    current_app.logger.info(f"MPesa Callback Received: {callback_data}")

    try:
        # Extract necessary fields
        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        transaction_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        if not transaction_id:
            current_app.logger.error("Transaction ID not found in callback data.")
            return jsonify({"ResultCode": 1, "ResultDesc": "Transaction ID missing"}), 400

        # Store callback in database
        transaction = PaymentTransaction.query.filter_by(checkout_request_id=transaction_id).first()

        if not transaction:
            transaction = PaymentTransaction(
                checkout_request_id=transaction_id,
                status="PENDING",  # Default to pending
                description="MPesa callback received"
            )
            db.session.add(transaction)

        transaction.status = "SUCCESS" if result_code == 0 else "FAILED"
        transaction.description = result_desc
        db.session.commit()

        current_app.logger.info(f"Transaction {transaction_id} updated in the database.")

    except Exception as e:
        current_app.logger.exception(f"Error processing MPesa callback: {str(e)}")
        db.session.rollback()
        return jsonify({"ResultCode": 1, "ResultDesc": "Internal server error"}), 500

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200


@mpesa_bp.route('/validate/<receipt_number>', methods=['GET'])
def validate_voucher():
    """
    Validate a voucher based on receipt number fetched from PaymentTransaction
    """
    try:
        # Get the payload data from the request
        data = request.get_json()

        # Extract receipt_number and auto_login information from the request
        receipt_number = data.get("receipt_number")
        auto_login = data.get("auto_login", False)  # Manual login by default

        # Ensure receipt_number is provided in the request
        if not receipt_number:
            return jsonify({"success": False, "message": "Receipt number is required"}), 400

        # Fetch the receipt from the PaymentTransaction table with SUCCESS status
        transaction = PaymentTransaction.query.filter_by(
            receipt_number=receipt_number, status="SUCCESS"
        ).first()

        if not transaction:
            return jsonify({"success": False, "message": "Invalid receipt number or transaction not successful"}), 404

        # Use the receipt_number to fetch the associated Voucher
        voucher = Voucher.query.filter_by(code=transaction.receipt_number).first()

        if not voucher:
            return jsonify({"success": False, "message": "No voucher found for this receipt number"}), 404

        # Check if the voucher is already marked as used
        if voucher.is_used:
            return jsonify({"success": False, "message": "This voucher has already been used"}), 400

        # Find the Client entry associated with the voucher
        client = Client.query.filter_by(voucher_id=voucher.id).first()

        if not client:
            return jsonify({"success": False, "message": "No client is associated with this voucher"}), 404

        # Mark the voucher as used
        voucher.is_used = True

        try:
            # Persist the changes to the database
            db.session.commit()
        except Exception as commit_error:
            db.session.rollback()  # Rollback on failure
            current_app.logger.error(f"Database commit failed: {commit_error}")
            return jsonify({"success": False, "message": "Failed to update voucher status"}), 500

        # If auto-login is requested, provide login details and redirect info
        if auto_login:
            return jsonify(
                {
                    "success": True,
                    "message": "Welcome! You are automatically logged in.",
                    "client": {
                        "id": client.id,
                        "mac_address": client.mac_address,
                        "connected_at": client.connected_at,
                    },
                    "auth_method": "auto_login",
                }
            ), 200

        # If manual login, confirm validation success
        return jsonify(
            {
                "success": True,
                "message": "Voucher validated successfully! You may now manually log in.",
                "auth_method": "manual_login",
            }
        ), 200

    except Exception as e:
        # Handle and log unexpected errors
        current_app.logger.error(f"Unexpected error in validate_voucher: {str(e)}")
        db.session.rollback()  # Rollback in case of unexpected errors
        return jsonify({"success": False, "message": "Internal server error"}), 500
