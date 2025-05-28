import logging
from typing import Optional, Callable, Any
from playwright.async_api import async_playwright, BrowserContext, APIRequestContext
from config_model import User, Config, DietlyCredentials


class DietlyScraperAPIError(Exception): pass

class DietlyScraper:
    def __init__(self, config: Config, credentials: DietlyCredentials, headless: bool = True):
        self.config = config
        self.credentials = credentials
        self.headless = headless

    @staticmethod
    def default_api_filter(request, api_url_prefix: str) -> bool:
        return api_url_prefix in request.url

    async def login_with_api(self, request_context: APIRequestContext) -> dict:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.config.sites.dietly.base_url,
            "Referer": self.config.sites.dietly.base_url,
            "User-Agent": "Mozilla/5.0"
        }
        resp = await request_context.post(
            self.config.sites.dietly.login_url,
            data=f"username={self.credentials.email}&password={self.credentials.password}&remember-me=false",
            headers=headers
        )
        if resp.status != 200:
            raise DietlyScraperAPIError(f"Login failed with status {resp.status}")
        return await resp.json()

    @staticmethod
    async def set_cookies_from_api(context: BrowserContext, api_context: APIRequestContext):
        cookies = (await api_context.storage_state()).get("cookies", [])
        await context.add_cookies(cookies) if cookies else None

    async def login_and_capture_api(
        self,
        api_url_prefix: Optional[str] = None,
        api_filter: Optional[Callable[[Any], bool]] = None,
        timeout: int = 15
    ) -> Optional[dict]:
        api_url_prefix = api_url_prefix or "/api/company/general/menus/delivery/"
        logging.info("Launching browser (headless=%s)...", self.headless)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            api_context = await p.request.new_context(base_url=self.config.sites.dietly.base_url)
            await self.login_with_api(api_context)
            await self.set_cookies_from_api(context, api_context)
            page = await context.new_page()
            api_response_data, api_captured = None, False

            async def route_handler(route, request):
                nonlocal api_response_data, api_captured
                if (api_filter and api_filter(request)) or (not api_filter and self.default_api_filter(request, api_url_prefix)):
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
                await page.goto(self.config.sites.dietly.base_url + "/profil-dietly", wait_until="networkidle")
                for _ in range(timeout * 2):
                    if api_captured: break
                    await page.wait_for_timeout(500)
                if not api_captured:
                    raise DietlyScraperAPIError(f"API response not captured within {timeout} seconds.")
                return api_response_data
            finally:
                await browser.close()
