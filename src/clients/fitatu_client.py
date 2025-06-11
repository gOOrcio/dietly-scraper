import logging
import uuid
from typing import Optional

from src.clients.base_client import BaseAPIClient
from src.models.add_product_model import NutritionProduct
from src.models.config_model import SiteConfiguration, FitatuCredentials
from src.utils.constants import (
    FITATU_HEADERS_BASE, SEARCH_PAGE_LIMIT, DEFAULT_MEAL_WEIGHT,
    USER_ID_NOT_SET_MSG, LOG_FORMAT
)
from src.utils.utils import (
    extract_user_id_from_jwt_token, get_current_timestamp_iso,
    safe_convert_to_int, build_api_url, build_query_url
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class FitatuClient(BaseAPIClient):
    """Client for interacting with Fitatu API for diet plan management."""

    def __init__(self, sites_config: SiteConfiguration, credentials: FitatuCredentials, brand: str):
        super().__init__()
        self.sites_config = sites_config
        self.credentials = credentials
        self.brand = brand
        self.api_base = sites_config.api_url
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None

        # Build API URLs from sites config
        self.login_url = build_api_url(self.api_base, "login")
        self.products_url = build_api_url(self.api_base, "products")
        self.search_base_url = build_api_url(self.api_base, "search", "food", "user")
        self.diet_plan_base_url = build_api_url(self.api_base, "diet-plan")
        self.diet_activity_base_url = build_api_url(self.api_base, "diet-and-activity-plan")

        headers = FITATU_HEADERS_BASE.copy()
        headers.update({
            "API-Secret": self.credentials.api_secret,
            "RequestId": str(uuid.uuid4().int % 1000)  # Generate unique request ID
        })
        self.update_headers(headers)

    def _build_search_url(self, date: str, phrase: str, meal: str = "breakfast", page: int = 1, limit: int = 40) -> str:
        """Build search URL with correct endpoint and query parameters.
        
        Args:
            date: Date for the search
            phrase: Search phrase
            meal: Meal type (default: breakfast)
            page: Page number (default: 1)
            limit: Results per page limit (default: 40)
            
        Returns:
            Complete search URL with query parameters
        """
        # Use the correct new search endpoint
        base_url = build_api_url(self.api_base, "search", "new", "food")
        return build_query_url(
            base_url,
            date=date,
            meal=meal,
            phrase=phrase,
            hasFilters="false",
            page=page,
            locale="pl_PL",
            limit=limit,
            accessType=["FREE", "PREMIUM"]
        )

    def _build_diet_plan_url(self, user_id: str) -> str:
        """Build diet plan URL for a specific user.
        
        Args:
            user_id: User ID
            
        Returns:
            Diet plan URL
        """
        return build_api_url(self.diet_plan_base_url, user_id, "days")

    def _build_diet_activity_url(self, user_id: str, date: str) -> str:
        """Build diet activity URL for a specific user and date.
        
        Args:
            user_id: User ID
            date: Target date
            
        Returns:
            Diet activity URL
        """
        return build_api_url(self.diet_activity_base_url, user_id, "day", date)

    @property
    def headers(self):
        return self._headers

    def update_headers(self, new_headers: dict):
        """Update or add headers for future requests."""
        self._headers.update(new_headers)

    async def login(self) -> Optional[dict]:
        """Login to Fitatu and extract user ID from JWT token.
        
        Returns:
            Login response data if successful, None otherwise
        """
        data = {
            "_username": self.credentials.email,
            "_password": self.credentials.password
        }

        response = await self.post(self.login_url, data)
        if not response:
            return None

        self.token = response.get("token")
        if not self.token:
            logging.error("No token received from login response")
            return None

        self.user_id = extract_user_id_from_jwt_token(self.token)
        if not self.user_id:
            return None

        self.update_headers({"Authorization": f"Bearer {self.token}"})
        logging.info(f"Successfully logged in with user ID: {self.user_id}")
        return response

    async def add_nutrition_product(self, product: NutritionProduct) -> Optional[dict]:
        """Add a nutrition product using the Fitatu API.
        
        Args:
            product: Nutrition product to add
            
        Returns:
            API response if successful, None otherwise
        """
        return await self.post(self.products_url, product.model_dump())

    async def search_product_by_name(self, name: str, date: str, meal: str = "breakfast") -> Optional[str]:
        """Search for a product by name and date in Fitatu.
        
        Args:
            name: Product name to search for
            date: Date for the search
            meal: Meal type for the search (e.g., "breakfast", "dinner")
            
        Returns:
            Product ID if found, None otherwise
        """
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return None

        url = self._build_search_url(date, name, meal)
        response = await self.get(url)

        if not response:
            logging.warning(f"Search API returned no data for '{name}' - will create new product")
            return None

        # Ensure response is a list of dicts
        try:
            if isinstance(response, dict):
                products = response.get("products") or response.get("data") or []
            elif isinstance(response, list):
                products = response
            else:
                logging.warning(f"Unexpected search response format for '{name}': {type(response)}")
                return None

            # Search for exact match
            for product in products:
                if isinstance(product, dict):
                    product_name = product.get("name", "")
                    product_brand = product.get("brand", "")
                    product_id = product.get("foodId") or product.get("id")
                    
                    if product_name == name and product_brand == self.brand and product_id:
                        logging.info(f"Product '{name}' found with ID {product_id}")
                        return str(product_id)

            logging.info(f"No exact match found for product: '{name}' with brand: '{self.brand}'")
            return None

        except Exception as e:
            logging.warning(f"Error processing search response for '{name}': {e}")
            return None

    async def get_existing_diet_plan_for_date(self, date: str) -> dict:
        """Retrieve existing diet plan for the given date.
        
        Args:
            date: Target date
            
        Returns:
            Dictionary with existing diet plan data
        """
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return {}

        url = self._build_diet_activity_url(self.user_id, date)
        response = await self.get(url)

        if not response or not isinstance(response, dict):
            return {}

        diet_plan = response.get("dietPlan", {})
        return {
            meal_key: [item for item in meal_data.get("items", []) if isinstance(item, dict) and item.get("brand") == self.brand]
            for meal_key, meal_data in diet_plan.items()
        }

    async def update_diet_plan_for_date(self, date: str, diet_plan: dict) -> bool:
        """Update the diet plan in Fitatu for a specific date.
        
        Args:
            date: Target date
            diet_plan: Diet plan data to update
            
        Returns:
            True if successful, False otherwise
        """
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return False

        url = self._build_diet_plan_url(self.user_id)
        response = await self.post(url, diet_plan)

        success = response is not None
        if success:
            logging.info(f"Fitatu Diet Plan updated for {date}")
        else:
            logging.error(f"Failed to update diet plan for {date}")

        return success

    async def create_or_find_product(self, product: NutritionProduct, date: str, meal: str = "breakfast") -> Optional[str]:
        """Find an existing product or create a new product in Fitatu.
        
        Args:
            product: Nutrition product to find or create
            date: Date for the operation
            meal: Meal type for the search (e.g., "breakfast", "dinner")
            
        Returns:
            Product ID if successful, None otherwise
        """
        product_id = await self.search_product_by_name(product.name, date, meal)
        if product_id:
            return product_id

        response = await self.add_nutrition_product(product)
        if isinstance(response, dict):
            return response.get("id")
        return None

    async def publish_diet_plan(self, date: str, meal_ids: dict, meal_weights: dict, meal_mapping: dict) -> bool:
        """Publish the complete diet plan to Fitatu with proper handling of existing meals.
        
        Args:
            date: Target date
            meal_ids: Dictionary mapping meal names to product IDs
            meal_weights: Dictionary mapping meal names to weights
            meal_mapping: Dictionary mapping meal names to Fitatu meal types
            
        Returns:
            True if successful, False otherwise
        """
        existing_plan = await self.get_existing_diet_plan_for_date(date)
        diet_plan = {date: {"dietPlan": {}}}

        # Get all existing product IDs across all meal types for this brand
        all_existing_product_ids = set()
        for meal_key, items in existing_plan.items():
            for item in items:
                if item.get("brand") == self.brand:
                    all_existing_product_ids.add(item.get("productId"))

        # Mark outdated meals for deletion (meals that exist but are not in today's menu)
        for meal_key, items in existing_plan.items():
            updated_items = []
            for item in items:
                # Only process items from our brand
                if item.get("brand") == self.brand:
                    # If this product is not in today's menu, mark it for deletion
                    if item["productId"] not in meal_ids.values():
                        item["deletedAt"] = get_current_timestamp_iso()
                        logging.info(f"Marking '{item.get('name', 'Unknown')}' as deleted (no longer in menu)")
                        updated_items.append(item)
                    # If it's in today's menu, keep it but don't re-add it
                    else:
                        logging.info(f"Keeping existing meal '{item.get('name', 'Unknown')}' - already in diet plan")
                        updated_items.append(item)
                else:
                    # Keep items from other brands unchanged
                    updated_items.append(item)
            
            if updated_items:
                diet_plan[date]["dietPlan"][meal_key] = {"items": updated_items}

        # Add new meals (only if not already present)
        for meal_name, meal_id in meal_ids.items():
            if meal_id not in all_existing_product_ids:
                self._add_meal_to_diet_plan(
                    diet_plan[date]["dietPlan"],
                    meal_name,
                    meal_id,
                    meal_weights.get(meal_name, DEFAULT_MEAL_WEIGHT),
                    existing_plan,
                    meal_mapping
                )
            else:
                logging.info(f"Skipping '{meal_name}' - product {meal_id} already exists in diet plan")

        return await self.update_diet_plan_for_date(date, diet_plan)

    @staticmethod
    def _add_meal_to_diet_plan(diet_plan: dict, meal_name: str, meal_id: str, meal_weight: int, existing_plan: dict, meal_mapping: dict) -> None:
        """Add a meal to the diet plan while avoiding duplicates.
        
        Args:
            diet_plan: Diet plan dictionary to modify
            meal_name: Name of the meal
            meal_id: Product ID of the meal
            meal_weight: Weight of the meal
            existing_plan: Existing diet plan data
            meal_mapping: Mapping from meal names to meal types
        """
        mapped_key = meal_mapping.get(meal_name)
        if not mapped_key:
            logging.info(f"Skipping '{meal_name}' - not supported meal by mapping configuration")
            return

        # Double-check that this product ID doesn't already exist in this meal category
        if mapped_key in existing_plan:
            existing_product_ids = {item.get("productId") for item in existing_plan[mapped_key] if not item.get("deletedAt")}
            if meal_id in existing_product_ids:
                logging.info(f"Skipping '{meal_name}' - product {meal_id} already exists in {mapped_key}")
                return

        # Initialize meal category if it doesn't exist
        if mapped_key not in diet_plan:
            diet_plan[mapped_key] = {"items": []}

        diet_plan[mapped_key]["items"].append({
            "planDayDietItemId": str(uuid.uuid1()),
            "foodType": "PRODUCT",
            "measureId": 1,
            "measureQuantity": safe_convert_to_int(meal_weight, DEFAULT_MEAL_WEIGHT),
            "productId": meal_id,
            "source": "API",
            "updatedAt": get_current_timestamp_iso()
        })
        logging.info(f"Added '{meal_name}' with product ID {meal_id} to diet plan ({mapped_key})")
