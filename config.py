# config.py
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()


# Read the variables
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
PASSKEY = os.getenv("PASSKEY")
SHORTCODE = os.getenv("SHORTCODE")
CALLBACK_URL = os.getenv("CALLBACK_URL")
STK_PUSH_URL=os.getenv("STK_PUSH_URL")
OAUTH_URL = os.getenv("OAUTH_URL")

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///instance/application.db"  # Default path for SQLite
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CONSUMER_KEY = os.getenv("CONSUMER_KEY", "CONSUMER_KEY")