from routes.mpesa import mpesa_bp
from routes.client import client_bp
from routes.voucher import voucher_bp


def init_routes(app):
    """
    Register all Blueprints with the Flask app.
    """
    app.register_blueprint(mpesa_bp, url_prefix="/mpesa")
    app.register_blueprint(client_bp, url_prefix="/client")
    app.register_blueprint(voucher_bp, url_prefix="/voucher")
