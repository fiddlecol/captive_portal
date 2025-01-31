# config.py
import os
from dotenv import load_dotenv
from flask import current_app

# Load environment variables from the .env file
load_dotenv()


# Read the variables
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
PASSKEY = os.getenv("PASSKEY")
SHORTCODE = os.getenv("SHORTCODE")
CALLBACK_URL = os.getenv("CALLBACK_URL")
LIPA_NA_MPESA_URL="https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
AUTH_URL = os.getenv( "AUTH_URL", "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
)


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///instance/application.db"  # Default path for SQLite
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CONSUMER_KEY = os.getenv("CONSUMER_KEY", "your_default_key")
