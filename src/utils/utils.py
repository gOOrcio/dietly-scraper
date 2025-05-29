import json
import logging
from base64 import b64decode
from datetime import datetime
from typing import Optional, Dict, Any, Union

from src.utils.constants import JWT_MIN_PARTS, BASE64_PADDING, LOG_FORMAT

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def extract_user_id_from_jwt(token: str) -> Optional[str]:
    """Extract user ID from JWT token payload."""
    try:
        token_parts = token.split('.')
        if len(token_parts) < JWT_MIN_PARTS:
            raise ValueError("Invalid token format")

        # Add padding if needed
        payload_b64 = token_parts[1] + BASE64_PADDING * (-len(token_parts[1]) % 4)
        payload = json.loads(b64decode(payload_b64).decode('utf-8'))

        user_id = payload.get('id')
        if not user_id:
            raise ValueError("User ID not found in token payload")

        return str(user_id)
    except Exception as e:
        logging.error(f"Failed to extract user ID from token: {e}")
        return None


def get_current_date() -> str:
    """Get current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_timestamp() -> str:
    """Get current timestamp in format expected by Fitatu API."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_valid_response(response_data: Optional[Dict[str, Any]]) -> bool:
    """Check if API response is valid and not empty."""
    return response_data is not None and bool(response_data)


def safe_get_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int with default fallback."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_get_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default
