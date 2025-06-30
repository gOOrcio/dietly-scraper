import logging
import uuid
from typing import Optional, Dict, Any

from src.clients.base_client import BaseAPIClient
from src.models.add_product_model import NutritionProduct
from src.models.config_model import SiteConfiguration, FitatuCredentials
from src.utils.constants import (
    FITATU_HEADERS_BASE, SEARCH_PAGE_LIMIT, DEFAULT_MEAL_WEIGHT,
    USER_ID_NOT_SET_MSG, LOG_FORMAT
)
from src.utils.decorators import require_user_id, log_api_call
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

    @log_api_call("Login")
    async def login(self) -> Optional[Dict[str, Any]]:
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

    async def add_nutrition_product(self, product: NutritionProduct) -> Optional[Dict[str, Any]]:
        """Add a nutrition product using the Fitatu API.
        
        Args:
            product: Nutrition product to add
            
        Returns:
            API response if successful, None otherwise
        """
        return await self.post(self.products_url, product.model_dump())

    @require_user_id
    async def search_product_by_name(self, name: str, date: str, meal: str = "breakfast") -> Optional[str]:
        """Search for a product by name and date in Fitatu."""
        url = self._build_search_url(date, name, meal)
        response = await self.get(url)

        if not response:
            logging.warning(f"Search API returned no data for '{name}' - will create new product")
            return None

        try:
            # Handle different response formats
            if isinstance(response, dict):
                products = response.get("products") or response.get("data") or []
            elif isinstance(response, list):
                products = response
            else:
                logging.warning(f"Unexpected search response format for '{name}': {type(response)}")
                return None

            # Search for exact matches - prefer brand matches first
            exact_matches = []
            no_brand_matches = []
            
            for product in products:
                if isinstance(product, dict):
                    product_name = product.get("name", "")
                    product_brand = product.get("brand", "")
                    product_id = product.get("foodId") or product.get("id")
                    
                    if product_name == name and product_id:
                        # Exact name match found
                        if product_brand == self.brand:
                            # Perfect match - same name and brand
                            logging.info(f"Found exact match: '{name}' with brand '{self.brand}' (ID: {product_id})")
                            return str(product_id)
                        elif not product_brand or product_brand.strip() == "":
                            # Name match but no brand - save for potential fallback but prefer creating new
                            no_brand_matches.append((product_id, product_brand))
                            logging.warning(f"Found product '{name}' with NO BRAND (ID: {product_id}) - will create new product with brand '{self.brand}' instead")
                        else:
                            # Name match but different brand - save as potential fallback
                            exact_matches.append((product_id, product_brand))

            # If no perfect brand match, prefer creating new product over using one without brand
            if exact_matches:
                product_id, found_brand = exact_matches[0]
                logging.info(f"Using name match: '{name}' with brand '{found_brand}' (ID: {product_id}) - no exact brand match found")
                return str(product_id)
            
            # If we have no brand matches, log and create new product instead
            if no_brand_matches:
                product_id, found_brand = no_brand_matches[0]
                logging.warning(f"Found {len(no_brand_matches)} product(s) without brand for '{name}' (ID: {product_id}) - creating new product with brand '{self.brand}' instead")
                return None

            logging.info(f"No match found for product: '{name}' - will create new product")
            return None

        except Exception as e:
            logging.warning(f"Error processing search response for '{name}': {e}")
            return None

    @require_user_id
    async def get_existing_diet_plan_for_date(self, date: str) -> Dict[str, Any]:
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

    @require_user_id
    @log_api_call("Diet plan update")
    async def update_diet_plan_for_date(self, date: str, diet_plan: Dict[str, Any]) -> bool:
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
        
        # Log the diet plan structure for debugging
        logging.debug(f"Updating diet plan for {date} with {len(diet_plan.get(date, {}).get('dietPlan', {}))} meal categories")
        for meal_key, meal_data in diet_plan.get(date, {}).get('dietPlan', {}).items():
            item_count = len(meal_data.get('items', []))
            logging.debug(f"  {meal_key}: {item_count} items")
        
        response = await self.post(url, diet_plan)

        success = response is not None
        if success:
            logging.info(f"Fitatu Diet Plan updated for {date}")
            logging.debug(f"API response: {response}")
        else:
            logging.error(f"Failed to update diet plan for {date} - no response from API")

        return success

    async def create_or_find_product(self, product: NutritionProduct, date: str, meal: str = "breakfast") -> Optional[str]:
        """Find an existing product or create a new product in Fitatu."""
        # First try: Search API
        product_id = await self.search_product_by_name(product.name, date, meal)
        if product_id:
            logging.info(f"Using existing product '{product.name}' with ID {product_id}")
            return product_id

        # Second try: Check existing diet plan for product with same name
        product_id = await self._find_product_in_existing_plan(product.name, date)
        if product_id:
            logging.info(f"Found product '{product.name}' in existing diet plan with ID {product_id}")
            return product_id

        # Last resort: Create new product
        logging.info(f"Creating new product: '{product.name}' with brand '{product.brand}'")
        response = await self.add_nutrition_product(product)
        if isinstance(response, dict):
            new_product_id = response.get("id")
            if new_product_id:
                logging.debug(f"Successfully created new product '{product.name}' with ID {new_product_id}")
            return new_product_id
        else:
            logging.error(f"Failed to create new product '{product.name}' - invalid response format")
            return None

    async def _find_product_in_existing_plan(self, product_name: str, date: str) -> Optional[str]:
        """Find a product in the existing diet plan by name, preferring the most recently added."""
        try:
            existing_plan = await self.get_existing_diet_plan_for_date(date)
            
            # Collect all matching products with their timestamps
            matching_products = []
            
            for meal_key, items in existing_plan.items():
                for item in items:
                    if (item.get("brand") == self.brand and 
                        item.get("name") == product_name and 
                        not item.get("deletedAt")):
                        
                        product_id = item.get("productId")
                        updated_at = item.get("updatedAt", "")
                        
                        if product_id:
                            matching_products.append((product_id, updated_at, meal_key))
            
            if matching_products:
                # Sort by updatedAt timestamp (most recent first)
                matching_products.sort(key=lambda x: x[1], reverse=True)
                most_recent_id = matching_products[0][0]
                
                logging.debug(f"Found {len(matching_products)} existing products for '{product_name}', using most recent: {most_recent_id}")
                return str(most_recent_id)
            
            return None
        except Exception as e:
            logging.warning(f"Error searching existing diet plan for '{product_name}': {e}")
            return None

    async def publish_diet_plan(self, date: str, meal_ids: Dict[str, str], 
                              meal_weights: Dict[str, int], meal_mapping: Dict[str, str]) -> bool:
        """Publish the complete diet plan to Fitatu - only add new meals that don't already exist."""
        existing_plan = await self.get_existing_diet_plan_for_date(date)
        diet_plan = {date: {"dietPlan": {}}}
        
        # Get all current product IDs from today's menu
        current_product_ids = set(meal_ids.values())
        logging.info(f"Today's menu contains {len(current_product_ids)} products")
        logging.debug(f"Product IDs: {current_product_ids}")
        
        # Log each product ID for debugging
        for meal_name, product_id in meal_ids.items():
            logging.debug(f"Product mapping: '{meal_name}' -> ID {product_id}")
        
        # Find which products already exist in the diet plan
        existing_product_ids = set()
        for meal_key, items in existing_plan.items():
            for item in items:
                if item.get("brand") == self.brand and not item.get("deletedAt"):
                    product_id = item.get("productId")
                    if product_id:
                        existing_product_ids.add(str(product_id))  # Convert to string for comparison

        logging.info(f"Existing diet plan contains {len(existing_product_ids)} products")
        logging.debug(f"Existing product IDs: {existing_product_ids}")
        
        # Copy existing diet plan structure without modifications
        for meal_key, items in existing_plan.items():
            if items:  # Only copy if there are items
                diet_plan[date]["dietPlan"][meal_key] = {"items": items}

        # Add only NEW meals (not already in diet plan)
        new_meals_added = 0
        for meal_name, meal_id in meal_ids.items():
            if str(meal_id) not in existing_product_ids:  # Ensure string comparison
                logging.debug(f"Adding new meal '{meal_name}' with product ID {meal_id} to diet plan")
                
                # Validate that the product ID looks reasonable (not empty, not None)
                if not meal_id or str(meal_id).strip() == "":
                    logging.error(f"Skipping '{meal_name}' - invalid product ID: {meal_id}")
                    continue
                
                self._add_meal_to_diet_plan(
                    diet_plan[date]["dietPlan"], meal_name, meal_id,
                    meal_weights.get(meal_name, DEFAULT_MEAL_WEIGHT),
                    existing_plan, meal_mapping
                )
                new_meals_added += 1
            else:
                logging.debug(f"Skipping '{meal_name}' (ID: {meal_id}) - already exists in diet plan")
        
        if new_meals_added > 0:
            logging.info(f"Adding {new_meals_added} new meals to diet plan")
            return await self.update_diet_plan_for_date(date, diet_plan)
        else:
            logging.info("No new meals to add - diet plan is already up to date")
            return True  # Consider this a success since nothing needed to be done

    def _add_meal_to_diet_plan(self, diet_plan: Dict[str, Any], meal_name: str, meal_id: str, 
                             meal_weight: int, existing_plan: Dict[str, Any], 
                             meal_mapping: Dict[str, str]) -> None:
        """Add a meal to the diet plan while avoiding duplicates.
        
        Args:
            diet_plan: Diet plan dictionary to modify
            meal_name: Name of the meal
            meal_id: Product ID of the meal
            meal_weight: Weight of the meal
            existing_plan: Existing diet plan data
            meal_mapping: Mapping from meal names to meal types
        """
        if not (mapped_key := meal_mapping.get(meal_name)):
            logging.info(f"Skipping '{meal_name}' - not supported meal by mapping configuration")
            return

        # Check for duplicates in this meal category
        if mapped_key in existing_plan:
            existing_product_ids = {item.get("productId") for item in existing_plan[mapped_key] 
                                  if not item.get("deletedAt")}
            if meal_id in existing_product_ids:
                logging.info(f"Skipping '{meal_name}' - product {meal_id} already exists in {mapped_key}")
                return

        # Initialize meal category if needed
        if mapped_key not in diet_plan:
            diet_plan[mapped_key] = {"items": []}

        # Create the meal item with proper brand information
        meal_item = {
            "planDayDietItemId": str(uuid.uuid1()),
            "foodType": "PRODUCT",
            "measureId": 1,
            "measureQuantity": safe_convert_to_int(meal_weight, DEFAULT_MEAL_WEIGHT),
            "productId": meal_id,
            "source": "API",
            "updatedAt": get_current_timestamp_iso(),
            "brand": self.brand  # Add brand information to ensure proper product identification
        }
        
        diet_plan[mapped_key]["items"].append(meal_item)
        logging.info(f"Added '{meal_name}' with product ID {meal_id} and brand '{self.brand}' to diet plan ({mapped_key})")
