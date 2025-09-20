# twitter_scraper.py (FINAL CORRECTED VERSION)
import asyncio
import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional

# --- ADDED: Import Playwright and your new browser manager ---
from playwright.async_api import async_playwright

def _setup_path():
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

_setup_path()

# ---- ADDED: Import your new browser manager ----
from common.browser_manager import get_browser, get_stealth_page

# ---- platform scrapers (these are your newly refactored worker files) ----
from scraper_types.twitter_scraper_meta import scrape_twitter_profiles_async
from scraper_types.twitter_scraper_visible_text import scrape_twitter_visible_text_seq

# ---- db + schema utils ----
from common.db_utils import get_db, process_and_store, SCHEMA


# ---- alias mapping and _merge_results function are unchanged ----
TWITTER_ALIAS: Dict[str, list] = {
    "url": ["twitter_link", "url"],

    # Paths now point into the 'profile' object using dot notation
    "profile.username": ["handle", "username"],
    "profile.full_name": ["name", "full_name"],
    "profile.bio": ["bio"],
    
    # Paths now point into the 'contact' object
    "contact.emails": ["emails"],
    "contact.phone_numbers": ["phones", "phone_numbers"],
    "contact.websites": ["external_links"],
}
def _merge_results(meta_results: List[Dict], visual_results: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for item in meta_results + visual_results:
        join_key = item.get("twitter_link") or item.get("url")
        if not join_key: continue
        if join_key not in merged: merged[join_key] = {}
        merged[join_key].update(item)
    return list(merged.values())


# ---- main function is MODIFIED to manage the browser ----
async def main(
    urls: List[str],
    *,
    headless: bool = True,
    db=None,
    schema: Optional[Dict] = None,
    alias: Optional[Dict[str, list]] = None,
    write_path: Optional[str] = None,
) -> List[Dict]:
    """
    1) Creates ONE stealth browser and pages via browser_manager
    2) Runs both Twitter scrapers concurrently with these pages
    3) Merges and processes results
    """
    print(f"--- Starting combined Twitter scrape for {len(urls)} URLs ---")

    async with async_playwright() as p:
        browser = await get_browser(p, headless=headless)
        try:
            # Create two separate pages from the same stealth browser
            meta_page = await get_stealth_page(browser)
            visual_page = await get_stealth_page(browser)

            # CHANGED: Pass the page object to each scraper task. The 'headless' arg is removed.
            meta_task = asyncio.create_task(
                scrape_twitter_profiles_async(urls, page=meta_page)
            )
            visual_task = asyncio.create_task(
                scrape_twitter_visible_text_seq(urls, page=visual_page)
            )

            meta_results, visual_results = await asyncio.gather(meta_task, visual_task)
        finally:
            # Ensure the single browser instance is always closed
            if browser:
                await browser.close()

    # The rest of the function for merging and storing data is unchanged
    print("\n--- Merging Twitter results ---")
    combined_results = _merge_results(meta_results, visual_results)

    if schema is not None and db is not None:
        print("\n--- Filtering to flat schema + inserting into MongoDB ---")
        filtered = process_and_store(
            db=db, data=combined_results, platform="twitter",
            schema_obj=schema, alias=alias or {}, write_path=write_path,
        )
        return filtered

    return combined_results

# The `if __name__ == "__main__":` block is unchanged and works as intended
if __name__ == "__main__":
    # ... (this part of your code does not need to change)
    parser = argparse.ArgumentParser(description="Run the main combined Twitter scraper.")
    # ... (all your argparse and asyncio.run logic remains the same)