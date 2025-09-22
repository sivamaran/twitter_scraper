# scrapers/twitter_scraper.py
import asyncio
from pathlib import Path
import sys
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from common.browser_manager import get_browser, get_stealth_page
from scraper_types.twitter_scraper_meta import scrape_twitter_profiles_async, _contacts
from scraper_types.twitter_scraper_visible_text import scrape_twitter_visible_text_seq
from common.db_utils import SCHEMA

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
        if not join_key: continue
        if join_key not in merged: merged[join_key] = {}
        merged[join_key].update(item)
    return list(merged.values())

def _map_to_schema(raw: Dict, schema: Dict, alias: Dict[str, list]) -> Dict:
    from copy import deepcopy
    mapped = deepcopy(schema)
    for schema_key, possible_keys in alias.items():
        target = mapped
        parts = schema_key.split(".")
        for p in parts[:-1]:
            target = target[p]
        for key in possible_keys:
            if key in raw and raw[key]:
                target[parts[-1]] = raw[key]
                break
    return mapped

async def main(urls: List[str], *, headless: bool = True,
               alias: Optional[Dict[str, list]] = None,
               schema: Optional[Dict] = None) -> List[Dict]:
    print(f"--- Starting combined Twitter scrape for {len(urls)} URLs ---")
    async with async_playwright() as p:
        browser = await get_browser(p, headless=headless)
        try:
            meta_page = await get_stealth_page(browser)
            visual_page = await get_stealth_page(browser)
            meta_task = asyncio.create_task(scrape_twitter_profiles_async(urls, page=meta_page))
            visual_task = asyncio.create_task(scrape_twitter_visible_text_seq(urls, page=visual_page))
            meta_results, visual_results = await asyncio.gather(meta_task, visual_task)
        finally:
            if browser: await browser.close()

    print("\n--- Merging Twitter results ---")
    combined_results = _merge_results(meta_results, visual_results)

    print("\n--- Enriching with contact extraction ---")
    for item in combined_results:
        bio_text = item.get("bio", "")
        tweet_text = item.get("main_tweet_text", "")
        text_blob = " ".join([bio_text or "", tweet_text or ""])
        contacts = _contacts(text_blob)
        item["emails"] = list(set(item.get("emails", []) + contacts["emails"]))
        item["phones"] = list(set(item.get("phones", []) + contacts["phones"]))

    print("\n--- Mapping results into schema ---")
    schema_obj = schema or SCHEMA
    alias_map = alias or TWITTER_ALIAS
    schema_results = [_map_to_schema(item, schema_obj, alias_map) for item in combined_results]

    return schema_results
