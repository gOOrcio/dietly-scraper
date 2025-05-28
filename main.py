import logging
from typing import Optional

from add_product_model import menu_meal_to_product
from fitatu_client import FitatuClient
from menu_response_model import MenuResponse
from dietly_scraper import DietlyScraper, DietlyScraperAPIError
from config_model import SitesConfig, UsersConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def main():
    """Main entry point for Dietly menu scraping."""
    sites = SitesConfig.load("sites.yaml")
    users = UsersConfig.load("users.yaml")
    menu: MenuResponse = Optional[MenuResponse]

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
        try:
            await fitatu.login()
            for meal in menu.deliveryMenuMeal:
                product = menu_meal_to_product(meal)
                await fitatu.add_product(product)
        except Exception as e:
            logging.info(f"Error during Fitatu login: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
