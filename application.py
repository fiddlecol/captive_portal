from flask import Flask, render_template
from database.models import db
from routes.mpesa import mpesa_bp
import os
from flask_migrate import Migrate
# Remove this line if unused
from database.models import PaymentTransaction



def create_app():
    app = Flask(__name__)

    # Configure the SQLite database
    base_dir = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(base_dir, 'instance/application.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Initialize database (bind db with the Flask app)
    db.init_app(app)
    migrate = Migrate(app, db)  # enable migration

    # Register routes/blueprints
    app.register_blueprint(mpesa_bp, url_prefix="/mpesa")


    # Create database tables (if not already created)
    with app.app_context():
        db.create_all()

    return app


app = create_app()


@app.route("/")
def home():
    return render_template("login.html")


@app.route("/buy")
def buy():
    return render_template("buy.html")


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/routes", methods=['GET'])
def list_routes():
    # List all registered routes in the application for debugging
    routes = [str(rule) for rule in app.url_map.iter_rules()]
    return {"routes": routes}



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
