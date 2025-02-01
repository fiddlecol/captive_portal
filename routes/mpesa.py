import re
import requests
from dotenv import load_dotenv
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from utilities import get_access_token, generate_password, password, timestamp
from database.models import PaymentTransaction


load_dotenv()

mpesa_bp = Blueprint("mpesa_bp", __name__)


def sanitize_phone_number(phone_number):
    print("Raw Phone Input:", phone_number)  # Debugging line
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
    phone_number = raw_data.get('phone_number')
    amount = raw_data.get('amount')
    voucher_data = raw_data.get('voucher_data')
    voucher_duration = raw_data.get('voucher_duration')

    current_app.logger.info(f"Raw request payload: {raw_data}")
    current_app.logger.info(f"Phone number: {phone_number}")
    current_app.logger.info(f"Amount: {amount}")
    current_app.logger.info(f"Voucher duration: {voucher_duration}")

    # Step 1: Get Access Token
    access_token = get_access_token()

    # Step 2: Send STK Push
    stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "BusinessShortCode": "174379",
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": "174379",
        "PhoneNumber": phone_number,
        "CallBackURL": "https://1fa3-105-161-95-134.ngrok-free.app/mpesa_callback",
        "AccountReference": "Voucher",
        "TransactionDesc": f"Buying {voucher_data} for {voucher_duration}",
    }

    response = requests.post(stk_push_url, headers=headers, json=payload)
    if response.status_code == 200:
        stk_response = response.json()
        current_app.logger.info(f"STK Push Response: {stk_response}")
        return jsonify({"status": "success", "stk_response": stk_response}), 200
    else:
        current_app.logger.error(f"Failed STK Push: {response.text}")
        return jsonify({"status": "error", "message": "Failed to send STK Push"}), 500


def initiate_stk_push(phone_number, amount, voucher_data, voucher_duration, account_reference, transaction_desc):
    # Step 1: Generate the dynamic password and timestamp
    password, timestamp = generate_password()

    # Step 2: Get an access token
    access_token = get_access_token()

    # Step 3: Prepare the request payload
    stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "BusinessShortCode": "174379",
        "Password": "password",
        "Timestamp": "%Y%m%d%H%M%S",
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": "174379",
        "PhoneNumber": phone_number,
        "CallBackURL": "https://1fa3-105-161-95-134.ngrok-free.app/mpesa_callback",
        "AccountReference": "Voucher",
        "TransactionDesc": f"Buying {voucher_data} for {voucher_duration}",
    }

    # Step 4: Send the POST request to Safaricom API
    try:
        response = requests.post(stk_push_url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)

        # If the request is successful, return the JSON response
        return response.json()
    except requests.exceptions.RequestException as e:
        # Log the failure and return an error message
        print(f"Error initiating STK Push: {e}")
        return {"error": str(e)}


@mpesa_bp.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    callback_data = request.get_json()
    current_app.logger.info(f"MPesa Callback Data Received: {callback_data}")

    # Validate callback data
    if not callback_data or "Body" not in callback_data:
        current_app.logger.error("Invalid callback data received")
        return jsonify({"ResultCode": 1, "ResultDesc": "Invalid callback data"}), 400

    try:
        # Extract relevant fields from callback
        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        callback_metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])

        # Log minimal details
        current_app.logger.info(
            f"MPesa Callback: ResultCode={result_code}, ResultDesc={result_desc}, "
            f"CheckoutRequestID={checkout_request_id}"
        )

        # Find transaction in the database

        transaction = PaymentTransaction.query.filter_by(checkout_request_id=checkout_request_id).first()

        if not transaction:
            current_app.logger.error(
                f"Transaction not found for CheckoutRequestID: {checkout_request_id}"
            )
            return jsonify({"ResultCode": 1, "ResultDesc": "Transaction not found"}), 404

        # Check for duplicate processing
        if transaction.status in ["SUCCESS", "FAILED"]:
            current_app.logger.info(
                f"Skipping already processed transaction {transaction.id}"
            )
            return jsonify({"ResultCode": 0, "ResultDesc": "Callback already processed"}), 200

        # Update transaction details
        if result_code == 0:  # Payment succeeded
            transaction.status = "SUCCESS"
            for item in callback_metadata:
                if item["Name"] == "MpesaReceiptNumber":
                    transaction.receipt_number = item["Value"]
        else:  # Payment failed
            transaction.status = "FAILED"

        db.session.commit()
        current_app.logger.info(
            f"Updated transaction {transaction.id} status to {transaction.status}"
        )

        # Respond to M-Pesa
        return jsonify({"ResultCode": 0, "ResultDesc": "Callback processed successfully"}), 200

    except Exception as e:
        current_app.logger.error(f"Exception in mpesa_callback: {e}")
        db.session.rollback()
        return jsonify({"ResultCode": 1, "ResultDesc": "Error processing callback"}), 500


# Route to handle voucher validation/login
@mpesa_bp.route('/validate', methods=['POST'])
def validate_voucher(receipt_number):
    transaction = PaymentTransaction.query.filter_by(receipt_number=receipt_number, status="SUCCESS").first()
    if transaction:
        return True  # Voucher valid
    return False  # Invalid voucher


