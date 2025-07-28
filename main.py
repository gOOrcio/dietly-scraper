import logging
import sys
import time
from datetime import datetime
from enum import Enum
from typing import NamedTuple, List, Dict, Tuple

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

# Configure logging with JSON format for better parsing
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # We'll format messages as JSON
    handlers=[logging.StreamHandler(sys.stdout)]
)

class ErrorCategory(Enum):
    TRANSIENT = "transient"
    API_ERROR = "api_error"
    VALIDATION = "validation"
    AUTH = "auth"
    NETWORK = "network"
    UNKNOWN = "unknown"

class SyncStatus(Enum):
    SUCCESS = "success"
    NO_MENU = "no_menu"
    FAILED = "failed"

class UserSyncResult(NamedTuple):
    user_name: str
    status: SyncStatus
    message: str
    error_category: ErrorCategory = ErrorCategory.UNKNOWN
    duration_ms: int = 0
    retry_count: int = 0

def log_json(level: str, message: str, **kwargs):
    """Log a message in JSON format for better parsing."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    logging.info(log_entry)

def categorize_error(error_msg: str) -> ErrorCategory:
    """Categorize error messages for better analysis."""
    error_msg = error_msg.lower()
    if any(x in error_msg for x in ["503", "502", "500", "504", "timeout", "connection"]):
        return ErrorCategory.TRANSIENT
    elif "api" in error_msg or "http" in error_msg:
        return ErrorCategory.API_ERROR
    elif "validation" in error_msg:
        return ErrorCategory.VALIDATION
    elif "auth" in error_msg or "login" in error_msg:
        return ErrorCategory.AUTH
    elif "network" in error_msg:
        return ErrorCategory.NETWORK
    return ErrorCategory.UNKNOWN

def is_transient_error(error_msg: str) -> bool:
    """Check if an error message indicates a transient failure."""
    transient_indicators = ["503", "502", "500", "504", "connection", "timeout", "network"]
    return any(indicator in error_msg.lower() for indicator in transient_indicators)

async def process_user_meal_sync(user, sites) -> UserSyncResult:
    """Process meal synchronization for a single user with retry logic."""
    start_time = time.time()
    retry_count = 0
    
    async def sync_attempt():
        try:
            async with DietlyClient(sites.dietly, user.dietly_credentials) as client:
                try:
                    api_result = await client.login_and_get_todays_menu()
                    if not api_result:
                        return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                    menu_results, company_name = api_result
                    if not menu_results:
                        return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                    # Process all menus from all orders
                    all_menus = []
                    for menu_data, order_company_name in menu_results:
                        if not is_valid_api_response(menu_data):
                            logging.warning(f"Invalid API response for order from {order_company_name}")
                            continue
                        
                        menu = MenuResponse.model_validate(menu_data)
                        all_menus.append((menu, order_company_name))
                        log_json("info", f"Retrieved menu data", user=user.name, company=order_company_name)

                    if not all_menus:
                        return UserSyncResult(user.name, SyncStatus.NO_MENU, NO_MENU_MEALS_MSG)

                except DietlyNoActivePlanError:
                    return UserSyncResult(user.name, SyncStatus.SUCCESS, NO_ACTIVE_PLAN_MSG)
                except DietlyClientAPIError as e:
                    error_category = categorize_error(str(e))
                    return UserSyncResult(
                        user.name, SyncStatus.FAILED, 
                        f"Dietly API failed: {e}",
                        error_category=error_category
                    )

                if await sync_menu_to_fitatu(all_menus, company_name, user, sites):
                    return UserSyncResult(user.name, SyncStatus.SUCCESS, "Menu synced successfully")
                else:
                    return UserSyncResult(
                        user.name, SyncStatus.FAILED, 
                        "Fitatu sync failed",
                        error_category=ErrorCategory.API_ERROR
                    )

        except ValidationError as ve:
            return UserSyncResult(
                user.name, SyncStatus.FAILED,
                f"Data validation failed: {str(ve)[:200]}",
                error_category=ErrorCategory.VALIDATION
            )
        except Exception as e:
            error_msg = str(e)
            error_category = categorize_error(error_msg)
            if any(keyword in error_msg.lower() for keyword in ["timeout", "connection", "network", "http"]):
                return UserSyncResult(
                    user.name, SyncStatus.NO_MENU,
                    f"HTTP timeout (likely no menu): {error_msg[:100]}",
                    error_category=error_category
                )
            else:
                return UserSyncResult(
                    user.name, SyncStatus.FAILED,
                    f"Unexpected error: {error_msg[:100]}",
                    error_category=error_category
                )

    # Retry logic for transient failures
    for attempt in range(RETRY_MAX_ATTEMPTS):
        result = await sync_attempt()
        retry_count = attempt
        
        if (result.status != SyncStatus.FAILED or 
            result.error_category != ErrorCategory.TRANSIENT or 
            attempt == RETRY_MAX_ATTEMPTS - 1):
            duration_ms = int((time.time() - start_time) * 1000)
            return UserSyncResult(
                *result[:-2],  # Keep all fields except duration and retry
                duration_ms=duration_ms,
                retry_count=retry_count
            )
        
        log_json("warning", "Transient error, retrying", 
                user=user.name, 
                attempt=attempt + 1,
                max_attempts=RETRY_MAX_ATTEMPTS,
                error=result.message)

    return result


async def sync_menu_to_fitatu(all_menus: List[Tuple[MenuResponse, str]], company_name: str, user, sites) -> bool:
    """Synchronize menu data to Fitatu service from multiple orders."""
    try:
        fitatu = FitatuClient(sites.fitatu, user.fitatu_credentials, company_name)
        
        if not await fitatu.login():
            logging.error(f"Failed to login to Fitatu for {user.name}")
            return False

        # Process all menus from all orders
        all_meal_data = {"meal_ids": {}, "meal_weights": {}}
        meal_name_mapping = {}  # Maps unique meal names to original meal names
        
        for i, (menu, order_company_name) in enumerate(all_menus):
            meal_data = await process_menu_meals(menu, fitatu)
            if meal_data["meal_ids"]:
                # Merge meal data from this order with existing data
                # If there are duplicate meal names, create unique names for the second order
                for meal_name, product_id in meal_data["meal_ids"].items():
                    unique_meal_name = meal_name
                    counter = 1
                    
                    # If this meal name already exists, create a unique name
                    while unique_meal_name in all_meal_data["meal_ids"]:
                        # Extract order number from company name if it exists
                        if " (Order " in order_company_name:
                            # Already has order info, just add counter
                            unique_meal_name = f"{meal_name} ({order_company_name.split(' (Order ')[0]} #{counter})"
                        else:
                            # Add order info
                            unique_meal_name = f"{meal_name} ({order_company_name})"
                        counter += 1
                        if counter > 10:  # Prevent infinite loop
                            break
                    
                    all_meal_data["meal_ids"][unique_meal_name] = product_id
                    all_meal_data["meal_weights"][unique_meal_name] = meal_data["meal_weights"].get(meal_name, 100)
                    meal_name_mapping[unique_meal_name] = meal_name  # Map unique name back to original
                
                logging.info(f"Processed {len(meal_data['meal_ids'])} meals from order {order_company_name}")
            else:
                logging.warning(f"No valid meals found in order from {order_company_name}")

        if not all_meal_data["meal_ids"]:
            logging.warning(f"No valid meals found to sync for {user.name} from any order")
            return False

        success = await fitatu.publish_diet_plan(
            get_current_date_iso(), all_meal_data["meal_ids"], 
            all_meal_data["meal_weights"], MEAL_MAPPING, meal_name_mapping
        )

        if success:
            logging.info(f"Successfully synced {len(all_meal_data['meal_ids'])} total meals to Fitatu for {user.name}")
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
    start_time = time.time()
    sites = SitesConfiguration.load_from_file("config/sites.yaml")
    users = UsersConfiguration.load_from_file("config/users.yaml")

    log_json("info", "Starting sync", date=get_current_date_iso(), total_users=len(users.users))

    results = []
    for user in users.users:
        log_json("info", "Processing user", user=user.name)
        try:
            result = await process_user_meal_sync(user, sites)
            results.append(result)
        except Exception as e:
            log_json("error", "Critical error", user=user.name, error=str(e)[:100])
            results.append(UserSyncResult(
                user.name, SyncStatus.FAILED,
                f"Critical error: {str(e)[:100]}",
                error_category=ErrorCategory.UNKNOWN
            ))

    # Calculate statistics
    total_duration = int((time.time() - start_time) * 1000)
    stats = {
        "total_users": len(results),
        "successful_syncs": sum(1 for r in results if r.status == SyncStatus.SUCCESS and "synced successfully" in r.message),
        "no_active_plan": sum(1 for r in results if r.status == SyncStatus.SUCCESS and NO_ACTIVE_PLAN_MSG in r.message),
        "no_menu": sum(1 for r in results if r.status == SyncStatus.NO_MENU),
        "failed": sum(1 for r in results if r.status == SyncStatus.FAILED),
        "total_duration_ms": total_duration,
        "avg_duration_ms": total_duration // len(results) if results else 0,
        "error_categories": {
            category.value: sum(1 for r in results if r.error_category == category)
            for category in ErrorCategory
        }
    }

    # Log summary
    log_json("info", "Sync summary", **stats)

    # Log detailed results
    for result in results:
        log_json(
            "info" if result.status != SyncStatus.FAILED else "error",
            result.message,
            user=result.user_name,
            status=result.status.value,
            error_category=result.error_category.value,
            duration_ms=result.duration_ms,
            retry_count=result.retry_count
        )

    # Exit with appropriate code
    exit_code = determine_sync_exit_code(results)
    status_msgs = {
        EXIT_CODE_SUCCESS: "🎉 All users processed successfully",
        EXIT_CODE_PARTIAL_FAILURE: "⚠️ Partial success - some users failed to sync",
        EXIT_CODE_TOTAL_FAILURE: "💥 All users failed to sync"
    }
    
    log_json(
        "info" if exit_code == EXIT_CODE_SUCCESS else "warning" if exit_code == EXIT_CODE_PARTIAL_FAILURE else "error",
        status_msgs[exit_code],
        exit_code=exit_code,
        **stats
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
