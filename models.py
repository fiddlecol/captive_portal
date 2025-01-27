from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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
