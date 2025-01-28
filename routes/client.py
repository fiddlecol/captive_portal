from flask import Blueprint, jsonify

client_bp = Blueprint("client", __name__)


@client_bp.route("/clients", methods=["GET"])
def list_clients():
    # Logic for listing clients
    return jsonify({"clients": []})
