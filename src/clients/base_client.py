import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
import httpx

from src.utils.constants import DEFAULT_REQUEST_TIMEOUT, LOG_FORMAT

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class BaseAPIClient(ABC):
    """Base class for API clients with shared httpx request handling."""

    def __init__(self, headless: bool = True):
        self.headless = headless  # Keep for backwards compatibility, not used with httpx
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

    async def _make_request(
            self,
            method: str,
            url: str,
            data: Optional[Union[str, Dict[str, Any]]] = None,
            timeout: int = DEFAULT_REQUEST_TIMEOUT
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request with error handling and logging."""
        client = await self._get_client()
        
        try:
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

            if response.status_code >= 400:
                error_text = response.text
                logging.error(f"HTTP {response.status_code} error: {error_text}")
                return None

            return response.json()

        except Exception as e:
            logging.error(f"Request failed for {method.upper()} {url}: {e}")
            return None

    async def get(self, url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make GET request."""
        return await self._make_request("GET", url, **kwargs)

    async def post(self, url: str, data: Optional[Union[str, Dict[str, Any]]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Make POST request."""
        return await self._make_request("POST", url, data, **kwargs)

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
