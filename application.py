from flask import Flask, render_template
from routes import init_routes
from models import db
import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))


def create_app():
    app = Flask(__name__)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Absolute directory of the app
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'instance/application.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Initialize database (bind db with the Flask app)
    db.init_app(app)

    # Register routes/blueprints
    init_routes(app)

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
