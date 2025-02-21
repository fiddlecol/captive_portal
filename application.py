from flask import Flask, render_template, jsonify, send_from_directory
from database.models import db
from routes import voucher_bp, client_bp
from routes.mpesa import mpesa_bp
import os
from flask_migrate import Migrate

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
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(voucher_bp, url_prefix='/voucher')

    # Create database tables (if not already created)
    with app.app_context():
        db.create_all()

    return app

app = create_app()

# Configure movie folder
MOVIE_FOLDER = "static/movies/"
app.config["MOVIE_FOLDER"] = MOVIE_FOLDER

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

@app.route("/get_ads")
def get_ads():
    ads_folder = "static/ads/"
    images = [f for f in os.listdir(ads_folder) if f.endswith((".jpg", ".png", ".jpeg", ".gif"))]
    return jsonify(images)

# Movie Streaming Routes
@app.route("/movies")
def list_movies():
    movies = [f for f in os.listdir(app.config["MOVIE_FOLDER"]) if f.endswith((".mp4", ".mkv", ".avi"))]
    return render_template("movies.html", movies=movies)

@app.route("/movies/<filename>")
def get_movie(filename):
    return send_from_directory(app.config["MOVIE_FOLDER"], filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
