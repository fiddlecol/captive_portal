from flask import Blueprint, request, jsonify
from extensions import db
from utilities import  current_app

mpesa_bp = Blueprint("mpesa_bp", __name__)


@mpesa_bp.route('/buy-voucher', methods=['POST'])
def buy_voucher():
    data = request.get_json()  # Get JSON data from the frontend
    phone_number = data.get('phone_number')
    amount = data.get('amount')
    user_type = data.get('user_type')
    duration = data.get('duration')

    # Perform actions like creating a voucher and initiating payment here
    # (This would typically involve backend logic such as calls to a payment API like Mpesa)
    # Mock response (success and voucher creation simulation)
    if phone_number and amount and user_type and duration:
        # Assume you generate a voucher code like this
        transaction_reference = f"FID-{phone_number[-4:]}-{amount}"  # Mock voucher generation
        return jsonify({'success': True, 'transaction_reference': transaction_reference}), 200
    else:
        return jsonify({'success': False, 'error': 'Invalid data'}), 400


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
