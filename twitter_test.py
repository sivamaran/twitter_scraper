from common.db_utils import save_to_mongo, save_to_json
import asyncio
from scrapers import twitter_scraper


URLS = ["https://x.com/imVkohli", "https://x.com/realdonaldtrump"]

async def run_test():
    print("--- Starting Twitter Test ---")
    results = await twitter_scraper.main(URLS, headless=True)

    # Save to Mongo
    save_to_mongo(results, db_name="leadgen", collection_name="twitter_leads")

    # Save to JSON
    save_to_json(results, file_path="twitter_output.json")

if __name__ == "__main__":
    asyncio.run(run_test())
