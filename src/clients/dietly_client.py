import logging
from typing import Optional, Dict, Any, Tuple, List

from src.clients.base_client import BaseAPIClient
from src.models.config_model import SiteConfiguration, DietlyCredentials
from src.models.dietly_order_models import ActiveOrdersResponse, OrderDetails
from src.utils.constants import (
    DIETLY_COMMON_HEADERS,
    USER_AGENT,
    DIETLY_ACTIVE_ORDERS_ENDPOINT,
    DIETLY_ORDER_DETAILS_ENDPOINT,
    DIETLY_DELIVERY_MENU_ENDPOINT,
    DIETLY_PROFILE_PATH,
)
from src.utils.utils import get_current_date_iso, build_api_url

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class DietlyClientAPIError(Exception):
    """Exception raised for Dietly API related errors."""

    pass


class DietlyNoActivePlanError(Exception):
    """Exception raised when user has no active meal plan - this is an acceptable state."""

    pass


class DietlyClient(BaseAPIClient):
    """Client for scraping Dietly API to retrieve menu data."""

    def __init__(self, site: SiteConfiguration, credentials: DietlyCredentials):
        super().__init__()
        self.site = site
        self.credentials = credentials

    def _build_common_headers(
        self, additional_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build common headers for Dietly API requests.

        Args:
            additional_headers: Optional additional headers to include

        Returns:
            Dictionary of headers for API requests
        """
        headers = DIETLY_COMMON_HEADERS.copy()
        headers["Referer"] = f"{self.site.base_url}{DIETLY_PROFILE_PATH}"

        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _build_company_headers(self, company_name: str) -> Dict[str, str]:
        """Build headers with company-specific fields.

        Args:
            company_name: Name of the company for the headers

        Returns:
            Dictionary of headers with company information
        """
        return self._build_common_headers(
            {"company-id": company_name, "x-launcher-type": "BROWSER_DIETLY"}
        )

    async def login(self) -> Optional[Dict[str, Any]]:
        """Login to Dietly and return session info.

        Returns:
            Login response data if successful, None otherwise

        Raises:
            DietlyClientAPIError: If login fails
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.site.base_url,
            "Referer": self.site.base_url,
            "User-Agent": USER_AGENT,
        }

        self.update_headers(headers)

        login_data = f"username={self.credentials.email}&password={self.credentials.password}&remember-me=false"

        response = await self.post(self.site.login_url, data=login_data)
        if not response:
            raise DietlyClientAPIError(
                "Login failed - invalid credentials or connection error"
            )

        logging.info("Successfully logged in to Dietly")
        return response

    async def get_active_orders(self) -> ActiveOrdersResponse:
        """Get active orders for the logged-in user.

        Returns:
            ActiveOrdersResponse containing list of active orders

        Raises:
            DietlyClientAPIError: If API request fails
            DietlyNoActivePlanError: If user has no active meal plans (acceptable state)
        """
        headers = self._build_common_headers()
        self.update_headers(headers)

        url = build_api_url(self.site.base_url, DIETLY_ACTIVE_ORDERS_ENDPOINT)
        response = await self.get(url)

        if response is None:
            raise DietlyClientAPIError(
                "Failed to get active orders - API request failed"
            )

        if not response:
            # No active orders is an acceptable state - user doesn't have a meal plan
            logging.info("No active orders found - user has no current meal plans")
            raise DietlyNoActivePlanError("User has no active meal plans for today")

        active_orders = ActiveOrdersResponse.model_validate(response)
        logging.info(f"Found {len(active_orders)} active order(s)")
        return active_orders

    async def get_order_details(self, order_id: int, company_name: str) -> OrderDetails:
        """Get detailed order information including deliveries.

        Args:
            order_id: ID of the order to retrieve
            company_name: Name of the company for headers

        Returns:
            OrderDetails containing complete order information

        Raises:
            DietlyClientAPIError: If API request fails
        """
        headers = self._build_company_headers(company_name)
        self.update_headers(headers)

        url = build_api_url(
            self.site.base_url, DIETLY_ORDER_DETAILS_ENDPOINT, str(order_id)
        )
        response = await self.get(url)

        if not response:
            raise DietlyClientAPIError(
                f"Failed to get order details for order {order_id} - API request failed"
            )

        order_details = OrderDetails.model_validate(response)
        logging.info(f"Retrieved order details for order {order_id}")
        return order_details

    @staticmethod
    async def find_delivery_for_date(
        order_details: OrderDetails, target_date: str
    ) -> Optional[int]:
        """Find delivery ID for the given date.

        Args:
            order_details: Order details containing deliveries
            target_date: Target date to find delivery for

        Returns:
            Delivery ID if found, None otherwise

        Raises:
            DietlyNoActivePlanError: If no delivery found for the date (acceptable state)
        """
        for delivery in order_details.deliveries:
            if delivery.date == target_date and not delivery.deleted:
                logging.info(
                    f"Found delivery {delivery.deliveryId} for date {target_date}"
                )
                return delivery.deliveryId

        # No delivery for this date is acceptable - user might not have planned meals
        logging.info(f"No delivery found for date {target_date}")
        raise DietlyNoActivePlanError(f"No meal delivery scheduled for {target_date}")

    async def get_delivery_menu(
        self, delivery_id: int, company_name: str
    ) -> Dict[str, Any]:
        """Get menu data for a specific delivery.

        Args:
            delivery_id: ID of the delivery to get menu for
            company_name: Name of the company for headers

        Returns:
            Dictionary containing menu data

        Raises:
            DietlyClientAPIError: If API request fails
        """
        headers = self._build_company_headers(company_name)
        self.update_headers(headers)

        url = build_api_url(
            self.site.base_url, DIETLY_DELIVERY_MENU_ENDPOINT, str(delivery_id), "new"
        )
        response = await self.get(url)

        if not response:
            raise DietlyClientAPIError(
                f"Failed to get delivery menu for delivery {delivery_id} - API request failed"
            )

        logging.info(f"Retrieved menu data for delivery {delivery_id}")
        return response

    async def login_and_get_todays_menu(
        self,
    ) -> Optional[Tuple[List[Tuple[Dict[str, Any], str]], str]]:
        """Main method to login and get today's menu data using direct API calls.

        Performs the complete API flow:
        1. Login
        2. Get active orders
        3. Get order details for each order
        4. Find delivery for today for each order
        5. Get menu for each delivery

        Returns:
            Tuple of (list of (menu_data, company_name) tuples, primary_company_name) if menus found, None otherwise

        Raises:
            DietlyNoActivePlanError: When user has no active meal plan (acceptable state)
            DietlyClientAPIError: For any actual API-related errors (failures)
        """
        current_date = get_current_date_iso()

        try:
            # Step 1: Login
            await self.login()

            # Step 2: Get active orders
            active_orders = await self.get_active_orders()

            if not active_orders:
                raise DietlyNoActivePlanError("No active orders found")

            logging.info(f"Found {len(active_orders)} active order(s)")

            # Process all active orders
            menu_results = []
            primary_company_name = None

            for i, order in enumerate(active_orders):
                try:
                    logging.info(
                        f"Processing order {i + 1}/{len(active_orders)} from company: {order.companyFullName} (ID: {order.orderId})"
                    )
                    logging.info(f"Company name for headers: {order.companyName}")

                    # Step 3: Get order details
                    order_details = await self.get_order_details(
                        order.orderId, order.companyName
                    )

                    # Step 4: Find delivery for current date
                    delivery_id = await self.find_delivery_for_date(
                        order_details, current_date
                    )

                    # Step 5: Get menu for delivery
                    menu_data = await self.get_delivery_menu(
                        delivery_id, order.companyName
                    )

                    # Store the result with order ID to make it unique
                    unique_company_name = (
                        f"{order.companyFullName} (Order {order.orderId})"
                    )
                    menu_results.append((menu_data, unique_company_name))

                    # Use the first order's company name as primary
                    if primary_company_name is None:
                        primary_company_name = order.companyFullName

                except DietlyNoActivePlanError as e:
                    logging.warning(
                        f"No delivery found for order {order.orderId} on {current_date}: {e}"
                    )
                    # Continue processing other orders
                    continue
                except Exception as e:
                    logging.error(f"Error processing order {order.orderId}: {e}")
                    # Continue processing other orders
                    continue

            if not menu_results:
                raise DietlyNoActivePlanError(
                    f"No valid deliveries found for {current_date} across all orders"
                )

            logging.info(
                f"Successfully processed {len(menu_results)} order(s) with valid deliveries"
            )
            return menu_results, primary_company_name

        except DietlyNoActivePlanError:
            # Re-raise this as it's an acceptable state that should be handled differently
            raise
        except DietlyClientAPIError:
            # Re-raise API errors as they are true failures
            raise
        except Exception as e:
            # Convert any unexpected errors to API errors (failures)
            raise DietlyClientAPIError(f"Unexpected error in API flow: {e}")
