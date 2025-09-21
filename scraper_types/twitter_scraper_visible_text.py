# scraper_types/twitter_scraper_visible_text.py

import time
from typing import List, Dict
from playwright.async_api import TimeoutError as PWTimeout, Page

# 🔹 Import meta utilities safely without renaming functions
from scraper_types import twitter_scraper_meta as meta_utils

# --- Selectors for visible text ---
BIO_SEL = ["div[data-testid='UserDescription'] span"]
TWEET_TEXT_SEL = ["div[data-testid='tweetText'] span"]
HASHTAG_SEL = ["a[href*='/hashtag/'] span"]

# -------------------------------------------------------------------
# Extract visible text from profile (bio, tweets, hashtags)
# -------------------------------------------------------------------
async def _extract_visible_text(page: Page, url: str) -> Dict:
    bio = await meta_utils._first_text(page, BIO_SEL)
    og_desc = await meta_utils._meta(page, prop="og:description")

    # Combine bio + meta description for contact extraction
    text_blob = " ".join([bio or "", og_desc or ""])

    # Grab hashtags if available
    hashtags = []
    try:
        els = await page.query_selector_all("a[href*='/hashtag/'] span")
        hashtags = [await e.text_content() for e in els if await e.text_content()]
    except Exception:
        pass

    return {
        "platform": "twitter",
        "twitter_link": url,
        "bio": bio,
        "main_tweet_text": await meta_utils._first_text(page, TWEET_TEXT_SEL),
        "hashtags": hashtags,
        "scraped_at": int(time.time()),
    }


# -------------------------------------------------------------------
# Main sequential scraper for visible text
# -------------------------------------------------------------------
async def scrape_twitter_visible_text_seq(urls: List[str], page: Page) -> List[Dict]:
    results: List[Dict] = []
    total = len(urls)

    for i, link in enumerate(urls, start=1):
        print(f"[VISIBLE] {i}/{total} → Starting scrape: {link}")
        try:
            await meta_utils._goto(page, link)
            results.append(await _extract_visible_text(page, link))
            print(f"[VISIBLE] {i}/{total} → Completed: {link}")
        except PWTimeout:
            print(f"[VISIBLE] {i}/{total} → Timeout: {link}")
            results.append({
                "platform": "twitter",
                "twitter_link": link,
                "error": "Navigation timeout (visible text)",
                "scraped_at": int(time.time()),
            })
        except Exception as e:
            print(f"[VISIBLE] {i}/{total} → Failed: {link} ({e})")
            results.append({
                "platform": "twitter",
                "twitter_link": link,
                "error": str(e),
                "scraped_at": int(time.time()),
            })

    return results
