import logging
import uuid
from typing import Optional

from add_product_model import Product
from base_client import BaseAPIClient
from config_model import Site, FitatuCredentials
from constants import (
    FITATU_HEADERS_BASE, SEARCH_PAGE_LIMIT,
    USER_ID_NOT_SET_MSG, LOG_FORMAT
)
from utils import extract_user_id_from_jwt, get_current_timestamp, safe_get_int

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class FitatuClient(BaseAPIClient):
    token: str
    user_id: Optional[str] = None

    def __init__(self, sites_config: Site, credentials: FitatuCredentials, brand: str, headless: bool = True):
        super().__init__(headless)
        self.sites_config = sites_config
        self.credentials = credentials
        self.brand = brand

        # Build API URLs from sites config
        self.api_base = sites_config.api_url
        self.login_url = f"{self.api_base}/login"
        self.products_url = f"{self.api_base}/products"
        self.search_url = f"{self.api_base}/search/food/user"
        self.diet_plan_url = f"{self.api_base}/diet-plan"
        self.diet_activity_url = f"{self.api_base}/diet-and-activity-plan"

        headers = FITATU_HEADERS_BASE.copy()
        headers.update({
            "API-Secret": self.credentials.api_secret,
            "RequestId": str(uuid.uuid4().int % 1000)  # Generate unique request ID
        })
        self.update_headers(headers)

    @property
    def headers(self):
        return self._headers

    def update_headers(self, new_headers: dict):
        """Update or add headers for future requests."""
        self._headers.update(new_headers)

    async def login(self):
        """Login to Fitatu and extract user ID from JWT token."""
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

        self.user_id = extract_user_id_from_jwt(self.token)
        if not self.user_id:
            return None

        self.update_headers({"Authorization": f"Bearer {self.token}"})
        logging.info(f"Successfully logged in with user ID: {self.user_id}")
        return response

    async def add_product(self, product: Product):
        """Add a product using the Fitatu API."""
        # Ensure we send a dict, not a JSON string
        return await self.post(self.products_url, product.model_dump())

    async def search_product(self, name: str, date: str):
        """Search for a product by name and date in Fitatu."""
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return None

        url = f"{self.search_url}/{self.user_id}?date={date}&phrase={name}&page=1&limit={SEARCH_PAGE_LIMIT}"
        response = await self.get(url)

        if not response:
            return None

        # Ensure response is a list of dicts
        if isinstance(response, dict):
            products = response.get("products") or []
        else:
            products = response

        for product in products:
            if isinstance(product, dict) and product.get("name") == name and product.get("brand") == self.brand:
                product_id = product.get("foodId")
                logging.info(f"Product '{name}' found with ID {product_id}")
                return product_id

        logging.info(f"No exact match found for product: {name}")
        return None

    async def get_existing_diet_plan(self, date: str):
        """Retrieves existing diet plan for the given date."""
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return {}

        url = f"{self.diet_activity_url}/{self.user_id}/day/{date}"
        response = await self.get(url)

        if not response or not isinstance(response, dict):
            return {}

        diet_plan = response.get("dietPlan", {})
        return {
            meal_key: [item for item in meal_data.get("items", []) if isinstance(item, dict) and item.get("brand") == self.brand]
            for meal_key, meal_data in diet_plan.items()
        }

    async def update_diet_plan(self, date: str, diet_plan: dict):
        """Publishes the diet plan to Fitatu."""
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return False

        url = f"{self.diet_plan_url}/{self.user_id}/days"
        response = await self.post(url, diet_plan)

        success = response is not None
        if success:
            logging.info(f"Fitatu Diet Plan updated for {date}")
        else:
            logging.error(f"Failed to update diet plan for {date}")

        return success

    async def create_or_find_product(self, product: Product, date: str):
        """Finds an existing product or creates a new product in Fitatu."""
        product_id = await self.search_product(product.name, date)
        if product_id:
            return product_id

        response = await self.add_product(product)
        # Ensure response is a dict before calling get
        if isinstance(response, dict):
            return response.get("id")
        return None

    async def publish_diet_plan(self, date: str, meal_ids: dict, meal_weights: dict, meal_mapping: dict):
        """Publishes the diet plan to Fitatu with proper handling of existing meals."""
        existing_plan = await self.get_existing_diet_plan(date)
        diet_plan = {date: {"dietPlan": {}}}

        # Mark outdated meals for deletion
        for meal_key, items in existing_plan.items():
            for item in items:
                if item["productId"] not in meal_ids.values():
                    item["deletedAt"] = get_current_timestamp()
                    logging.info(f"Marking '{item.get('name', 'Unknown')}' as deleted")
            diet_plan[date]["dietPlan"][meal_key] = {"items": [item for item in items if "deletedAt" in item]}

        # Add new meals
        for meal_name, meal_id in meal_ids.items():
            self._add_meal_to_diet_plan(
                diet_plan[date]["dietPlan"],
                meal_name,
                meal_id,
                meal_weights.get(meal_name, 100),
                existing_plan,
                meal_mapping
            )

        return await self.update_diet_plan(date, diet_plan)

    @staticmethod
    def _add_meal_to_diet_plan(diet_plan: dict, meal_name: str, meal_id: str, meal_weight: int, existing_plan: dict, meal_mapping: dict):
        """Add a meal to the diet plan while avoiding duplicates."""
        mapped_key = meal_mapping.get(meal_name)
        if not mapped_key:
            logging.info(f"Skipping '{meal_name}' - not supported meal by mapping configuration")
            return

        if meal_id and mapped_key in existing_plan and any(item.get("productId") == meal_id for item in existing_plan[mapped_key]):
            logging.info(f"Skipping '{meal_name}' - already exists in diet plan")
            return

        diet_plan.setdefault(mapped_key, {"items": []})["items"].append({
            "planDayDietItemId": str(uuid.uuid1()),
            "foodType": "PRODUCT",
            "measureId": 1,
            "measureQuantity": safe_get_int(meal_weight, 100),
            "productId": meal_id,
            "source": "API",
            "updatedAt": get_current_timestamp()
        })
        logging.info(f"Added '{meal_name}' with product ID {meal_id} to diet plan")
