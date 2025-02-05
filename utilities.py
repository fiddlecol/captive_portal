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
    """
    Fetch MPesa access token, caching it to reduce API calls.
    """
    global cached_token, token_expiry

    # Use cached token if it's still valid
    if cached_token and time.time() < token_expiry:
        return cached_token

    # Request new access token
    oauth_url = OAUTH_URL
    auth = (CONSUMER_KEY, CONSUMER_SECRET)

    try:
        response = requests.get(oauth_url, auth=auth)
        response.raise_for_status()
        data = response.json()

        cached_token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)  # Default expiry 1 hour
        token_expiry = time.time() + int(expires_in) - 10  # Renew slightly before expiration

        if not cached_token:
            raise ValueError("Failed to retrieve access token!")

        current_app.logger.info(f"New Access Token Retrieved: {cached_token}")
        return cached_token
    except requests.RequestException as e:
        current_app.logger.error(f"Error fetching MPesa access token: {e}")
        raise
