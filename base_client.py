import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union

from playwright.async_api import async_playwright

from constants import DEFAULT_REQUEST_TIMEOUT, LOG_FORMAT

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class BaseAPIClient(ABC):
    """Base class for API clients with shared Playwright request handling."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._headers: Dict[str, str] = {}

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    def update_headers(self, new_headers: Dict[str, str]) -> None:
        """Update or add headers for future requests."""
        self._headers.update(new_headers)

    async def _make_request(
            self,
            method: str,
            url: str,
            data: Optional[Union[str, Dict[str, Any]]] = None,
            timeout: int = DEFAULT_REQUEST_TIMEOUT
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request with error handling and logging."""
        async with async_playwright() as p:
            request_context = await p.request.new_context()
            try:
                if method.upper() == "GET":
                    response = await request_context.get(url, headers=self._headers)
                elif method.upper() == "POST":
                    response = await request_context.post(url, headers=self._headers, data=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                logging.info(f"{method.upper()} {url} - Status: {response.status}")

                if response.status >= 400:
                    error_text = await response.text()
                    logging.error(f"HTTP {response.status} error: {error_text}")
                    return None

                return await response.json()

            except Exception as e:
                logging.error(f"Request failed for {method.upper()} {url}: {e}")
                return None
            finally:
                await request_context.dispose()

    async def get(self, url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Make GET request."""
        return await self._make_request("GET", url, **kwargs)

    async def post(self, url: str, data: Optional[Union[str, Dict[str, Any]]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Make POST request."""
        return await self._make_request("POST", url, data, **kwargs)

    @abstractmethod
    async def login(self) -> Optional[Dict[str, Any]]:
        """Login method must be implemented by subclasses."""
        pass
