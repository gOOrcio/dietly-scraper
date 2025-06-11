import logging
import sys
from enum import Enum
from typing import NamedTuple, List

from pydantic import ValidationError
from src.clients.dietly_client import DietlyClient, DietlyClientAPIError, DietlyNoActivePlanError
from src.clients.fitatu_client import FitatuClient
from src.models.add_product_model import convert_menu_meal_to_nutrition_product
from src.models.config_model import SitesConfiguration, UsersConfiguration
from src.models.menu_response_model import MenuResponse
from src.utils.constants import (
    MEAL_MAPPING, LOG_FORMAT, EXIT_CODE_SUCCESS, EXIT_CODE_PARTIAL_FAILURE, 
    EXIT_CODE_TOTAL_FAILURE, NO_MENU_MEALS_MSG, NO_ACTIVE_PLAN_MSG, RETRY_MAX_ATTEMPTS
)
from src.utils.utils import get_current_date_iso, is_valid_api_response

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class SyncStatus(Enum):
    SUCCESS = "success"
    NO_MENU = "no_menu"
    FAILED = "failed"


class UserSyncResult(NamedTuple):
    user_name: str
    status: SyncStatus
    message: str


def is_transient_error(error_msg: str) -> bool:
    """Check if an error message indicates a transient failure."""
    transient_indicators = ["503", "502", "500", "504", "connection", "timeout", "network"]
    return any(indicator in error_msg.lower() for indicator in transient_indicators)


async def process_user_meal_sync(user, sites) -> UserSyncResult:
    """Process meal synchronization for a single user with retry logic."""
    
    async def sync_attempt():
        try:
            async with DietlyClient(sites.dietly, user.dietly_credentials) as client:
                try:
                    api_result = await client.login_and_get_todays_menu()
                    if not api_result:
                        return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                    menu_data, company_name = api_result
                    if not is_valid_api_response(menu_data):
                        return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                    menu = MenuResponse.model_validate(menu_data)
                    logging.info(f"Successfully retrieved menu data for {user.name} from {company_name}")

                except DietlyNoActivePlanError:
                    return UserSyncResult(user.name, SyncStatus.SUCCESS, NO_ACTIVE_PLAN_MSG)
                except DietlyClientAPIError as e:
                    return UserSyncResult(user.name, SyncStatus.FAILED, f"Dietly API failed: {e}")

                # Sync to Fitatu
                if await sync_menu_to_fitatu(menu, company_name, user, sites):
                    return UserSyncResult(user.name, SyncStatus.SUCCESS, "Menu synced successfully")
                else:
                    return UserSyncResult(user.name, SyncStatus.FAILED, "Fitatu sync failed")

        except ValidationError as ve:
            return UserSyncResult(user.name, SyncStatus.FAILED, f"Data validation failed: {str(ve)[:200]}")
        except Exception as e:
            error_msg = str(e)
            if any(keyword in error_msg.lower() for keyword in ["timeout", "connection", "network", "http"]):
                return UserSyncResult(user.name, SyncStatus.NO_MENU, f"HTTP timeout (likely no menu): {error_msg[:100]}")
            else:
                return UserSyncResult(user.name, SyncStatus.FAILED, f"Unexpected error: {error_msg[:100]}")

    # Retry logic for transient failures
    for attempt in range(RETRY_MAX_ATTEMPTS):
        result = await sync_attempt()
        
        # Return immediately if not a transient failure or last attempt
        if (result.status != SyncStatus.FAILED or 
            not is_transient_error(result.message) or 
            attempt == RETRY_MAX_ATTEMPTS - 1):
            return result
        
        logging.warning(f"User {user.name} sync failed with transient error (attempt {attempt + 1}/{RETRY_MAX_ATTEMPTS}): {result.message}")

    return result


async def sync_menu_to_fitatu(menu: MenuResponse, company_name: str, user, sites) -> bool:
    """Synchronize menu data to Fitatu service."""
    try:
        fitatu = FitatuClient(sites.fitatu, user.fitatu_credentials, company_name)
        
        if not await fitatu.login():
            logging.error(f"Failed to login to Fitatu for {user.name}")
            return False

        meal_data = await process_menu_meals(menu, fitatu)
        if not meal_data["meal_ids"]:
            logging.warning(f"No valid meals found to sync for {user.name}")
            return False

        success = await fitatu.publish_diet_plan(
            get_current_date_iso(), meal_data["meal_ids"], 
            meal_data["meal_weights"], MEAL_MAPPING
        )

        if success:
            logging.info(f"Successfully synced {len(meal_data['meal_ids'])} meals to Fitatu for {user.name}")
        return success

    except Exception as e:
        logging.error(f"Error during Fitatu processing for {user.name}: {e}")
        return False


async def process_menu_meals(menu: MenuResponse, fitatu: FitatuClient) -> dict:
    """Process individual meals from menu and convert to Fitatu products."""
    meal_ids, meal_weights = {}, {}
    today = get_current_date_iso()

    for meal in menu.deliveryMenuMeal:
        if meal.deliveryMealId is None:
            continue

        product = convert_menu_meal_to_nutrition_product(meal, fitatu.brand)
        meal_type_english = MEAL_MAPPING.get(meal.mealName, "breakfast")
        
        if product_id := await fitatu.create_or_find_product(product, today, meal_type_english):
            meal_ids[meal.mealName] = product_id
            meal_weights[meal.mealName] = int(meal.nutrition.weight)
            logging.info(f"Processed meal: {meal.mealName}")
        else:
            logging.error(f"Failed to create/find product for {meal.mealName}")

    return {"meal_ids": meal_ids, "meal_weights": meal_weights}


def determine_sync_exit_code(results: List[UserSyncResult]) -> int:
    """Determine appropriate exit code based on synchronization results."""
    successful_syncs = sum(1 for r in results if r.status == SyncStatus.SUCCESS)
    no_menu_users = sum(1 for r in results if r.status == SyncStatus.NO_MENU)
    
    # Consider "no menu" as acceptable
    acceptable_results = successful_syncs + no_menu_users
    
    if acceptable_results == len(results):
        return EXIT_CODE_SUCCESS
    elif successful_syncs > 0:
        return EXIT_CODE_PARTIAL_FAILURE
    else:
        return EXIT_CODE_TOTAL_FAILURE


async def main():
    """Main entry point for Dietly menu synchronization."""
    sites = SitesConfiguration.load_from_file("config/sites.yaml")
    users = UsersConfiguration.load_from_file("config/users.yaml")

    logging.info(f"Starting Dietly sync for {get_current_date_iso()}")

    results = []
    for user in users.users:
        logging.info(f"Processing user: {user.name}")
        try:
            result = await process_user_meal_sync(user, sites)
            results.append(result)
        except Exception as e:
            logging.error(f"Critical error processing {user.name}: {e}")
            results.append(UserSyncResult(user.name, SyncStatus.FAILED, f"Critical error: {str(e)[:100]}"))

    # Summary
    successful_syncs = sum(1 for r in results if r.status == SyncStatus.SUCCESS and "synced successfully" in r.message)
    no_active_plan_users = sum(1 for r in results if r.status == SyncStatus.SUCCESS and NO_ACTIVE_PLAN_MSG in r.message)
    no_menu_users = sum(1 for r in results if r.status == SyncStatus.NO_MENU)
    failed_syncs = sum(1 for r in results if r.status == SyncStatus.FAILED)

    logging.info("=== SYNC SUMMARY ===")
    logging.info(f"Total users: {len(results)} | Successful: {successful_syncs} | No active plan: {no_active_plan_users} | No menu: {no_menu_users} | Failed: {failed_syncs}")

    # Detailed results
    status_icons = {"success": "✅", "no_menu": "ℹ️", "failed": "❌"}
    for result in results:
        icon = "📅" if result.status == SyncStatus.SUCCESS and NO_ACTIVE_PLAN_MSG in result.message else status_icons[result.status.value]
        logging.info(f"{icon} {result.user_name}: {result.message}")

    # Exit with appropriate code
    exit_code = determine_sync_exit_code(results)
    status_msgs = {
        EXIT_CODE_SUCCESS: "🎉 All users processed successfully",
        EXIT_CODE_PARTIAL_FAILURE: "⚠️ Partial success - some users failed to sync",
        EXIT_CODE_TOTAL_FAILURE: "💥 All users failed to sync"
    }
    
    if exit_code == EXIT_CODE_SUCCESS:
        logging.info(status_msgs[exit_code])
    elif exit_code == EXIT_CODE_PARTIAL_FAILURE:
        logging.warning(status_msgs[exit_code])
    else:
        logging.error(status_msgs[exit_code])

    sys.exit(exit_code)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
