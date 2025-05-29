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
        except DietlyScraperAPIError as e:
            logging.info(f"Error while scraping Dietly API: {e}")

        fitatu = FitatuClient(
            sites_config=sites.fitatu,
            credentials=user.fitatu_credentials,
            brand="Dietly",
            headless=True
        )
        await fitatu.login()
        meal_ids = {}
        meal_weights = {}
        for meal in menu.deliveryMenuMeal:
            product = menu_meal_to_product(meal, fitatu.brand)
            add_resp = await fitatu.add_product(product)
            product_id = add_resp.get("id") if add_resp else None
            if product_id:
                meal_ids[meal.mealName] = product_id
                meal_weights[meal.mealName] = int(meal.nutrition.weight)
        existing_plan = await fitatu.get_existing_diet_plan(today)
        diet_plan = {today: {"dietPlan": {}}}
        meal_mapping = {
            "Śniadanie": "breakfast",
            "II śniadanie": "second_breakfast",
            "Obiad": "dinner",
            "Podwieczorek": "snack",
            "Kolacja": "supper"
        }
        for meal_name, product_id in meal_ids.items():
            FitatuClient.add_meal_to_diet_plan(
                diet_plan[today]["dietPlan"],
                meal_name,
                product_id,
                meal_weights.get(meal_name, 100),
                existing_plan,
                meal_mapping
            )
        await fitatu.update_diet_plan(today, diet_plan)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
