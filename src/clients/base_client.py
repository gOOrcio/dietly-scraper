import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union

import httpx

from src.utils.constants import DEFAULT_REQUEST_TIMEOUT, LOG_FORMAT, RETRYABLE_STATUS_CODES, RETRY_MAX_ATTEMPTS
from src.utils.utils import calculate_retry_delay

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class BaseAPIClient(ABC):
    """Base class for API clients with shared httpx request handling."""

    def __init__(self):
        self._headers: Dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    def update_headers(self, new_headers: Dict[str, str]) -> None:
        """Update or add headers for future requests."""
        self._headers.update(new_headers)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx client with session persistence."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=DEFAULT_REQUEST_TIMEOUT,
                follow_redirects=True
            )
        return self._client

    def _is_retryable_error(self, exception: Exception, status_code: Optional[int] = None) -> bool:
        """Check if an error should trigger a retry.
        
        Args:
            exception: The exception that occurred
            status_code: HTTP status code if available
            
        Returns:
            True if the error should trigger a retry
        """
        # Network-related exceptions that should be retried
        retryable_exceptions = (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.PoolTimeout,
            ConnectionError,
            OSError
        )
        
        if isinstance(exception, retryable_exceptions):
            return True
            
        # HTTP status codes that should be retried
        if status_code and status_code in RETRYABLE_STATUS_CODES:
            return True
            
        return False

    async def _make_request_with_retry(
            self,
            method: str,
            url: str,
            data: Optional[Union[str, Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request with retry logic and exponential backoff.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            data: Request data (for POST requests)
            
        Returns:
            Response data as dict if successful, None otherwise
        """
        last_exception = None
        
        for attempt in range(RETRY_MAX_ATTEMPTS):
            try:
                result = await self._make_single_request(method, url, data)
                return result
                
            except Exception as e:
                last_exception = e
                status_code = getattr(e, 'response', None)
                if hasattr(status_code, 'status_code'):
                    status_code = status_code.status_code
                else:
                    status_code = None
                
                should_retry = self._is_retryable_error(e, status_code)
                
                if not should_retry or attempt == RETRY_MAX_ATTEMPTS - 1:
                    # Don't retry on last attempt or non-retryable error
                    logging.error(f"Request failed for {method.upper()} {url}: {e}")
                    return None
                
                delay = calculate_retry_delay(attempt)
                logging.warning(
                    f"Request {method.upper()} {url} failed (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS}): {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                await asyncio.sleep(delay)
        
        # This should never be reached, but handle it gracefully
        if last_exception:
            logging.error(f"Request failed for {method.upper()} {url}: {last_exception}")
        return None

    async def _make_single_request(
            self,
            method: str,
            url: str,
            data: Optional[Union[str, Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make a single HTTP request without retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            data: Request data (for POST requests)
            
        Returns:
            Response data as dict if successful, None otherwise
            
        Raises:
            Exception: Various HTTP and network exceptions
        """
        client = await self._get_client()

        if method.upper() == "GET":
            response = await client.get(url, headers=self._headers)
        elif method.upper() == "POST":
            if isinstance(data, dict):
                response = await client.post(url, headers=self._headers, json=data)
            else:
                response = await client.post(url, headers=self._headers, content=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        logging.info(f"{method.upper()} {url} - Status: {response.status_code}")

        if response.status_code in RETRYABLE_STATUS_CODES:
            # Raise an exception for retryable status codes to trigger retry logic
            error_text = response.text
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code} error: {error_text[:200]}",
                request=response.request,
                response=response
            )
        elif response.status_code >= 400:
            # Non-retryable client errors (4xx) - don't retry
            error_text = response.text
            logging.error(f"HTTP {response.status_code} error: {error_text}")
            return None

        return response.json()

    async def _make_request(
            self,
            method: str,
            url: str,
            data: Optional[Union[str, Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request with error handling and logging.
        
        This is the main entry point that includes retry logic.
        """
        return await self._make_request_with_retry(method, url, data)

    async def get(self, url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make GET request."""
        return await self._make_request("GET", url, **kwargs)

    async def post(self, url: str, data: Optional[Union[str, Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """Make POST request."""
        return await self._make_request("POST", url, data)

    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    @abstractmethod
    async def login(self) -> Optional[Dict[str, Any]]:
        """Login method must be implemented by subclasses."""
        pass
