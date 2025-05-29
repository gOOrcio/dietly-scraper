import logging
import sys
from enum import Enum
from typing import NamedTuple

from add_product_model import menu_meal_to_product
from config_model import SitesConfig, UsersConfig
from constants import MEAL_MAPPING, DEFAULT_BRAND, LOG_FORMAT
from dietly_scraper import DietlyScraper, DietlyScraperAPIError
from fitatu_client import FitatuClient
from menu_response_model import MenuResponse
from utils import get_current_date, is_valid_response

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

class SyncStatus(Enum):
    SUCCESS = "success"
    NO_MENU = "no_menu" 
    FAILED = "failed"

class UserSyncResult(NamedTuple):
    user_name: str
    status: SyncStatus
    message: str

async def process_user_meals(user, sites) -> UserSyncResult:
    """Process meals for a single user. Returns detailed sync result."""
    scraper = DietlyScraper(sites.dietly, user.dietly_credentials)

    try:
        json_data = await scraper.login_and_capture_api()
        if not is_valid_response(json_data):
            logging.info(f"No menu data found for {user.name} on {get_current_date()} - sync skipped (acceptable)")
            return UserSyncResult(user.name, SyncStatus.NO_MENU, "No menu available for today")

        menu = MenuResponse.model_validate(json_data)
        logging.info(f"Successfully retrieved menu data for {user.name}")

    except DietlyScraperAPIError as e:
        # Check if this is a "no menu found" scenario vs actual error
        if "API response not captured within" in str(e):
            logging.info(f"No menu data available for {user.name} on {get_current_date()} - sync skipped (acceptable)")
            return UserSyncResult(user.name, SyncStatus.NO_MENU, "No menu available for today")
        else:
            logging.error(f"Error while scraping Dietly API for {user.name}: {e}")
            return UserSyncResult(user.name, SyncStatus.FAILED, f"Dietly scraping failed: {e}")

    # Menu found, now try to sync to Fitatu
    sync_success = await sync_to_fitatu(menu, user, sites)
    if sync_success:
        return UserSyncResult(user.name, SyncStatus.SUCCESS, "Menu synced successfully")
    else:
        return UserSyncResult(user.name, SyncStatus.FAILED, "Fitatu sync failed")

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
            logging.error(f"Failed to login to Fitatu for {user.name}")
            return False

        meal_data = await process_meals(menu, fitatu)
        if not meal_data["meal_ids"]:
            logging.warning(f"No valid meals found to sync for {user.name}")
            return False

        success = await fitatu.publish_diet_plan(
            get_current_date(),
            meal_data["meal_ids"],
            meal_data["meal_weights"],
            MEAL_MAPPING
        )

        if success:
            logging.info(f"Successfully synced {len(meal_data['meal_ids'])} meals to Fitatu for {user.name}")
        return success

    except Exception as e:
        logging.error(f"Error during Fitatu processing for {user.name}: {e}")
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

def determine_exit_code(results: list[UserSyncResult]) -> int:
    """Determine appropriate exit code based on sync results."""
    total_users = len(results)
    successful_syncs = len([r for r in results if r.status == SyncStatus.SUCCESS])
    no_menu_users = len([r for r in results if r.status == SyncStatus.NO_MENU])
    failed_syncs = len([r for r in results if r.status == SyncStatus.FAILED])
    
    # Consider "no menu" as acceptable, not a failure
    acceptable_results = successful_syncs + no_menu_users
    
    if acceptable_results == total_users:
        # All users either synced successfully or had no menu (both acceptable)
        return 0
    elif successful_syncs > 0:
        # At least one user synced successfully, but some failed
        return 1
    else:
        # All users failed to sync (ignoring "no menu" cases)
        return 2

async def main():
    """Main entry point for Dietly menu scraping."""
    sites = SitesConfig.load("sites.yaml")
    users = UsersConfig.load("users.yaml")
    
    today = get_current_date()
    logging.info(f"Starting Dietly sync for {today}")
    
    results = []
    for user in users.users:
        logging.info(f"Processing user: {user.name}")
        result = await process_user_meals(user, sites)
        results.append(result)
    
    # Summary logging
    successful_syncs = len([r for r in results if r.status == SyncStatus.SUCCESS])
    no_menu_users = len([r for r in results if r.status == SyncStatus.NO_MENU])
    failed_syncs = len([r for r in results if r.status == SyncStatus.FAILED])
    total_users = len(results)
    
    logging.info("=== SYNC SUMMARY ===")
    logging.info(f"Total users: {total_users}")
    logging.info(f"Successful syncs: {successful_syncs}")
    logging.info(f"No menu available: {no_menu_users}")
    logging.info(f"Failed syncs: {failed_syncs}")
    
    # Detailed results
    for result in results:
        status_icon = {"success": "✅", "no_menu": "ℹ️", "failed": "❌"}[result.status.value]
        logging.info(f"{status_icon} {result.user_name}: {result.message}")
    
    # Determine exit code and final status
    exit_code = determine_exit_code(results)
    
    if exit_code == 0:
        logging.info("🎉 All users processed successfully")
    elif exit_code == 1:
        logging.warning("⚠️ Partial success - some users failed to sync")
    else:
        logging.error("💥 All users failed to sync")
    
    logging.info(f"Sync completed with exit code: {exit_code}")
    return exit_code

if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
