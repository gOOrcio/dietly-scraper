# Default timeouts and limits
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_SCRAPING_TIMEOUT = 15
DEFAULT_RETRY_COUNT = 3
DEFAULT_WAIT_TIMEOUT = 500
SEARCH_PAGE_LIMIT = 1

# Playwright timeouts
PLAYWRIGHT_NAVIGATION_TIMEOUT = 45000  # 45 seconds for page navigation
PLAYWRIGHT_DEFAULT_TIMEOUT = 30000     # 30 seconds for general operations

# Meal mappings
MEAL_MAPPING = {
    "Śniadanie": "breakfast",
    "II śniadanie": "second_breakfast",
    "Obiad": "dinner",
    "Podwieczorek": "snack",
    "Kolacja": "supper"
}

# API response status codes
SUCCESS_STATUS_CODES = (200, 201, 202)

# Default brands
DEFAULT_BRAND = "Dietly"

# JWT token constants
JWT_MIN_PARTS = 2
BASE64_PADDING = '='

# Logging format
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Headers constants
FITATU_HEADERS_BASE = {
    "Accept": "application/json; version=v3",
    "Referer": "https://www.fitatu.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
    "Origin": "https://www.fitatu.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Site": "same-site",
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json;charset=utf-8",
    "Sec-Fetch-Mode": "cors",
    "APP-Timezone": "Europe/Warsaw",
    "APP-Locale": "pl_PL",
    "API-Cluster": "pl-pl718304",
    "APP-StorageLocale": "pl_PL",
    "APP-OS": "FITATU-WEB",
    "APP-SearchLocale": "pl_PL",
    "Priority": "u=3, i",
    "APP-UUID": "64c2d1b0-c8ad-11e8-8956-0242ac120008",
    "APP-Location-Country": "PL",
    "APP-Version": "4.2.1",
    "API-Key": "FITATU-MOBILE-APP"
}

# Dietly constants
DIETLY_DEFAULT_API_PREFIX = "/api/company/general/menus/delivery/"
DIETLY_PROFILE_PATH = "/profil-dietly"

# Error messages
USER_ID_NOT_SET_MSG = "User ID not set. Please login first."
LOGIN_FAILED_MSG = "Login failed with status {status}"
API_RESPONSE_NOT_CAPTURED_MSG = "API response not captured within {timeout} seconds."
