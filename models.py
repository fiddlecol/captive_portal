from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Create the Flask application
app = Flask(__name__)

# Initialize extensions
db = SQLAlchemy()  # Do not pass `app` here
migrate = Migrate(app, db)  # Initialize Flask-Migrate with app and database

class Voucher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    price = db.Column(db.Float, nullable=False)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(50), unique=True, nullable=False)
    voucher_id = db.Column(db.Integer, db.ForeignKey('voucher.id'))
    connected_at = db.Column(db.DateTime, default=db.func.now())


class PaymentTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    checkout_request_id = db.Column(db.String(255), unique=True, nullable=True)
    status = db.Column(db.String(20), default="PENDING", nullable=False)
    receipt_number = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# Trigger the table creation process
if __name__ == "__main__":  # This ensures it doesn't run on model imports elsewhere
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")