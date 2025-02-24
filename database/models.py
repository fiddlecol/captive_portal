from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

db = SQLAlchemy()
nairobi_tz = pytz.timezone("Africa/Nairobi")


def nairobi_now():
    return datetime.now(nairobi_tz)


class Voucher(db.Model):
    __tablename__ = 'voucher'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=nairobi_now)
    price = db.Column(db.Float, nullable=False)
    expiry_time = db.Column(db.DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Voucher {self.code}>"


class Client(db.Model):
    __tablename__ = 'client'
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(50), unique=True, nullable=False)
    voucher_id = db.Column(db.Integer, db.ForeignKey('voucher.id'))
    connected_at = db.Column(db.DateTime(timezone=True), default=nairobi_now)

    voucher = db.relationship("Voucher", backref="client")


class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transactions'

    id = db.Column(db.Integer, primary_key=True)
    checkout_request_id = db.Column(db.String(255), nullable=False, unique=True)
    merchant_request_id = db.Column(db.String(255), nullable=False)
    receipt_number = db.Column(db.String(50), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='PENDING')
    phone_number = db.Column(db.String(15), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=nairobi_now)


# Explicitly expose the models for import
__all__ = ["Voucher", "Client", "PaymentTransaction", "db"]
