import logging

from add_product_model import menu_meal_to_product
from config_model import SitesConfig, UsersConfig
from constants import MEAL_MAPPING, DEFAULT_BRAND, LOG_FORMAT
from dietly_scraper import DietlyScraper, DietlyScraperAPIError
from fitatu_client import FitatuClient
from menu_response_model import MenuResponse
from utils import get_current_date, is_valid_response

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


async def process_user_meals(user, sites) -> bool:
    """Process meals for a single user. Returns True if successful."""
    scraper = DietlyScraper(sites.dietly, user.dietly_credentials)

    try:
        json_data = await scraper.login_and_capture_api()
        if not is_valid_response(json_data):
            logging.info("No data captured from Dietly.")
            return False

        menu = MenuResponse.model_validate(json_data)
        logging.info("Successfully retrieved menu data")

    except DietlyScraperAPIError as e:
        logging.error(f"Error while scraping Dietly API: {e}")
        return False

    return await sync_to_fitatu(menu, user, sites)


async def sync_to_fitatu(menu: MenuResponse, user, sites) -> bool:
    """Sync menu data to Fitatu. Returns True if successful."""
    fitatu = FitatuClient(
        sites_config=sites.fitatu,
        credentials=user.fitatu_credentials,
        brand=DEFAULT_BRAND,
        headless=True
    )

    try:
        login_result = await fitatu.login()
        if not is_valid_response(login_result):
            logging.error("Failed to login to Fitatu")
            return False

        meal_data = await process_meals(menu, fitatu)
        if not meal_data["meal_ids"]:
            logging.warning("No valid meals found to sync")
            return False

        success = await fitatu.publish_diet_plan(
            get_current_date(),
            meal_data["meal_ids"],
            meal_data["meal_weights"],
            MEAL_MAPPING
        )

        if success:
            logging.info(f"Successfully synced {len(meal_data['meal_ids'])} meals to Fitatu")
        return success

    except Exception as e:
        logging.error(f"Error during Fitatu processing: {e}")
        return False


async def process_meals(menu: MenuResponse, fitatu: FitatuClient) -> dict:
    """Process individual meals and return meal IDs and weights."""
    meal_ids = {}
    meal_weights = {}
    today = get_current_date()

    for meal in menu.deliveryMenuMeal:
        if meal.deliveryMealId is None:
            logging.info(f"Skipping '{meal.mealName}' - no delivery")
            continue

        product = menu_meal_to_product(meal, fitatu.brand)
        product_id = await fitatu.create_or_find_product(product, today)

        if product_id:
            meal_ids[meal.mealName] = product_id
            meal_weights[meal.mealName] = int(meal.nutrition.weight)
            logging.info(f"Processed meal: {meal.mealName}")
        else:
            logging.error(f"Failed to create/find product for {meal.mealName}")

    return {"meal_ids": meal_ids, "meal_weights": meal_weights}


async def main():
    """Main entry point for Dietly menu scraping."""
    sites = SitesConfig.load("sites.yaml")
    users = UsersConfig.load("users.yaml")

    success_count = 0
    total_users = len(users.users)

    for user in users.users:
        logging.info(f"Processing user: {user.name}")
        if await process_user_meals(user, sites):
            success_count += 1

    logging.info(f"Completed processing: {success_count}/{total_users} users successful")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
