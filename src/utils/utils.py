import base64
import binascii
import json
import logging
import random
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Callable, TypeVar
from urllib.parse import quote

from src.utils.constants import JWT_MIN_PARTS, BASE64_PADDING, LOG_FORMAT, RETRY_MAX_ATTEMPTS, RETRY_BASE_DELAY, RETRY_MAX_DELAY, RETRY_BACKOFF_MULTIPLIER

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

T = TypeVar('T')


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


def calculate_retry_delay(attempt: int, base_delay: float = RETRY_BASE_DELAY, 
                         max_delay: float = RETRY_MAX_DELAY, 
                         multiplier: float = RETRY_BACKOFF_MULTIPLIER,
                         jitter: bool = True) -> float:
    """Calculate exponential backoff delay with optional jitter.
    
    Args:
        attempt: Current retry attempt (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        multiplier: Exponential backoff multiplier
        jitter: Whether to add random jitter to prevent thundering herd
        
    Returns:
        Delay in seconds for this attempt
    """
    delay = base_delay * (multiplier ** attempt)
    delay = min(delay, max_delay)
    
    if jitter:
        # Add ±20% jitter to prevent thundering herd
        jitter_range = delay * 0.2
        delay += random.uniform(-jitter_range, jitter_range)
        delay = max(0.1, delay)  # Ensure minimum delay
    
    return delay


async def retry_async(
    func: Callable[..., T],
    *args,
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    retryable_exceptions: tuple = (Exception,),
    retryable_status_codes: set = None,
    **kwargs
) -> T:
    """Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Arguments to pass to the function
        max_attempts: Maximum number of attempts
        retryable_exceptions: Exceptions that should trigger retry
        retryable_status_codes: HTTP status codes that should trigger retry
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the function call
        
    Raises:
        Exception: The last exception if all retries failed
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            result = await func(*args, **kwargs)
            return result
            
        except Exception as e:
            last_exception = e
            
            # Check if this exception should trigger a retry
            should_retry = isinstance(e, retryable_exceptions)
            
            # Check for HTTP status codes in the exception message
            if retryable_status_codes and hasattr(e, 'response'):
                status_code = getattr(e.response, 'status_code', None)
                should_retry = should_retry or (status_code in retryable_status_codes)
            
            if not should_retry or attempt == max_attempts - 1:
                # Don't retry on last attempt or non-retryable exception
                raise e
            
            delay = calculate_retry_delay(attempt)
            logging.warning(
                f"Attempt {attempt + 1}/{max_attempts} failed with {type(e).__name__}: {e}. "
                f"Retrying in {delay:.2f} seconds..."
            )
            await asyncio.sleep(delay)
    
    # This should never be reached, but just in case
    raise last_exception
