# HTTP timeout (seconds)
DEFAULT_REQUEST_TIMEOUT = 30

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
    "Kolacja": "supper",
}

# JWT token constants
BASE64_PADDING = "="

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
    "Sec-Fetch-Dest": "empty",
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
    "API-Key": "FITATU-MOBILE-APP",
}

# Fitatu rejects (HTTP 400) product names longer than this; 214 chars was seen
# accepted, 280+ rejected, 255 is the likely DB column limit.
FITATU_MAX_PRODUCT_NAME_LENGTH = 255

# Dietly constants
DIETLY_PROFILE_PATH = "/profil-dietly"

# Spring Security CSRF (double-submit cookie) required on the login POST
DIETLY_XSRF_COOKIE = "XSRF-TOKEN"
DIETLY_XSRF_HEADER = "X-XSRF-TOKEN"

# Error messages
USER_ID_NOT_SET_MSG = "User ID not set. Please login first."
NO_MENU_MEALS_MSG = "No menu meals found for the given date."
NO_ACTIVE_PLAN_MSG = "No active meal plan found for today."

# Retry configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 30.0  # seconds
RETRY_BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
