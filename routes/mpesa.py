import re
import time
from datetime import timezone, datetime, timedelta
import requests
from flask import Blueprint, request, jsonify, current_app
from config import Config, STK_PUSH_URL
from database.models import PaymentTransaction, db, Voucher
from utilities import get_access_token, get_password_and_timestamp, SHORTCODE, TILL_NUMBER, CALLBACK_URL
from zoneinfo import ZoneInfo


EAT = ZoneInfo("Africa/Nairobi") 

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

        # Generate password and timestamp for payload
        password, timestamp = get_password_and_timestamp()
        access_token = get_access_token()
        
        if not access_token:
            current_app.logger.error("Failed to retrieve access token.")
            return jsonify({"status": "error", "message": "Authentication error"}), 401
        
        current_app.logger.info(f"Retrieved Access Token: {access_token}")

        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerBuyGoodsOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": TILL_NUMBER,
            "PhoneNumber": phone_number,
            "CallBackURL": CALLBACK_URL,
            "AccountReference": f"Voucher_{voucher_data}",
            "TransactionDesc": f"Buying {voucher_data} for {voucher_duration}",
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        current_app.logger.info(f"STK Push Headers: {headers}")
        current_app.logger.info(f"STK Push Payload: {payload}")

        # Track response time for logging
        start_time = time.time()
        response = requests.post(STK_PUSH_URL, headers=headers, json=payload, timeout=10)
        end_time = time.time()
        
        current_app.logger.info(f"STK Push completed in {end_time - start_time} seconds")

        try:
            json_response = response.json()
        except ValueError:
            current_app.logger.error(f"Invalid JSON response: {response.text}")
            return jsonify({"status": "error", "message": "Invalid response from M-Pesa"}), 500

        # Handle successful M-Pesa response
        if response.status_code == 200 and json_response.get("ResponseCode") == "0":
            transaction = PaymentTransaction(
                checkout_request_id=json_response.get("CheckoutRequestID"),
                merchant_request_id=json_response.get("MerchantRequestID"),
                phone_number=phone_number,
                amount=float(amount),
                status="PENDING",  # Set as PENDING initially; will update after callback
                description=f"Voucher for {voucher_data} ({voucher_duration})"
            )
            db.session.add(transaction)
            db.session.commit()
            current_app.logger.info(f"Transaction saved: ID {transaction.id}")
            return jsonify({"status": "success", "stk_response": json_response}), 200
        else:
            current_app.logger.error(f"STK Push failed with: {json_response.get('errorMessage', 'Unknown error')}")
            return jsonify({"status": "error", "message": json_response.get('errorMessage', 'Unknown error')}), 400

    except requests.RequestException as req_ex:
        current_app.logger.error(f"RequestException during STK Push: {req_ex}")
        return jsonify({"status": "error", "message": "STK Push request failed"}), 500
    except Exception as e:
        current_app.logger.exception(f"Unexpected error during buy-voucher: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@mpesa_bp.route('/mpesa_callback', methods=['POST'])
def mpesa_callback():
    """Handle callbacks from MPesa."""
    try:
        # Log raw incoming data for debugging purposes
        raw_data = request.get_data(as_text=True)
        current_app.logger.info(f"Raw MPesa Callback Data: {raw_data}")

        # Ensure Content-Type is JSON
        if not request.content_type or "application/json" not in request.content_type:
            current_app.logger.error(f"Invalid Content-Type: {request.content_type}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Content-Type must be application/json"}), 400

        # Ensure the body is not empty
        if not request.data:
            current_app.logger.error("Empty request body received.")
            return jsonify({"ResultCode": 1, "ResultDesc": "Empty request body"}), 400

        # Attempt to parse JSON from request
        try:
            callback_data = request.get_json()
        except Exception as e:
            current_app.logger.error(f"Failed to parse JSON: {str(e)}. Raw Data: {raw_data}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Invalid JSON format"}), 400

        # Log the successfully parsed JSON payload
        current_app.logger.info(f"Parsed MPesa Callback Data: {callback_data}")

        # Extract and validate key data
        stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
        if not stk_callback:
            current_app.logger.error("stkCallback data is missing in callback.")
            return jsonify({"ResultCode": 1, "ResultDesc": "stkCallback missing"}), 400

        transaction_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")

        if not transaction_id:
            current_app.logger.error(f"Transaction ID missing in callback: {callback_data}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Transaction ID missing"}), 400

        # Process Metadata
        metadata_items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
        metadata_dict = {item.get("Name"): item.get("Value") for item in metadata_items if "Name" in item}
        receipt_number = metadata_dict.get("MpesaReceiptNumber")

        # Fetch the transaction from the database
        from sqlalchemy.exc import SQLAlchemyError
        try:
            transaction = PaymentTransaction.query.filter_by(checkout_request_id=transaction_id).first()
        except SQLAlchemyError as db_error:
            current_app.logger.error(f"Database query error: {str(db_error)}")
            return jsonify({"ResultCode": 1, "ResultDesc": "Database query failed"}), 500

        # Create new transaction if none exists
        if not transaction:
            try:
                transaction = PaymentTransaction(
                    checkout_request_id=transaction_id,
                    status="PENDING",
                    description="MPesa callback received",
                    receipt_number=receipt_number
                )
                db.session.add(transaction)
            except SQLAlchemyError as db_error:
                current_app.logger.error(f"Failed to create transaction: {str(db_error)}")
                db.session.rollback()
                return jsonify({"ResultCode": 1, "ResultDesc": "Transaction creation error"}), 500

        # Process the ResultCode
        if result_code == 0:
            transaction.status = "SUCCESS"
            transaction.receipt_number = receipt_number
            current_app.logger.info(f"Transaction {transaction_id} successful with receipt number: {receipt_number}")

            # Check if voucher exists or create a new one
            existing_voucher = Voucher.query.filter_by(code=receipt_number).first()
            if not existing_voucher:
                try:
                    voucher = Voucher(
                        code=receipt_number,
                        is_used=False,
                        price=transaction.amount,
                        expiry_time=None)
                    db.session.add(voucher)
                except Exception as e:
                    current_app.logger.error(f"Failed to create voucher: {str(e)}")
                    db.session.rollback()
                    return jsonify({"ResultCode": 1, "ResultDesc": "Voucher creation error"}), 500
            else:
                current_app.logger.warning(f"Duplicate voucher detected: {receipt_number}")

        elif result_code == 2001:  # Wrong PIN
            transaction.status = "FAILED"
            transaction.description = "Wrong PIN entered"
            current_app.logger.warning(f"Transaction {transaction_id} failed due to wrong PIN.")
        elif result_code == 1032:  # Cancelled by user
            transaction.status = "FAILED"
            transaction.description = "Transaction cancelled by user"
            current_app.logger.warning(f"Transaction {transaction_id} was cancelled by user.")
        else:  # Other failure cases
            transaction.status = "FAILED"
            transaction.description = result_desc
            current_app.logger.error(f"Transaction {transaction_id} failed: {result_desc}")

        # Commit database changes
        db.session.commit()

    except Exception as e:
        current_app.logger.exception(f"Unhandled error processing MPesa callback: {str(e)}")
        db.session.rollback()
        return jsonify({"ResultCode": 1, "ResultDesc": "Internal server error"}), 500

    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"}), 200



@mpesa_bp.route('/validate_voucher', methods=['POST'])
def validate_voucher():
    data = request.get_json()
    receipt_number = data.get("receipt_number")

    if not receipt_number:
        current_app.logger.info("No receipt_number provided")
        return jsonify({"status": "error", "message": "Receipt number is required"}), 400

    try:
        # Transaction validation
        current_app.logger.info(f"Validating transaction for receipt_number: {receipt_number}")
        transaction = PaymentTransaction.query.filter_by(receipt_number=receipt_number, status="SUCCESS").first()
        if not transaction:
            current_app.logger.info(f"Transaction not found or unsuccessful for receipt_number: {receipt_number}")
            return jsonify({"status": "error", "message": "Invalid or unsuccessful transaction"}), 404

        # Voucher validation
        current_app.logger.info(f"Validating voucher for code: {receipt_number}")
        voucher = Voucher.query.filter_by(code=receipt_number).first()
        if not voucher:
            current_app.logger.info(f"Voucher not found for code: {receipt_number}")
            return jsonify({"status": "error", "message": "Voucher not found"}), 404

        # Handle used voucher
        if voucher.is_used:
            if voucher.expiry_time:
                expiry_time = voucher.expiry_time.replace(tzinfo=timezone.utc).astimezone(EAT)

                if expiry_time > datetime.now(timezone.utc):
                    current_app.logger.info(f"Reconnecting to active session for voucher: {receipt_number}")
                    return jsonify({"status": "success", "message": "Reconnected to active session"}), 200

            current_app.logger.info(f"Voucher expired for code: {receipt_number}")
            return jsonify({"status": "error", "message": "Voucher expired"}), 400

        # Mark voucher as used and set expiry
        voucher.is_used = True
        voucher.expiry_time = datetime.now(EAT) + timedelta(hours=1)
        db.session.commit()

        # Successful response
        response_data = {
            "status": "success",
            "message": "Voucher validated successfully",
            "expiry_time": voucher.expiry_time.isoformat()
        }
        current_app.logger.info(f"Sending success response: {response_data}")
        return jsonify(response_data), 200

    except Exception as e:
        current_app.logger.exception(f"Error validating voucher: {str(e)}")
        db.session.rollback()
        return jsonify({"status": "error", "message": "Internal server error"}), 500



@mpesa_bp.route('/payment-status', methods=['GET'])
def payment_status():
    phone = request.args.get('phone')
    request_id = request.args.get('request_id')

    if not phone or not request_id:
        current_app.logger.error("Missing required query parameters: phone or request_id.")
        return jsonify({"status": "error", "message": "Missing required query parameters: phone or request_id"}), 400

    try:
        # Query the database for the transaction
        transaction = PaymentTransaction.query.filter_by(
            phone_number=phone, 
            checkout_request_id=request_id
        ).first()

        if not transaction:
            current_app.logger.warning(f"Transaction not found. Phone: {phone}, Request ID: {request_id}")
            return jsonify({"status": "error", "message": "Transaction not found"}), 404

        # Log the transaction status
        current_app.logger.info(f"Transaction found: {transaction.checkout_request_id}, Status: {transaction.status}")

        response_data = {
            "status": "success",
            "transaction_status": transaction.status,
            "amount": transaction.amount,
            "description": transaction.description,
            "receipt_number": transaction.receipt_number or "N/A",
            "timestamp": transaction.updated_at.isoformat() if transaction.updated_at else None
        }

        # Return JSON response
        return jsonify(response_data), 200

    except Exception as e:
        current_app.logger.exception("Error fetching payment status")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
