from datetime import datetime
import base64
import requests
import os
import time
import logging
from dotenv import load_dotenv  # Ensure dotenv is loaded

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load M-Pesa environment variables
CONSUMER_KEY = os.getenv("CONSUMER_KEY", "CONSUMER_KEY")  
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET", "CONSUMER_SECRET")
SHORTCODE = os.getenv("SHORTCODE", "SHORTCODE")  
PASSKEY = os.getenv("PASSKEY", "PASSKEY")
OAUTH_URL = os.getenv("OAUTH_URL", "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials")
CALLBACK_URL = os.getenv("CALLBACK_URL", "CALLBACK_URL")

if not SHORTCODE or not PASSKEY or not OAUTH_URL or not CALLBACK_URL or not CONSUMER_KEY or not CONSUMER_SECRET:
    raise ValueError("🚨 Missing required environment variables!")

# Cache for access token
cached_token = None
token_expiry = 0


def get_password_and_timestamp():
    """Generate Base64-encoded password for MPesa STK Push."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{SHORTCODE}{PASSKEY}{timestamp}".encode()).decode("utf-8")
    return password, timestamp


def get_access_token():
    """Generate an OAuth access token with caching and retry mechanism."""
    global cached_token, token_expiry

    # Use cached token if still valid
    if cached_token and time.time() < token_expiry:
        logger.info("✅ Using cached access token.")
        return cached_token

    try:
        auth_string = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_encoded}",
            "Content-Type": "application/json"
        }

        for attempt in range(3):  # Retry up to 3 times
            response = requests.get(OAUTH_URL, headers=headers, timeout=10)

            if response.status_code == 200:
                token_data = response.json()
                cached_token = token_data.get("access_token")
                expires_in = int(token_data.get("expires_in", 3600))  # Convert to int
                token_expiry = time.time() + expires_in - 10  # Buffer of 10s

                logger.info(f"✅ New Access Token: {cached_token}")  # Log token
                return cached_token
            else:
                logger.error(f"❌ Error generating access token: {response.status_code}, {response.text}")
                time.sleep(2 ** attempt)  # Exponential backoff

    except requests.RequestException as e:
        logger.exception(f"❌ Exception during token generation: {str(e)}")

    return None
