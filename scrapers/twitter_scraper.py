# twitter_scraper.py

import asyncio
import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright

def _setup_path():
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

_setup_path()

# ---- browser manager ----
from common.browser_manager import get_browser, get_stealth_page

# ---- scrapers ----
from scraper_types.twitter_scraper_meta import scrape_twitter_profiles_async, _contacts
from scraper_types.twitter_scraper_visible_text import scrape_twitter_visible_text_seq

# ---- db + schema utils ----
from common.db_utils import get_db, process_and_store, SCHEMA


# ---- alias mapping for schema ----
TWITTER_ALIAS: Dict[str, list] = {
    "url": ["twitter_link", "url"],

    "profile.username": ["handle", "username"],
    "profile.full_name": ["name", "full_name"],
    "profile.bio": ["bio"],

    "contact.emails": ["emails"],
    "contact.phone_numbers": ["phones", "phone_numbers"],
    "contact.websites": ["external_links"],
}


def _merge_results(meta_results: List[Dict], visual_results: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for item in meta_results + visual_results:
        join_key = item.get("twitter_link") or item.get("url")
        if not join_key:
            continue
        if join_key not in merged:
            merged[join_key] = {}
        merged[join_key].update(item)
    return list(merged.values())


# ---- main orchestrator ----
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
    Orchestrates the Twitter scraping:
      1. Launches one stealth browser with two pages
      2. Runs meta & visible scrapers concurrently
      3. Merges results
      4. Enriches with contact extraction
      5. Stores or returns data
    """
    print(f"--- Starting combined Twitter scrape for {len(urls)} URLs ---")

    async with async_playwright() as p:
        browser = await get_browser(p, headless=headless)
        try:
            meta_page = await get_stealth_page(browser)
            visual_page = await get_stealth_page(browser)

            meta_task = asyncio.create_task(
                scrape_twitter_profiles_async(urls, page=meta_page)
            )
            visual_task = asyncio.create_task(
                scrape_twitter_visible_text_seq(urls, page=visual_page)
            )

            meta_results, visual_results = await asyncio.gather(meta_task, visual_task)
        finally:
            if browser:
                await browser.close()

    # --- merge results ---
    print("\n--- Merging Twitter results ---")
    combined_results = _merge_results(meta_results, visual_results)

    # --- enrichment: extract emails & phones from bios/tweets ---
    print("\n--- Enriching with contact extraction ---")
    for item in combined_results:
        bio_text = item.get("bio", "")
        tweet_text = item.get("main_tweet_text", "")
        text_blob = " ".join([bio_text or "", tweet_text or ""])

        contacts = _contacts(text_blob)
        item["emails"] = list(set(item.get("emails", []) + contacts["emails"]))
        item["phones"] = list(set(item.get("phones", []) + contacts["phones"]))

    # --- optional DB / file write ---
    if schema is not None and db is not None:
        print("\n--- Filtering to schema + inserting into MongoDB ---")
        filtered = process_and_store(
            db=db,
            data=combined_results,
            platform="twitter",
            schema_obj=schema,
            alias=alias or {},
            write_path=write_path,
        )
        return filtered

    return combined_results


# ---- CLI runner ----
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the main combined Twitter scraper.")
    parser.add_argument("urls", nargs="+", help="Twitter profile URLs to scrape")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--output", type=str, help="Optional output JSON file path")
    args = parser.parse_args()

    db = None
    schema = SCHEMA
    alias = TWITTER_ALIAS

    results = asyncio.run(
        main(
            args.urls,
            headless=args.headless,
            db=db,
            schema=schema,
            alias=alias,
            write_path=args.output,
        )
    )

    if not args.output:
        print(json.dumps(results, indent=2))
