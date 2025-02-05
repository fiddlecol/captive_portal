import re
from datetime import datetime
import requests
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
from database.models import PaymentTransaction, db
from utilities import get_access_token, get_password_and_timestamp
from config import SHORTCODE, CALLBACK_URL, STK_PUSH_URL

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

        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(STK_PUSH_URL, headers=headers, json=payload)

        current_app.logger.info(f"STK Push Response JSON: {response.json()}")

        if response.status_code == 200:
            stk_response = response.json()
            if stk_response.get("ResponseCode") != "0":
                error_message = stk_response.get("errorMessage", "Unknown error occurred.")
                current_app.logger.error(f"STK Push failed: {error_message}")
                return jsonify({"status": "error", "message": f"STK Push failed: {error_message}"}), 400

            try:
                transaction = PaymentTransaction(
                    checkout_request_id=stk_response.get("CheckoutRequestID"),
                    phone_number=phone_number,
                    amount=float(amount),
                    status="PENDING",
                    description=f"Voucher for {voucher_data} ({voucher_duration})"
                )
                db.session.add(transaction)
                current_app.logger.info(f"Transaction to be saved: {transaction}")

                db.session.commit()
                current_app.logger.info(
                    f"Transaction saved: ID {transaction.id}, CheckoutRequestID {transaction.checkout_request_id}")
                return jsonify({"status": "success", "stk_response": stk_response}), 200
            except SQLAlchemyError as db_ex:
                db.session.rollback()
                current_app.logger.error(f"Database error: {db_ex}")
                return jsonify({"status": "error", "message": "Database error occurred"}), 500

        current_app.logger.error(f"Unexpected response from STK Push: {response.text}")
        return jsonify({"status": "error", "message": "Failed to process STK Push"}), 500

    except requests.RequestException as req_ex:
        current_app.logger.error(f"RequestException during STK Push: {req_ex}")
        return jsonify({"status": "error", "message": "STK Push request failed"}), 500
    except Exception as e:
        current_app.logger.exception("Unexpected error during buy-voucher")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@mpesa_bp.route('/validate/<receipt_number>', methods=['GET'])
def validate_voucher(receipt_number):
    transaction = PaymentTransaction.query.filter_by(receipt_number=receipt_number, status="SUCCESS").first()
    if transaction:
        return jsonify({"status": "success", "message": "Voucher is valid"}), 200
    return jsonify({"status": "error", "message": "Invalid or expired voucher"}), 404
