from menu_response_model import MenuResponse
from dietly_scraper import login_and_capture_api, DietlyScraperAPIError
from config_model import Config

async def main():
    """Main entry point for Dietly menu scraping."""
    config = Config.load()
    try:
        today_menu = await login_and_capture_api(config.sites.dietly, config.users[0])
        if today_menu:
            menu = MenuResponse.model_validate(today_menu)
            print(menu.model_dump_json(indent=2))
        else:
            print("No data captured.")
    except DietlyScraperAPIError as e:
        print(f"Error while scraping Dietly API: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

