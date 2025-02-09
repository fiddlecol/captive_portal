import re
import time
from datetime import datetime, timedelta

import requests
from flask import Blueprint, request, jsonify, current_app

from config import SHORTCODE, CALLBACK_URL, STK_PUSH_URL
from database.models import PaymentTransaction, db, Voucher
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

        # Extract callback metadata
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata_dict = {item["Name"]: item["Value"] for item in metadata_items if "Name" in item and "Value" in item}

        # Extract receipt number
        receipt_number = metadata_dict.get("MpesaReceiptNumber")

        # Fetch transaction from DB
        transaction = PaymentTransaction.query.filter_by(checkout_request_id=transaction_id).first()

        if not transaction:
            transaction = PaymentTransaction(
                checkout_request_id=transaction_id,
                status="PENDING",  # Default to pending
                description="MPesa callback received",
                receipt_number=receipt_number
            )
            db.session.add(transaction)

        # Handle different cases based on ResultCode
        if result_code == 0:
            transaction.status = "SUCCESS"
            transaction.receipt_number = receipt_number
            current_app.logger.info(f"Transaction {transaction_id} successful with Receipt: {receipt_number}")
        elif result_code == 2001:
            transaction.status = "FAILED"
            transaction.description = "Wrong PIN entered"
            current_app.logger.warning(f"Transaction {transaction_id} failed: Wrong PIN entered.")
        elif result_code == 1032:
            transaction.status = "FAILED"
            transaction.description = "Transaction cancelled by user"
            current_app.logger.warning(f"Transaction {transaction_id} cancelled by user.")
        else:
            transaction.status = "FAILED"
            transaction.description = result_desc
            current_app.logger.error(f"Transaction {transaction_id} failed: {result_desc}")

        db.session.commit()

    except Exception as e:
        current_app.logger.exception(f"Error processing MPesa callback: {str(e)}")
        db.session.rollback()
        return jsonify({"ResultCode": 1, "ResultDesc": "Internal server error"}), 500

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200


@mpesa_bp.route('/validate_voucher', methods=['POST'])
def validate_voucher():
    """Validate a receipt number and use it as a voucher code."""
    data = request.get_json()
    receipt_number = data.get("receipt_number")

    if not receipt_number:
        return jsonify({"status": "error", "message": "Receipt number is required"}), 400

    try:
        # Find transaction by receipt number
        transaction = PaymentTransaction.query.filter_by(receipt_number=receipt_number, status="SUCCESS").first()
        if not transaction:
            return jsonify({"status": "error", "message": "Invalid or unsuccessful transaction"}), 404

        # Check if voucher exists
        voucher = Voucher.query.filter_by(code=receipt_number).first()
        if not voucher:
            return jsonify({"status": "error", "message": "Voucher not found"}), 404

        # Check if the voucher was already used but still active
        if voucher.is_used:
            if voucher.expiry_time and voucher.expiry_time > datetime.utcnow():
                return jsonify({"status": "success", "message": "Reconnected to active session"}), 200
            return jsonify({"status": "error", "message": "Voucher expired"}), 400

        # Mark voucher as used and set expiry time (e.g., 1 hour from activation)
        voucher.is_used = True
        voucher.expiry_time = datetime.utcnow() + timedelta(hours=1)  # Adjust duration as needed
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Voucher validated successfully",
            "expiry_time": voucher.expiry_time.isoformat()
        }), 200

    except Exception as e:
        current_app.logger.exception(f"Error validating voucher: {str(e)}")
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@mpesa_bp.route('/payment-status', methods=['GET'])
def payment_status():
    phone = request.args.get('phone')  # Get phone query parameter
    request_id = request.args.get('request_id')  # Get request_id query parameter

    if not phone or not request_id:
        current_app.logger.error("Missing required query parameters: phone or request_id.")
        return jsonify({"status": "error", "message": "Missing required query parameters: phone or request_id"}), 400

    try:
        # Query the PaymentTransaction table for status
        transaction = PaymentTransaction.query.filter_by(phone_number=phone, checkout_request_id=request_id).first()

        if not transaction:
            current_app.logger.error(f"Transaction not found for Phone: {phone}, Request ID: {request_id}")
            return jsonify({"status": "error", "message": "Transaction not found."}), 404

        # Log and return transaction details
        current_app.logger.info(f"Found transaction: {transaction.checkout_request_id}, Status: {transaction.status}")
        return jsonify({
            "status": "success",
            "transaction_status": transaction.status,
            "amount": transaction.amount,
            "description": transaction.description,
            "receipt_number": transaction.receipt_number,
            "timestamp": transaction.updated_at.isoformat() if transaction.updated_at else None
        }), 200

    except Exception as e:
        current_app.logger.exception(f"Error fetching payment status: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

