import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.ondoperps.xyz/v1")
TOKEN_SYMBOL = os.getenv("TOKEN_SYMBOL", "BTC-USD")
INTERVAL = int(os.getenv("INTERVAL", "15"))
SPREAD_BPS = float(os.getenv("SPREAD_BPS", "10"))
ORDER_SIZE = float(os.getenv("ORDER_SIZE", "0.1"))

def validate_config():
    if not API_KEY:
        raise ValueError("API_KEY must be set in the .env file")
        
    if not API_SECRET:
        raise ValueError("API_SECRET must be set in the .env file")
    
    if SPREAD_BPS <= 0:
        raise ValueError("SPREAD_BPS must be greater than 0")
        
    if ORDER_SIZE <= 0:
        raise ValueError("ORDER_SIZE must be greater than 0")
        
    if INTERVAL <= 0:
        raise ValueError("INTERVAL must be greater than 0")

validate_config()
