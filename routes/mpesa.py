import requests
from flask import Blueprint, request, jsonify, current_app
from config import LIPA_NA_MPESA_URL
from extensions import db
from utilities import get_access_token, generate_password
from dotenv import load_dotenv
import re


# Load environment variables from the .env file
load_dotenv()

mpesa_bp = Blueprint("mpesa_bp", __name__)


@mpesa_bp.route('/buy-voucher', methods=['POST'])
def buy_voucher():
    try:
        # Log incoming JSON data
        data = request.get_json()
        current_app.logger.info(f"Raw request payload: {data}")

        if not data:
            return jsonify({"success": False, "error": "Invalid JSON data."}), 400

        # Cast voucher amount to integer
        try:
            amount_str = data.get('amount', '')
            amount = int(amount_str)  # Possible source of error
        except ValueError:
            return jsonify({"success": False, "error": "Voucher amount must be a number."}), 400

        current_app.logger.info(f"Voucher amount: {amount}")

        duration = data.get('voucher_duration', '')  # Another potential source of error
        # Ensure duration is provided
        if not duration:
            return jsonify({"success": False, "error": "Duration is required."}), 400

        # Define allowed vouchers
        allowed_vouchers = {
            1: "1 GB for 1 Hour",
            35: "3 GB for 3 Hours",
            45: "6 GB for 12 Hours",
            60: "10 GB for 24 Hours",
            1000: "Unlimited for 1 Month",
        }

        # Validate the amount
        if amount not in allowed_vouchers:
            raise ValueError(
                f"Invalid voucher amount: {amount}. "
                f"Allowed values: {list(allowed_vouchers.keys())}"
            )
        voucher_data = data.get('voucher_data', '')
        if not voucher_data:
            raise ValueError("Voucher data is missing.")

        allowed_data = ["1 GB", "3 GB", "6 GB", "10 GB", "Unlimited"]
        if voucher_data not in allowed_data:
            raise ValueError(f"Invalid voucher data. Allowed values: {', '.join(allowed_data)}")

        # Log successful validation
        current_app.logger.info("Amount, data and duration validated successfully")

        # (Placeholder) Process the request - M-Pesa transaction logic would go here
        return jsonify({"success": True, "message": "Voucher purchase request received."}), 200

    except ValueError as e:
        current_app.logger.error(f"ValueError: {e}")
        return jsonify({"success": False, "error": f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {e}")
        return jsonify({"success": False, "error": f"Unexpected error: {str(e)}"}), 500



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



def initiate_stk_push(phone_number, amount):
    try:
        phone_number = sanitize_phone_number(phone_number) # Ensure correct format
        access_token = get_access_token()
        password, timestamp = generate_password()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "BusinessShortCode": "174379",  # Your Business Shortcode
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": 1,
            "PartyA": "254746919779",  # Formatted phone number
            "PartyB": "174379",  # Your PartyB (business shortcode)
            "PhoneNumber": "254746919779", # customer's  phone number
            "CallBackURL": "https://41df-2c0f-fe38-224c-66b9-fd16-2f36-c647-e4e9.ngrok-free.app/mpesa_callback",
            "AccountReference": "WiFi Voucher",
            "TransactionDesc": "Purchase WiFi Voucher",
        }

        # Log the payload
        print("STK Push Payload:", payload)

        # Make the STK Push request

        response = requests.post(LIPA_NA_MPESA_URL, headers=headers, json=payload)

        # Log the response status and body
        print("STK Push Response Status:", response.status_code)
        print("STK Push Response Text:", response.text)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json()}
    except Exception as e:
        return {"error": str(e)}

# Example usage: Initiating STK Push
phone_number = "254708374149"  # Replace with the customer's phone number
amount = 50  # Amount to charge

response = initiate_stk_push(phone_number, amount)
print(response)


@mpesa_bp.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    callback_data = request.get_json()
    current_app.logger.info(f"MPesa Callback Data Received: {callback_data}")

    try:
        # Extract relevant fields from callback
        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        callback_metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])

        # Log callback details
        current_app.logger.info(
            f"MPesa Callback: ResultCode={result_code}, ResultDesc={result_desc}, "
            f"CheckoutRequestID={checkout_request_id}"
        )

        # Find transaction in the database
        from models import PaymentTransaction
        transaction = PaymentTransaction.query.filter_by(checkout_request_id=checkout_request_id).first()

        if not transaction:
            current_app.logger.error(
                f"Transaction not found for CheckoutRequestID: {checkout_request_id}"
            )
            return jsonify({"ResultCode": 1, "ResultDesc": "Transaction not found"}), 404

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
def validate_voucher():
    try:
        # Parse the incoming JSON request
        data = request.json
        print("Data received for validation:", data)

        # Extract required fields
        transaction_reference = data.get('transaction_reference')

        # Check if transaction_reference is present
        if not transaction_reference:
            return jsonify({"success": False, "error": "Missing voucher code"}), 400

            # Example validation logic
            # Replace this with real validation (e.g., database query)
        if transaction_reference.startswith("FID-"):  # Check format
            return jsonify({"success": True, "message": "Voucher code validated"}), 200
        else:
            return jsonify({"success": False, "error": "Invalid voucher code"}), 400

    except Exception as e:
        current_app.logger.error(f"Exception in validate_voucher: {str(e)}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


