from flask import Blueprint, jsonify

voucher_bp = Blueprint("voucher", __name__)


@voucher_bp.route("/list", methods=["GET"])
def list_vouchers():
    # Logic for listing vouchers
    return jsonify({"vouchers": []})
