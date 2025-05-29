import logging
import uuid
from base64 import b64decode
import json

from add_product_model import Product
from config_model import Site, FitatuCredentials
from playwright.async_api import async_playwright
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

USER_ID_NOT_SET_MSG = "User ID not set. Please login first."

class FitatuClient:
    token: str

    def __init__(self, sites_config: Site, credentials: FitatuCredentials, brand: str, headless: bool = True):
        self.sites_config = sites_config
        self.credentials = credentials
        self.headless = headless
        self.brand = brand
        self._headers = {
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
            "RequestId": "73",
            "APP-Timezone": "Europe/Warsaw",
            "APP-Locale": "pl_PL",
            "API-Cluster": "pl-pl718304",
            "APP-StorageLocale": "pl_PL",
            "APP-OS": "FITATU-WEB",
            "APP-SearchLocale": "pl_PL",
            "Priority": "u=3, i",
            "API-Secret": self.credentials.api_secret,
            "APP-UUID": "64c2d1b0-c8ad-11e8-8956-0242ac120008",
            "APP-Location-Country": "PL",
            "APP-Version": "4.2.1",
            "API-Key": "FITATU-MOBILE-APP"
        }

    @property
    def headers(self):
        return self._headers

    def update_headers(self, new_headers: dict):
        """Update or add headers for future requests."""
        self._headers.update(new_headers)

    async def login(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            await context.new_page()
            data = {
                "_username": self.credentials.email,
                "_password": self.credentials.password
            }
            request_context = await p.request.new_context()
            response = await request_context.post(
                "https://pl-pl.fitatu.com/api/login",
                headers=self._headers,
                data=data,
            )
            logging.info(f"Login response status: {response.status}")
            try:
                json_resp = await response.json()
                logging.info(f"Login response JSON: {json_resp}")
                self.token = json_resp["token"]
                try:
                    token_parts = self.token.split('.')
                    if len(token_parts) >= 2:
                        payload = json.loads(b64decode(token_parts[1] + '=' * (-len(token_parts[1]) % 4)).decode('utf-8'))
                        self.user_id = payload.get('id')
                        if not self.user_id:
                            raise ValueError("User ID not found in token payload")
                    else:
                        raise ValueError("Invalid token format")
                except Exception as e:
                    logging.error(f"Failed to extract user ID from token: {e}")
                    return None

                self.update_headers({"Authorization": f"Bearer {self.token}"})
                logging.info(f"Successfully set user ID to: {self.user_id}")
                return json_resp
            except Exception as e:
                logging.error(f"Failed to parse login response: {e}")
                return None
            finally:
                await request_context.dispose()
                await context.close()
                await browser.close()

    async def add_product(self, product: Product):
        """
        Add a product using the Fitatu API.
        """
        async with async_playwright() as p:
            request_context = await p.request.new_context()
            response = await request_context.post(
                "https://pl-pl.fitatu.com/api/products",
                headers=self._headers,
                data=product.model_dump_json()
            )
            logging.info(f"Add product response status: {response.status}")
            try:
                json_resp = await response.json()
                logging.info(f"Add product response JSON: {json_resp}")
                return json_resp
            except Exception as e:
                logging.error(f"Failed to parse add product response: {e}")
                return None
            finally:
                await request_context.dispose()

    async def search_product(self, name: str, date: str):
        """
        Search for a product by name and date in Fitatu.
        Returns the first matching product id or None.
        """
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return None
        url = f"https://pl-pl.fitatu.com/api/search/food/user/{self.user_id}?date={date}&phrase={name}&page=1&limit=1"
        async with async_playwright() as p:
            request_context = await p.request.new_context()
            response = await request_context.get(url, headers=self._headers)
            try:
                response_text = await response.text()
                logging.debug(f"Search product response text: {response_text}")

                if not response_text:
                    logging.warning(f"Empty response when searching for product: {name}")
                    return None

                products = await response.json()
                if not products:
                    logging.info(f"No products found for: {name}")
                    return None

                for product in products:
                    if product.get("name") == name and product.get("brand") == self.brand:
                        product_id = product.get("foodId")
                        logging.info(f"Product '{name}' found with ID {product_id}")
                        return product_id
                logging.info(f"No exact match found for product: {name}")
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON response: {e}. Response text: {response_text}")
            except Exception as e:
                logging.error(f"Failed to parse search product response: {e}. Response text: {response_text}")
            finally:
                await request_context.dispose()
        return None

    async def get_existing_diet_plan(self, date: str):
        """
        Retrieves existing diet plan for the given date.
        """
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return {}
        url = f"https://pl-pl.fitatu.com/api/diet-and-activity-plan/{self.user_id}/day/{date}"
        async with async_playwright() as p:
            request_context = await p.request.new_context()
            response = await request_context.get(url, headers=self._headers)
            try:
                resp = await response.json()
                return {
                    meal_key: [item for item in meal_data.get("items", []) if item.get("brand") == self.brand]
                    for meal_key, meal_data in resp.get("dietPlan", {}).items()
                } if resp else {}
            except Exception as e:
                logging.error(f"Failed to parse get diet plan response: {e}")
                return {}
            finally:
                await request_context.dispose()

    async def update_diet_plan(self, date: str, diet_plan: dict):
        """
        Publishes the diet plan to Fitatu.
        """
        if not self.user_id:
            logging.error(USER_ID_NOT_SET_MSG)
            return False
        url = f"https://pl-pl.fitatu.com/api/diet-plan/{self.user_id}/days"
        async with async_playwright() as p:
            request_context = await p.request.new_context()
            response = await request_context.post(
                url,
                headers=self._headers,
                data=diet_plan
            )
            try:
                if response.status in (200, 201, 202):
                    logging.info(f"Fitatu Diet Plan updated for {date}")
                    return True
                else:
                    logging.error(f"Failed to update diet plan for {date}: {response.status}")
                    return False
            except Exception as e:
                logging.error(f"Failed to parse update diet plan response: {e}")
                return False
            finally:
                await request_context.dispose()

    @staticmethod
    def add_meal_to_diet_plan(diet_plan: dict, meal_name: str, meal_id: str, meal_weight: int, existing_plan: dict, meal_mapping: dict):
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
            "measureQuantity": int(meal_weight),
            "productId": meal_id,
            "source": "API",
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        logging.info(f"Added '{meal_name}' with product ID {meal_id} to diet plan")

    async def create_or_find_product(self, product: Product, date: str):
        """
        Finds an existing product or creates a new product in Fitatu.
        Returns the product ID if successful, None otherwise.
        """
        product_id = await self.search_product(product.name, date)
        if (product_id):
            return product_id
        
        response = await self.add_product(product)
        return response.get("id") if response else None

    async def publish_diet_plan(self, date: str, meal_ids: dict, meal_weights: dict, meal_mapping: dict):
        """
        Publishes the diet plan to Fitatu with proper handling of existing meals.
        """
        existing_plan = await self.get_existing_diet_plan(date)
        diet_plan = {date: {"dietPlan": {}}}

        for meal_key, items in existing_plan.items():
            for item in items:
                if item["productId"] not in meal_ids.values():
                    item["deletedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logging.info(f"Marking '{item.get('name', 'Unknown')}' as deleted")
            diet_plan[date]["dietPlan"][meal_key] = {"items": [item for item in items if "deletedAt" in item]}

        for meal_name, meal_id in meal_ids.items():
            self.add_meal_to_diet_plan(
                diet_plan[date]["dietPlan"], 
                meal_name, 
                meal_id, 
                meal_weights.get(meal_name, 100), 
                existing_plan,
                meal_mapping
            )

        return await self.update_diet_plan(date, diet_plan)
