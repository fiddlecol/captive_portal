from flask import Flask
from extensions import db
from routes import init_routes
from models import db



def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///instance/application.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    db.init_app(app)

    # Register routes/blueprints
    from routes import init_routes
    init_routes(app)

    return app  # Return 'flask_app'


app = create_app()  # Assign the function output to 'app', keeping it global

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
