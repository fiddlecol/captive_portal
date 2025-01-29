from flask import Flask, render_template
from extensions import db
from routes import init_routes
from models import db
from routes.mpesa import mpesa_bp



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


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/buy")
def buy():
    return render_template("buy.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
