from flask import Blueprint, jsonify, request
from database.models import Client
from flask_sqlalchemy import SQLAlchemy
from flask import current_app


client_bp = Blueprint("client", __name__)
db = SQLAlchemy()


@client_bp.route("/list", methods=["GET"])
def list_clients():
    """Fetch and list all clients with pagination, filtering, and sorting."""
    try:
        # Retrieve query parameters for pagination and filtering
        page = int(request.args.get("page", 1))  # Default page 1
        per_page = int(request.args.get("per_page", 10))  # Default 10 items per page
        mac_address_filter = request.args.get("mac_address", None)
        voucher_used_filter = request.args.get("voucher_used",
                                               None)  # True/False to filter clients based on voucher usage

        # Base query
        query = Client.query

        # Optional filter: Filter by mac_address (exact match)
        if mac_address_filter:
            query = query.filter_by(mac_address=mac_address_filter)

        # Optional filter: Filter by voucher usage
        if voucher_used_filter is not None:  # True or False (string comparison)
            is_used = voucher_used_filter.lower() == "true"
            query = query.join(Client.voucher).filter_by(is_used=is_used)

        # Optional sorting (default sorting by connected_at, most recent first)
        query = query.order_by(Client.connected_at.desc())

        # Paginating the results
        paginated_clients = query.paginate(page=page, per_page=per_page)

        # Format the response
        client_list = [
            {
                "id": client.id,
                "mac_address": client.mac_address,
                "voucher_id": client.voucher_id,
                "voucher_code": client.voucher.code if client.voucher else None,
                "connected_at": client.connected_at.isoformat() if client.connected_at else None,
            }
            for client in paginated_clients.items
        ]

        return jsonify({
            "status": "success",
            "clients": client_list,
            "page": paginated_clients.page,
            "per_page": paginated_clients.per_page,
            "total": paginated_clients.total,
            "pages": paginated_clients.pages
        }), 200

    except ValueError as value_error:
        # Handle parameter parsing errors (e.g., invalid page or per_page values)
        current_app.logger.error(f"Parameter parsing error: {str(value_error)}")
        return jsonify({"status": "error", "message": "Invalid query parameters"}), 400

    except Exception as e:
        # Handle unexpected errors
        current_app.logger.exception(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

