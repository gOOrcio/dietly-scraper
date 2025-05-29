import logging
from typing import Optional
from datetime import datetime

from add_product_model import menu_meal_to_product
from fitatu_client import FitatuClient
from menu_response_model import MenuResponse
from dietly_scraper import DietlyScraper, DietlyScraperAPIError
from config_model import SitesConfig, UsersConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(asctime)s - %(message)s")

async def main():
    """Main entry point for Dietly menu scraping."""
    sites = SitesConfig.load("sites.yaml")
    users = UsersConfig.load("users.yaml")
    menu: MenuResponse = Optional[MenuResponse]
    today = datetime.now().strftime("%Y-%m-%d")

    for user in users.users:
        scraper = DietlyScraper(sites.dietly, user.dietly_credentials)
        try:
            json = await scraper.login_and_capture_api()
            if json:
                menu = MenuResponse.model_validate(json)
                logging.info(menu.model_dump_json(indent=2))
            else:
                logging.info("No data captured.")
                continue
        except DietlyScraperAPIError as e:
            logging.info(f"Error while scraping Dietly API: {e}")
            continue

        fitatu = FitatuClient(
            sites_config=sites.fitatu,
            credentials=user.fitatu_credentials,
            brand="Dietly",
            headless=True
        )
        
        try:
            await fitatu.login()
            meal_ids = {}
            meal_weights = {}
            
            # Process each meal - create or find product
            for meal in menu.deliveryMenuMeal:
                if meal.deliveryMealId is None:
                    logging.info(f"Skipping '{meal.mealName}' - no delivery")
                    continue
                    
                product = menu_meal_to_product(meal, fitatu.brand)
                product_id = await fitatu.create_or_find_product(product, today)
                
                if product_id:
                    meal_ids[meal.mealName] = product_id
                    meal_weights[meal.mealName] = int(meal.nutrition.weight)
                else:
                    logging.error(f"Failed to create/find product for {meal.mealName}")
            
            meal_mapping = {
                "Śniadanie": "breakfast",
                "II śniadanie": "second_breakfast", 
                "Obiad": "dinner",
                "Podwieczorek": "snack",
                "Kolacja": "supper"
            }
            
            success = await fitatu.publish_diet_plan(today, meal_ids, meal_weights, meal_mapping)
            if not success:
                logging.error(f"Failed to publish diet plan for {today}")
                
        except Exception as e:
            logging.error(f"Error during Fitatu processing: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
