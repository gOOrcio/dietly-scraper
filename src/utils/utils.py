import base64
import binascii
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import quote

from src.utils.constants import JWT_MIN_PARTS, BASE64_PADDING, LOG_FORMAT

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def extract_user_id_from_jwt_token(token: str) -> Optional[str]:
    """Extract user ID from JWT token payload.
    
    Args:
        token: JWT token string
        
    Returns:
        User ID as string if found, None otherwise
    """
    try:
        parts = token.split('.')
        if len(parts) < JWT_MIN_PARTS:
            logging.error("Invalid JWT token format - insufficient parts")
            return None

        payload = parts[1]

        # Add padding if needed for proper base64 decoding
        missing_padding = len(payload) % 4
        if missing_padding:
            payload += BASE64_PADDING * (4 - missing_padding)

        decoded = base64.b64decode(payload)
        payload_data = json.loads(decoded)

        # Try different possible user ID field names
        user_id = payload_data.get('id') or payload_data.get('userIdentifier')
        if user_id:
            logging.info(f"Successfully extracted user ID: {user_id}")
            return str(user_id)
        else:
            logging.error("User ID not found in JWT payload - tried 'id' and 'userIdentifier' fields")
            return None

    except (json.JSONDecodeError, binascii.Error) as e:
        logging.error(f"Failed to decode JWT token: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error extracting user ID from JWT: {e}")
        return None


def get_current_date_iso() -> str:
    """Get current date in ISO format (YYYY-MM-DD).
    
    Returns:
        Current date as string in YYYY-MM-DD format
    """
    return datetime.now().strftime("%Y-%m-%d")


def get_current_timestamp_iso() -> str:
    """Get current timestamp in ISO format.
    
    Returns:
        Current timestamp as ISO string
    """
    return datetime.now().isoformat()


def is_valid_api_response(response: Optional[Dict[str, Any]]) -> bool:
    """Check if API response is valid and contains data.
    
    Args:
        response: API response to validate
        
    Returns:
        True if response is valid dict with data, False otherwise
    """
    return response is not None and isinstance(response, dict) and len(response) > 0


def safe_convert_to_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer with fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Converted integer or default value
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_convert_to_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with fallback.
    
    Args:
        value: Value to convert  
        default: Default value if conversion fails
        
    Returns:
        Converted float or default value
    """
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def build_api_url(base_url: str, endpoint: str, *path_params: str) -> str:
    """Build API URL by combining base URL, endpoint and path parameters.
    
    Args:
        base_url: Base URL (e.g., "https://api.example.com")
        endpoint: API endpoint (e.g., "/users")
        *path_params: Additional path parameters
        
    Returns:
        Complete API URL
    """
    base = base_url.rstrip('/')
    endpoint = endpoint.strip('/')

    url = f"{base}/{endpoint}"

    # Add path parameters
    for param in path_params:
        # URL encode path parameters for safety
        encoded_param = quote(str(param))
        url = f"{url}/{encoded_param}"

    return url


def build_query_url(base_url: str, **query_params: Any) -> str:
    """Build URL with query parameters.
    
    Args:
        base_url: Base URL
        **query_params: Query parameters as key-value pairs
        
    Returns:
        URL with query parameters appended
    """
    if not query_params:
        return base_url

    # URL encode query parameters
    query_string = "&".join(f"{key}={quote(str(value))}" for key, value in query_params.items())
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{query_string}"
