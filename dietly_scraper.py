import logging
from typing import Optional, Callable, Any
from playwright.async_api import async_playwright, BrowserContext, APIRequestContext
from config_model import User

class DietlyScraperAPIError(Exception):
    """Custom exception for Dietly API scraping errors."""
    pass

def default_api_filter(request, api_url_prefix: str) -> bool:
    """Default filter to match API requests by URL substring."""
    return api_url_prefix in request.url

async def login_with_api(request_context: APIRequestContext, user: User) -> dict:
    """Perform login via API and return response JSON."""
    login_url = "https://dietly.pl/api/auth/login"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://dietly.pl",
        "Referer": "https://dietly.pl/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"
    }
    data = f"username={user.email}&password={user.password}&remember-me=false"
    resp = await request_context.post(login_url, data=data, headers=headers)
    if resp.status != 200:
        raise DietlyScraperAPIError(f"Login failed with status {resp.status}")
    return await resp.json()

async def set_cookies_from_api(context: BrowserContext, api_context: APIRequestContext):
    """Transfer cookies from API context to browser context."""
    storage = await api_context.storage_state()
    cookies = storage.get("cookies", [])
    set_cookie_params = []
    for c in cookies:
        set_cookie_params.append({
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite", "Lax"),
        })
    if set_cookie_params:
        await context.add_cookies(set_cookie_params)

async def login_and_capture_api(
    url: str,
    user: User,
    api_url_prefix: str = "/api/company/general/menus/delivery/",
    api_filter: Optional[Callable[[Any], bool]] = None,
    timeout: int = 15,
    headless: bool = True
) -> Optional[dict]:
    """
    Log in to Dietly and capture the first matching API response.
    Args:
        url: The login page URL.
        user: User credentials.
        api_url_prefix: API URL substring to match.
        api_filter: Optional custom filter function for requests.
        timeout: Max seconds to wait for API response.
        headless: Whether to run browser in headless mode.
    Returns:
        The JSON response dict, or None if not found.
    Raises:
        DietlyScraperAPIError: On JSON parse or timeout errors.
    """
    logging.info("Launching browser (headless=%s)...", headless)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        api_context = await p.request.new_context(base_url="https://dietly.pl")
        await login_with_api(api_context, user)
        await set_cookies_from_api(context, api_context)
        page = await context.new_page()

        api_response_data = None
        api_captured = False

        async def route_handler(route, request):
            nonlocal api_response_data, api_captured
            if (api_filter and api_filter(request)) or (not api_filter and default_api_filter(request, api_url_prefix)):
                response = await route.fetch()
                try:
                    api_response_data = await response.json()
                    api_captured = True
                    logging.info("API response captured from %s", request.url)
                except Exception as e:
                    raise DietlyScraperAPIError(f"Failed to parse JSON from API response: {e}")
                await route.continue_()
                await context.unroute("**/*", route_handler)
            else:
                await route.continue_()

        await context.route("**/*", route_handler)

        try:
            await page.goto(url)
            for _ in range(timeout * 2):
                if api_captured:
                    break
                await page.wait_for_timeout(500)
            if not api_captured:
                raise DietlyScraperAPIError(f"API response not captured within {timeout} seconds.")
            return api_response_data
        finally:
            await browser.close()
