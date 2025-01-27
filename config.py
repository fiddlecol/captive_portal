# config.py
import os

MPESA_CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY", "default_consumer_key")
MPESA_CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "default_consumer_secret")
MPESA_AUTH_URL = os.getenv(
    "MPESA_AUTH_URL",
    "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
)
MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")  # Replace `123456` with your shortcode
MPESA_PASSKEY = os.getenv("MPESA_PASSKEY", "default_passkey")  # Replace with your passkey
MPESA_CALLBACK_URL='https://f7a6-2c0f-fe38-2326-38ac-4904-1811-35f5-11e1.ngrok-free.app/mpesa_callback'