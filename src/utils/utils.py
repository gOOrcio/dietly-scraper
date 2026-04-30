import base64
import json
import logging
import random
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import quote

from src.utils.constants import (
    BASE64_PADDING,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
    RETRY_BACKOFF_MULTIPLIER,
    LOG_FORMAT,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def extract_user_id_from_jwt_token(token: str) -> Optional[str]:
    """Extract user ID from JWT token payload."""
    try:
        payload = token.split(".")[1]
        # Add padding if needed
        payload += BASE64_PADDING * (4 - len(payload) % 4)
        decoded = json.loads(base64.b64decode(payload))

        user_id = decoded.get("id") or decoded.get("userIdentifier")
        if user_id:
            logging.info(f"Successfully extracted user ID: {user_id}")
            return str(user_id)

        logging.error("User ID not found in JWT payload")
        return None
    except Exception as e:
        logging.error(f"Failed to decode JWT token: {e}")
        return None


def get_current_date_iso() -> str:
    """Get current date in ISO format (YYYY-MM-DD)."""
    return datetime.now().strftime("%Y-%m-%d")


def get_current_timestamp_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def is_valid_api_response(response: Optional[Dict[str, Any]]) -> bool:
    """Check if API response is valid and contains data."""
    return response is not None and isinstance(response, dict) and len(response) > 0


def safe_convert(value: Any, target_type: type, default: Any = None):
    """Safely convert value to target type with fallback."""
    if default is None:
        default = target_type()
    try:
        return target_type(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# Shortcuts for common conversions
def safe_convert_to_int(value: Any, default: int = 0) -> int:
    return safe_convert(value, int, default)


def safe_convert_to_float(value: Any, default: float = 0.0) -> float:
    return safe_convert(value, float, default)


def build_api_url(base_url: str, *path_parts: str) -> str:
    """Build API URL by combining base URL and path parts."""
    parts = [base_url.rstrip("/")] + [
        quote(str(part).strip("/")) for part in path_parts
    ]
    return "/".join(parts)


def build_query_url(base_url: str, **params: Any) -> str:
    """Build URL with query parameters."""
    if not params:
        return base_url

    query_parts = []
    for key, value in params.items():
        if isinstance(value, list):
            query_parts.extend(f"{key}[]={quote(str(item))}" for item in value)
        else:
            query_parts.append(f"{key}={quote(str(value))}")

    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{'&'.join(query_parts)}"


def calculate_retry_delay(attempt: int, jitter: bool = True) -> float:
    """Calculate exponential backoff delay with optional jitter."""
    delay = min(RETRY_BASE_DELAY * (RETRY_BACKOFF_MULTIPLIER**attempt), RETRY_MAX_DELAY)

    if jitter:
        jitter_range = delay * 0.2
        delay += random.uniform(-jitter_range, jitter_range)
        delay = max(0.1, delay)

    return delay
