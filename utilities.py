import requests
from datetime import datetime
import base64
from dotenv import load_dotenv


# Load environment variables from the .env file
load_dotenv()

def get_timestamp():
    """
    Generate the current timestamp in the required format (YYYYMMDDHHMMSS).
    """
    return datetime.now().strftime("%Y%m%d%H%M%S")


def generate_password():
    shortcode = "174379"
    passkey = "bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919"
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data_to_encode = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(data_to_encode.encode()).decode()
    return password

def get_access_token():
    # Replace these with your actual credentials
    consumer_key = "Wlh60goVFPOXmsmYmckZAi44rfuzFBRVUAl8QPgTNvZsOGra"
    consumer_secret = "RtCL8XMDLCfQfGO0zjpUauCFnJO6dAikMlFUaOV2RMY7tfQP0AOXyr9GbOUC7VLn"
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

    try:
        # Use Basic Authentication to send the credentials
        response = requests.get(url, auth=(consumer_key, consumer_secret))

        # Log the response for debugging
        print(f"Request URL: {url}")
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")

        # Raise an exception for HTTP errors
        response.raise_for_status()

        # Parse and return the access token
        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("No access token found in the response.")
        return access_token

    except requests.exceptions.RequestException as e:
        print(f"Error fetching access token: {e}")
        return None


# Test the function
token = get_access_token()
if token:
    print(f"\nAccess Token: {token}")
else:
    print("\nFailed to retrieve access token.")
