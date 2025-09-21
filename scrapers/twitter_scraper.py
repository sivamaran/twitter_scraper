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

# ---- Imports ----
from common.browser_manager import get_browser, get_stealth_page
from scraper_types.twitter_scraper_meta import scrape_twitter_profiles_async
from scraper_types.twitter_scraper_visible_text import scrape_twitter_visible_text_seq
from common.db_utils import get_db, process_and_store, SCHEMA

# ---- alias mapping ----
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

# ---- main function ----
async def main(
    urls: List[str],
    *,
    headless: bool = True,
    db=None,
    schema: Optional[Dict] = None,
    alias: Optional[Dict[str, list]] = None,
    write_path: Optional[str] = None,
) -> List[Dict]:
    print(f"--- Starting Twitter scrape for {len(urls)} URLs ---")

    async with async_playwright() as p:
        browser = await get_browser(p, headless=headless)
        try:
            meta_page = await get_stealth_page(browser)
            visual_page = await get_stealth_page(browser)

            # Run both scrapers
            meta_task = asyncio.create_task(
                scrape_twitter_profiles_async(urls, page=meta_page)
            )
            visual_task = asyncio.create_task(
                scrape_twitter_visible_text_seq(urls, page=visual_page)
            )

            meta_results, visual_results = await asyncio.gather(meta_task, visual_task)

            # ✅ Per-URL status prints
            print("\n--- Individual URL Status ---")
            for idx, result in enumerate(meta_results, start=1):
                url = result.get("twitter_link") or result.get("url")
                status = "OK" if "error" not in result else f"ERROR: {result['error']}"
                print(f"[INFO] {idx}/{len(meta_results)} → {url} → {status}")

        finally:
            if browser:
                await browser.close()

    print("\n--- Merging Twitter results ---")
    combined_results = _merge_results(meta_results, visual_results)

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the main Twitter scraper.")
    parser.add_argument("--urls", type=str, default="twitter_urls.txt", help="Path to file containing Twitter URLs")
    parser.add_argument("--output", type=str, default="twitter_output.json", help="Path to save output JSON")
    parser.add_argument("--headful", action="store_true", help="Run browser in headful mode")
    args = parser.parse_args()

    urls = []
    with open(args.urls, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    results = asyncio.run(
        main(urls, headless=not args.headful, db=None, schema=None, alias=TWITTER_ALIAS, write_path=args.output)
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n--- Test Complete ---\nResults have been saved to '{args.output}'")
