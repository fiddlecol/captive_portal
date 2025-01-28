from flask import Blueprint, request, jsonify
from extensions import db
from models import PaymentTransaction
from utilities import  current_app

mpesa_bp = Blueprint("mpesa", __name__)


@mpesa_bp.route('/buy-voucher', methods=['POST'])
def buy_voucher():
    phone_number = request.json['phone_number']
    amount = request.json['amount']

    # Simulated MPESA API response
    response = {
        "MerchantRequestID": "b54f-471d-93d9-f7f3bf3f7c0e2078704",
        "CheckoutRequestID": "ws_CO_28012025210330027746919779",
        "ResponseCode": "0",
        "ResponseDescription": "Success. Request accepted for processing",
        "CustomerMessage": "Success. Request accepted for processing"
    }

    if response['ResponseCode'] == '0':  # Successful response
        checkout_request_id = response['CheckoutRequestID']

        # Check if this checkout_request_id already exists in the database
        existing_transaction = PaymentTransaction.query.filter_by(
            checkout_request_id=checkout_request_id
        ).first()

        if existing_transaction:
            # Optional: Return a response to indicate the duplicate
            return jsonify({
                "error": "Duplicate transaction",
                "message": f"A transaction with checkout_request_id '{checkout_request_id}' already exists."
            }), 400

        # Otherwise, create and save the new transaction
        new_transaction = PaymentTransaction(
            phone_number=phone_number,
            amount=amount,
            checkout_request_id=checkout_request_id,
            status="PENDING"  # Default to PENDING
        )

        db.session.add(new_transaction)
        db.session.commit()

        return jsonify({"message": "Transaction created successfully"}), 200

    return jsonify({"error": "STK Push failed"}), 400

@mpesa_bp.route('/mpesa-callback', methods=['POST'])
def mpesa_callback():
    callback_data = request.get_json()
    current_app.logger.info(f"MPesa Callback Data Received: {callback_data}")

    # Extract information from callback payload
    stk_callback = callback_data.get("Body", {}).get("stkCallback", {})
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc")
    checkout_request_id = stk_callback.get("CheckoutRequestID")
    callback_metadata = stk_callback.get("CallbackMetadata", {}).get("Item", [])

    current_app.logger.info(f"MPesa Callback ResultCode: {result_code}, ResultDesc: {result_desc}")

    # Update the corresponding transaction in the database
    from models import PaymentTransaction
    transaction = PaymentTransaction.query.filter_by(checkout_request_id=checkout_request_id).first()

    if not transaction:
        current_app.logger.error(f"Transaction not found for CheckoutRequestID: {checkout_request_id}")
        return jsonify({"ResultCode": 1, "ResultDesc": "Transaction not found"}), 404

    try:
        # If the ResultCode is `0`, it means the payment was successful
        if result_code == 0:
            transaction.status = "SUCCESS"

            # Optional: Extract useful metadata like MpesaReceiptNumber
            for item in callback_metadata:
                if item["Name"] == "MpesaReceiptNumber":
                    transaction.receipt_number = item["Value"]
        else:
            transaction.status = "FAILED"

        db.session.commit()
        current_app.logger.info(f"Updated transaction {transaction.id} status to {transaction.status}")
    except Exception as e:
        current_app.logger.error(f"Error updating transaction: {e}")
        db.session.rollback()
        return jsonify({"ResultCode": 1, "ResultDesc": "Error updating transaction"}), 500

    # Respond to MPesa
    return jsonify({"ResultCode": 0, "ResultDesc": "Callback processed successfully"})
