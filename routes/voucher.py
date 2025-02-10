from flask import Blueprint, jsonify, current_app, request
from database.models import Voucher  # Assuming Voucher is defined in a models.py file
from flask_sqlalchemy import SQLAlchemy

voucher_bp = Blueprint("voucher", __name__)
db = SQLAlchemy()


@voucher_bp.route("/list", methods=["GET"])
def list_vouchers():
    """Fetch and list all vouchers with detailed exception handling."""
    try:
        # Retrieve query parameters for pagination
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))

        try:
            # Execute the query and paginate results
            paginated_vouchers = Voucher.query.paginate(page=page, per_page=per_page)
        except Exception as db_error:
            current_app.logger.exception(f"Database error occurred: {str(db_error)}")
            return jsonify({"status": "error", "message": "Database query failed"}), 500

        # Format the response
        voucher_list = [
            {
                "id": voucher.id,
                "code": voucher.code,
                "is_used": voucher.is_used,
                "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
                "price": voucher.price

            }
            for voucher in paginated_vouchers.items
        ]

        return jsonify({
            "status": "success",
            "vouchers": voucher_list,
            "page": paginated_vouchers.page,
            "per_page": paginated_vouchers.per_page,
            "total": paginated_vouchers.total,
            "pages": paginated_vouchers.pages
        }), 200

    except ValueError as value_error:
        # Handle parameter parsing errors (e.g., invalid page or per_page values)
        current_app.logger.error(f"Parameter parsing error: {str(value_error)}")
        return jsonify({"status": "error", "message": "Invalid query parameters"}), 400

    except Exception as e:
        # Handle unexpected errors
        current_app.logger.exception(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

