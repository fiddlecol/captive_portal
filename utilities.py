from datetime import datetime
import base64
import requests
import os
import time
from flask import current_app
from config import OAUTH_URL, CONSUMER_KEY, CONSUMER_SECRET

# Credentials
SHORTCODE = os.getenv('SHORTCODE')
PASSKEY = os.getenv('PASSKEY')

if not SHORTCODE or not PASSKEY:
    current_app.logger.warning("SHORTCODE or PASSKEY is missing! Using defaults for testing.")
    SHORTCODE = "123456"  # Example test shortcode
    PASSKEY = "test_passkey"

# Cache for access token
cached_token = None
token_expiry = 0

def get_password_and_timestamp():
    """
    Generate Base64-encoded password for MPesa STK Push.
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{SHORTCODE}{PASSKEY}{timestamp}".encode()).decode("utf-8")
    return password, timestamp



def get_access_token():
    """Generate an OAuth access token."""
    try:
        # Encode the Consumer Key and Secret as per M-Pesa requirements
        auth_string = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_encoded}"  # Basic auth scheme
        }

        # Send the HTTP GET request to obtain the token
        response = requests.get(OAUTH_URL, headers=headers)

        if response.status_code == 200:
            # Parse token and return it
            token_data = response.json()
            return token_data.get("access_token")
        else:
            # Log the error from the API
            print(f"Error generating access token: {response.status_code}, {response.text}")
            return None

    except Exception as e:
        print(f"Exception during token generation: {str(e)}")
        return None

