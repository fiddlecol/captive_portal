from flask import Flask, render_template
from routes import init_routes
from models import db
import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))



def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/application.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


    # Initialize extensions
    db.init_app(app)

    # Register routes/blueprints
    init_routes(app)

    return app  # Return 'flask_app'


app = create_app()  # Assign the function output to 'app', keeping it global


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
