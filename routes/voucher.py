from flask import Blueprint, jsonify, current_app
from database.models import Voucher  # Assuming Voucher is defined in a models.py file
from flask_sqlalchemy import SQLAlchemy

voucher_bp = Blueprint("voucher", __name__)
db = SQLAlchemy()


@voucher_bp.route("/list", methods=["GET"])
def list_vouchers():
    """Fetch and list all vouchers from the database."""
    try:
        # Retrieve all vouchers from the database
        vouchers = Voucher.query.all()

        # Format the response as a list of dictionaries
        voucher_list = [
            {
                "id": voucher.id,
                "code": voucher.code,
                "is_used": voucher.is_used,
                "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
                "price": voucher.price
            }
            for voucher in vouchers
        ]

        return jsonify({"status": "success", "vouchers": voucher_list}), 200

    except Exception as e:
        # Handle errors and log the exception
        current_app.logger.exception(f"Error retrieving vouchers: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
