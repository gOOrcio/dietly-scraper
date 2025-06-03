import logging
import sys
from enum import Enum
from typing import NamedTuple

from pydantic import ValidationError
from src.clients.dietly_client import DietlyClient, DietlyClientAPIError, DietlyNoActivePlanError
from src.clients.fitatu_client import FitatuClient
from src.models.add_product_model import convert_menu_meal_to_nutrition_product
from src.models.config_model import SitesConfiguration, UsersConfiguration
from src.models.menu_response_model import MenuResponse
from src.utils.constants import MEAL_MAPPING, LOG_FORMAT, EXIT_CODE_SUCCESS, EXIT_CODE_PARTIAL_FAILURE, EXIT_CODE_TOTAL_FAILURE, NO_MENU_MEALS_MSG, NO_ACTIVE_PLAN_MSG
from src.utils.utils import get_current_date_iso, is_valid_api_response

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


class SyncStatus(Enum):
    """Status of user synchronization process."""
    SUCCESS = "success"
    NO_MENU = "no_menu"
    FAILED = "failed"


class UserSyncResult(NamedTuple):
    """Result of processing a single user."""
    user_name: str
    status: SyncStatus
    message: str


async def process_user_meal_sync(user, sites) -> UserSyncResult:
    """Process meal synchronization for a single user.
    
    Args:
        user: User configuration
        sites: Sites configuration
        
    Returns:
        UserSyncResult with sync status and details
    """
    try:
        async with DietlyClient(sites.dietly, user.dietly_credentials) as client:
            try:
                api_result = await client.login_and_get_todays_menu()
                if not api_result:
                    logging.info(f"No menu data found for {user.name} on {get_current_date_iso()} - sync skipped (acceptable)")
                    return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                menu_data, company_name = api_result
                if not is_valid_api_response(menu_data):
                    logging.info(f"No valid menu data found for {user.name} on {get_current_date_iso()} - sync skipped (acceptable)")
                    return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                logging.info(f"Retrieved menu data for delivery {menu_data.get('deliveryId', 'unknown')}")
                try:
                    menu = MenuResponse.model_validate(menu_data)
                except ValidationError as ve:
                    logging.error(f"Menu validation failed for {user.name}:")
                    logging.error(f"Validation errors: {ve}")
                    logging.debug(f"Raw menu data structure: {_truncate_for_debug(menu_data)}")

                    _log_dietary_exclusion_debug_info(menu_data, user.name)
                    
                    return UserSyncResult(user.name, SyncStatus.FAILED, f"Menu validation failed: {str(ve)[:200]}")
                
                _warn_about_data_quality_issues(menu, user.name)
                
                logging.info(f"Successfully retrieved menu data for {user.name} from {company_name}")

            except DietlyNoActivePlanError as e:
                # No active plan is an acceptable state - treat as SUCCESS, not failure
                logging.info(f"No active meal plan for {user.name} on {get_current_date_iso()} - sync skipped (acceptable)")
                return UserSyncResult(user.name, SyncStatus.SUCCESS, NO_ACTIVE_PLAN_MSG)

            except DietlyClientAPIError as e:
                # Real failures from Dietly API - report as FAILED
                logging.error(f"Dietly API error for {user.name}: {e}")
                return UserSyncResult(user.name, SyncStatus.FAILED, f"Dietly API failed: {e}")

            # Menu found, now try to sync to Fitatu
            sync_success = await sync_menu_to_fitatu(menu, company_name, user, sites)
            if sync_success:
                return UserSyncResult(user.name, SyncStatus.SUCCESS, "Menu synced successfully")
            else:
                return UserSyncResult(user.name, SyncStatus.FAILED, "Fitatu sync failed")

    except ValidationError as ve:
        logging.error(f"Validation error processing {user.name}: {ve}")
        return UserSyncResult(user.name, SyncStatus.FAILED, f"Data validation failed: {str(ve)[:200]}")
    
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Unexpected error processing {user.name}: {e}")

        if any(keyword in error_msg.lower() for keyword in ["timeout", "connection", "network", "http"]):
            logging.info(f"HTTP/timeout error for {user.name} - likely no menu available")
            return UserSyncResult(user.name, SyncStatus.NO_MENU, f"HTTP timeout (likely no menu): {error_msg[:100]}")
        else:
            # Other unexpected errors are true failures
            return UserSyncResult(user.name, SyncStatus.FAILED, f"Unexpected error: {error_msg[:100]}")


async def sync_menu_to_fitatu(menu: MenuResponse, company_name: str, user, sites) -> bool:
    """Synchronize menu data to Fitatu service.
    
    Args:
        menu: Menu response from Dietly API
        company_name: Name of the meal company
        user: User configuration
        sites: Sites configuration
        
    Returns:
        True if synchronization was successful, False otherwise
    """
    try:
        fitatu = FitatuClient(
            sites_config=sites.fitatu,
            credentials=user.fitatu_credentials,
            brand=company_name
        )

        try:
            login_result = await fitatu.login()
            if not is_valid_api_response(login_result):
                logging.error(f"Failed to login to Fitatu for {user.name}")
                return False

            meal_data = await process_menu_meals(menu, fitatu)
            if not meal_data["meal_ids"]:
                logging.warning(f"No valid meals found to sync for {user.name}")
                return False

            success = await fitatu.publish_diet_plan(
                get_current_date_iso(),
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

    except Exception as e:
        logging.error(f"Unexpected error in Fitatu sync for {user.name}: {e}")
        return False


async def process_menu_meals(menu: MenuResponse, fitatu: FitatuClient) -> dict:
    """Process individual meals from menu and convert to Fitatu products.
    
    Args:
        menu: Menu response containing meals
        fitatu: Fitatu client instance
        
    Returns:
        Dictionary with meal_ids and meal_weights
    """
    meal_ids = {}
    meal_weights = {}
    today = get_current_date_iso()

    for meal in menu.deliveryMenuMeal:
        if meal.deliveryMealId is None:
            logging.info(f"Skipping '{meal.mealName}' - no delivery")
            continue

        product = convert_menu_meal_to_nutrition_product(meal, fitatu.brand)
        product_id = await fitatu.create_or_find_product(product, today)

        if product_id:
            meal_ids[meal.mealName] = product_id
            meal_weights[meal.mealName] = int(meal.nutrition.weight)
            logging.info(f"Processed meal: {meal.mealName}")
        else:
            logging.error(f"Failed to create/find product for {meal.mealName}")

    return {"meal_ids": meal_ids, "meal_weights": meal_weights}


def determine_sync_exit_code(results: list[UserSyncResult]) -> int:
    """Determine appropriate exit code based on synchronization results.
    
    Args:
        results: List of user sync results
        
    Returns:
        Exit code (0=success, 1=partial failure, 2=total failure)
    """
    total_users = len(results)
    successful_syncs = len([r for r in results if r.status == SyncStatus.SUCCESS])
    no_menu_users = len([r for r in results if r.status == SyncStatus.NO_MENU])

    # Consider "no menu" as acceptable, not a failure
    acceptable_results = successful_syncs + no_menu_users

    if acceptable_results == total_users:
        # All users either synced successfully or had no menu (both acceptable)
        return EXIT_CODE_SUCCESS
    elif successful_syncs > 0:
        # At least one user synced successfully, but some failed
        return EXIT_CODE_PARTIAL_FAILURE
    else:
        # All users failed to sync (ignoring "no menu" cases)
        return EXIT_CODE_TOTAL_FAILURE


async def main():
    """Main entry point for Dietly menu synchronization."""
    sites = SitesConfiguration.load_from_file("config/sites.yaml")
    users = UsersConfiguration.load_from_file("config/users.yaml")

    today = get_current_date_iso()
    logging.info(f"Starting Dietly sync for {today}")

    results = []
    for user in users.users:
        logging.info(f"Processing user: {user.name}")
        try:
            result = await process_user_meal_sync(user, sites)
            results.append(result)
        except Exception as e:
            # Ultimate fallback - should not happen with our improved error handling
            logging.error(f"Critical error processing {user.name}: {e}")
            results.append(UserSyncResult(user.name, SyncStatus.FAILED, f"Critical error: {str(e)[:100]}"))

    # Summary logging
    successful_syncs = len([r for r in results if r.status == SyncStatus.SUCCESS and "synced successfully" in r.message])
    no_active_plan_users = len([r for r in results if r.status == SyncStatus.SUCCESS and NO_ACTIVE_PLAN_MSG in r.message])
    no_menu_users = len([r for r in results if r.status == SyncStatus.NO_MENU])
    failed_syncs = len([r for r in results if r.status == SyncStatus.FAILED])
    total_users = len(results)

    logging.info("=== SYNC SUMMARY ===")
    logging.info(f"Total users: {total_users}")
    logging.info(f"Successful meal syncs: {successful_syncs}")
    logging.info(f"No active meal plan: {no_active_plan_users}")
    logging.info(f"No menu available: {no_menu_users}")
    logging.info(f"Failed syncs: {failed_syncs}")

    # Detailed results
    for result in results:
        if result.status == SyncStatus.SUCCESS and NO_ACTIVE_PLAN_MSG in result.message:
            status_icon = "📅"  # Calendar icon for no active plan
        else:
            status_icon = {"success": "✅", "no_menu": "ℹ️", "failed": "❌"}[result.status.value]
        logging.info(f"{status_icon} {result.user_name}: {result.message}")

    # Determine exit code and final status
    exit_code = determine_sync_exit_code(results)

    if exit_code == EXIT_CODE_SUCCESS:
        logging.info("🎉 All users processed successfully")
    elif exit_code == EXIT_CODE_PARTIAL_FAILURE:
        logging.warning("⚠️ Partial success - some users failed to sync")
    else:
        logging.error("💥 All users failed to sync")

    return sys.exit(exit_code)


def _truncate_for_debug(data: dict, max_items: int = 3) -> dict:
    """Truncate menu data for debug logging to avoid overwhelming logs."""
    if not isinstance(data, dict):
        return data
    
    truncated = {}
    for key, value in list(data.items())[:max_items]:
        if isinstance(value, list) and len(value) > 2:
            truncated[key] = f"[{len(value)} items] " + str(value[:2]) + "..."
        elif isinstance(value, dict):
            truncated[key] = _truncate_for_debug(value, max_items=2)
        else:
            truncated[key] = value
    
    if len(data) > max_items:
        truncated["..."] = f"and {len(data) - max_items} more keys"
    
    return truncated


def _log_dietary_exclusion_debug_info(menu_data: dict, user_name: str):
    """Log specific debug information about dietaryExclusionId None values."""
    try:
        meals = menu_data.get('deliveryMenuMeal', [])
        for i, meal in enumerate(meals):
            allergens = meal.get('allergensWithExcluded', [])
            for j, allergen in enumerate(allergens):
                if allergen.get('dietaryExclusionId') is None:
                    logging.error(f"DEBUG - {user_name}: meal[{i}] '{meal.get('mealName', 'unknown')}' allergensWithExcluded[{j}] has None dietaryExclusionId")
                    logging.error(f"DEBUG - Full allergen data: {allergen}")
            
            # Also check ingredient exclusions in raw data
            for ingredient in meal.get('ingredients', []):
                for k, exclusion in enumerate(ingredient.get('exclusion', [])):
                    if exclusion.get('dietaryExclusionId') is None:
                        logging.error(f"DEBUG - {user_name}: meal[{i}] '{meal.get('mealName', 'unknown')}' ingredient '{ingredient.get('name', 'unknown')}' exclusion[{k}] has None dietaryExclusionId")
                        logging.error(f"DEBUG - Full exclusion data: {exclusion}")
    except Exception as e:
        logging.error(f"Error in debug logging for {user_name}: {e}")


def _warn_about_data_quality_issues(menu: MenuResponse, user_name: str):
    """Log warnings about data quality issues (None dietaryExclusionId values)."""
    try:
        meals = menu.deliveryMenuMeal
        for i, meal in enumerate(meals):
            allergens = meal.allergensWithExcluded
            for j, allergen in enumerate(allergens):
                if allergen.dietaryExclusionId is None:
                    logging.warning(f"WARNING - {user_name}: meal[{i}] '{meal.mealName}' allergensWithExcluded[{j}] has None dietaryExclusionId")
                    logging.warning(f"WARNING - Allergen details: companyAllergenName={allergen.companyAllergenName}, dietlyAllergenName={allergen.dietlyAllergenName}, excluded={allergen.excluded}")
            
            # Also check ingredient exclusions
            for ingredient in meal.ingredients:
                for k, exclusion in enumerate(ingredient.exclusion):
                    if exclusion.dietaryExclusionId is None:
                        logging.warning(f"WARNING - {user_name}: meal[{i}] '{meal.mealName}' ingredient '{ingredient.name}' exclusion[{k}] has None dietaryExclusionId")
                        logging.warning(f"WARNING - Exclusion details: name={exclusion.name}, chosen={exclusion.chosen}")
    except Exception as e:
        logging.error(f"Error in data quality logging for {user_name}: {e}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
