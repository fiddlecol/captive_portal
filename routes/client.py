from flask import Blueprint, jsonify
from database.models import Client  # Assuming Client is defined in a models.py file
from flask_sqlalchemy import SQLAlchemy
from flask import current_app

# Create a Blueprint for client-related logic
client_bp = Blueprint("client", __name__)
db = SQLAlchemy()


@client_bp.route("/client", methods=["GET"])
def list_clients():
    """Fetch and list all clients from the database."""
    try:
        # Retrieve all clients from the database
        clients = Client.query.all()

        # Format the response as a list of dictionaries
        client_list = [
            {
                "id": client.id,
                "name": client.name,
                "email": client.email,
                "phone": client.phone,
                "created_at": client.created_at.isoformat() if client.created_at else None
            }
            for client in clients
        ]

        return jsonify({"status": "success", "clients": client_list}), 200

    except Exception as e:
        # Handle errors and log the exception
        current_app.logger.exception(f"Error retrieving clients: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
