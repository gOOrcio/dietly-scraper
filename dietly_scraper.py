import logging
from typing import Optional, Callable, Any
from playwright.async_api import async_playwright, BrowserContext, APIRequestContext
from config_model import User, Config

class DietlyScraperAPIError(Exception): pass

def default_api_filter(request, api_url_prefix: str) -> bool:
    return api_url_prefix in request.url

async def login_with_api(request_context: APIRequestContext, user: User, config: Config) -> dict:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json, text/plain, */*",
        "Origin": config.sites.dietly,
        "Referer": config.sites.dietly,
        "User-Agent": "Mozilla/5.0"
    }
    resp = await request_context.post(
        config.sites.dietly_login,
        data=f"username={user.email}&password={user.password}&remember-me=false",
        headers=headers
    )
    if resp.status != 200:
        raise DietlyScraperAPIError(f"Login failed with status {resp.status}")
    return await resp.json()

async def set_cookies_from_api(context: BrowserContext, api_context: APIRequestContext):
    cookies = (await api_context.storage_state()).get("cookies", [])
    await context.add_cookies(cookies) if cookies else None

async def login_and_capture_api(
    config: Config,
    user: User,
    api_url_prefix: Optional[str] = None,
    api_filter: Optional[Callable[[Any], bool]] = None,
    timeout: int = 15,
    headless: bool = True
) -> Optional[dict]:
    api_url_prefix = api_url_prefix or "/api/company/general/menus/delivery/"
    logging.info("Launching browser (headless=%s)...", headless)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        api_context = await p.request.new_context(base_url=config.sites.dietly)
        await login_with_api(api_context, user, config)
        await set_cookies_from_api(context, api_context)
        page = await context.new_page()
        api_response_data, api_captured = None, False

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
            await page.goto(config.sites.dietly_menu, wait_until="networkidle")
            for _ in range(timeout * 2):
                if api_captured: break
                await page.wait_for_timeout(500)
            if not api_captured:
                raise DietlyScraperAPIError(f"API response not captured within {timeout} seconds.")
            return api_response_data
        finally:
            await browser.close()
