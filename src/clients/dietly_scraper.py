import logging
from typing import Optional, Dict, Any

from src.clients.base_client import BaseAPIClient
from src.models.config_model import Site, DietlyCredentials
from src.models.dietly_order_models import ActiveOrdersResponse, OrderDetails
from src.utils.utils import get_current_date

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class DietlyScraperAPIError(Exception): pass


class DietlyScraper(BaseAPIClient):
    def __init__(self, site: Site, credentials: DietlyCredentials):
        super().__init__()
        self.site = site
        self.credentials = credentials

    async def login(self) -> Optional[Dict[str, Any]]:
        """Login to Dietly and return session info"""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.site.base_url,
            "Referer": self.site.base_url,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"
        }
        
        # Update headers for this session
        self.update_headers(headers)
        
        login_data = f"username={self.credentials.email}&password={self.credentials.password}&remember-me=false"
        
        response = await self.post(self.site.login_url, data=login_data)
        if not response:
            raise DietlyScraperAPIError("Login failed")
            
        logging.info("Successfully logged in to Dietly")
        return response

    async def get_active_orders(self) -> ActiveOrdersResponse:
        """Get active orders for the logged-in user"""
        headers = {
            "Accept": "*/*",
            "Referer": f"{self.site.base_url}/profil-dietly",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty"
        }
        
        # Update headers for this request
        self.update_headers(headers)
        
        response = await self.get(f"{self.site.base_url}/api/profile/profile-order/active-ids")
        if response is None:
            raise DietlyScraperAPIError("Failed to get active orders")
        
        orders_data = response
        if not orders_data:
            logging.info("No active orders found - user has no current meal plans")
            return ActiveOrdersResponse.model_validate([])
            
        active_orders = ActiveOrdersResponse.model_validate(orders_data)
        logging.info(f"Found {len(active_orders)} active order(s)")
        return active_orders

    async def get_order_details(self, order_id: int, company_name: str) -> OrderDetails:
        """Get detailed order information including deliveries"""
        headers = {
            "Accept": "*/*",
            "Referer": f"{self.site.base_url}/profil-dietly",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
            "company-id": company_name,
            "x-launcher-type": "BROWSER_DIETLY",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty"
        }
        
        # Update headers for this request
        self.update_headers(headers)
        
        response = await self.get(f"{self.site.base_url}/api/company/customer/order/{order_id}")
        if not response:
            raise DietlyScraperAPIError(f"Failed to get order details for order {order_id}")
        
        order_details = OrderDetails.model_validate(response)
        logging.info(f"Retrieved order details for order {order_id}")
        return order_details

    async def find_delivery_for_date(self, order_details: OrderDetails, target_date: str) -> Optional[int]:
        """Find delivery ID for the given date, return None if not found"""
        for delivery in order_details.deliveries:
            if delivery.date == target_date and not delivery.deleted:
                logging.info(f"Found delivery {delivery.deliveryId} for date {target_date}")
                return delivery.deliveryId
        
        logging.info(f"No delivery found for date {target_date}")
        return None

    async def get_delivery_menu(self, delivery_id: int, company_name: str) -> Dict[str, Any]:
        """Get menu data for a specific delivery"""
        headers = {
            "Accept": "*/*",
            "Referer": f"{self.site.base_url}/profil-dietly",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
            "company-id": company_name,
            "x-launcher-type": "BROWSER_DIETLY",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty"
        }
        
        # Update headers for this request
        self.update_headers(headers)
        
        response = await self.get(f"{self.site.base_url}/api/company/general/menus/delivery/{delivery_id}/new")
        if not response:
            raise DietlyScraperAPIError(f"Failed to get delivery menu for delivery {delivery_id}")
        
        logging.info(f"Retrieved menu data for delivery {delivery_id}")
        return response

    async def login_and_capture_api(self) -> Optional[Dict[str, Any]]:
        """
        Main method to login and get today's menu data using direct API calls:
        1. Login
        2. Get active orders  
        3. Get order details
        4. Find delivery for today
        5. Get menu for delivery
        """
        current_date = get_current_date()
        
        try:
            # Step 1: Login
            await self.login()
            
            # Step 2: Get active orders
            active_orders = await self.get_active_orders()
            if not active_orders or len(active_orders) == 0:
                logging.info("No active orders found - sync will be skipped")
                return None
            
            # Assume first order (as per instructions)
            first_order = active_orders[0]
            logging.info(f"Using order from company: {first_order.companyFullName} (ID: {first_order.orderId})")
            logging.info(f"Company name for headers: {first_order.companyName}")
            
            # Step 3: Get order details
            order_details = await self.get_order_details(first_order.orderId, first_order.companyName)
            
            # Step 4: Find delivery for current date
            delivery_id = await self.find_delivery_for_date(order_details, current_date)
            if delivery_id is None:
                logging.info(f"No delivery scheduled for {current_date} - sync will be skipped")
                return None
            
            # Step 5: Get menu for delivery
            menu_data = await self.get_delivery_menu(delivery_id, first_order.companyName)
            return menu_data
            
        except Exception as e:
            # Re-raise as DietlyScraperAPIError for consistent error handling
            if isinstance(e, DietlyScraperAPIError):
                raise e
            else:
                raise DietlyScraperAPIError(f"Unexpected error in API flow: {e}")
