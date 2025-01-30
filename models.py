from flask import Flask
from extensions import db

# Create the Flask application
app = Flask(__name__)


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
    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    checkout_request_id = db.Column(db.String(50), unique=True, nullable=False)
    phone_number = db.Column(db.String(12), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="PENDING")
    receipt_number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f"<PaymentTransaction {self.checkout_request_id}>"


# Trigger the table creation process
if __name__ == "__main__":  # This ensures it doesn't run on model imports elsewhere
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")