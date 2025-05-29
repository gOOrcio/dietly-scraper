# Default timeouts and limits
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_SCRAPING_TIMEOUT = 15
DEFAULT_RETRY_COUNT = 3
DEFAULT_WAIT_TIMEOUT = 500
SEARCH_PAGE_LIMIT = 1

# HTTP timeouts
HTTP_REQUEST_TIMEOUT = 30
HTTP_CONNECTION_TIMEOUT = 10

# Exit codes for main script
EXIT_CODE_SUCCESS = 0  # All users processed successfully
EXIT_CODE_PARTIAL_FAILURE = 1  # Some users failed
EXIT_CODE_TOTAL_FAILURE = 2  # All users failed

# Default values
DEFAULT_MEAL_WEIGHT = 100

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

# JWT token constants
JWT_MIN_PARTS = 2
BASE64_PADDING = '='

# Logging format
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Common User Agent
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"

# Dietly API endpoints
DIETLY_ACTIVE_ORDERS_ENDPOINT = "/api/profile/profile-order/active-ids"
DIETLY_ORDER_DETAILS_ENDPOINT = "/api/company/customer/order"
DIETLY_DELIVERY_MENU_ENDPOINT = "/api/company/general/menus/delivery"

# Dietly common headers
DIETLY_COMMON_HEADERS = {
    "Accept": "*/*",
    "User-Agent": USER_AGENT,
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty"
}

# Headers constants
FITATU_HEADERS_BASE = {
    "Accept": "application/json; version=v3",
    "Referer": "https://www.fitatu.com/",
    "User-Agent": USER_AGENT,
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
NO_MENU_MEALS_MSG = "No menu meals found for the given date."
