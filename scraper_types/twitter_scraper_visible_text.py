import time
from typing import List, Dict
from playwright.async_api import Page

# --- Helpers ---
async def _goto(page: Page, url: str):
    await page.goto(url, wait_until="domcontentloaded", timeout=35000)
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

async def _extract_visible_text(page: Page, url: str) -> Dict:
    # 🔹 Replace with your existing extraction logic
    bio = ""
    main_tweet = ""
    hashtags = []

    return {
        "platform": "twitter",
        "twitter_link": url,
        "bio": bio,
        "main_tweet_text": main_tweet,
        "hashtags": hashtags,
        "scraped_at": int(time.time())
    }

# --- Main VISIBLE TEXT scraper ---
async def scrape_twitter_visible_text_seq(urls: List[str], page: Page) -> List[Dict]:
    results = []
    total = len(urls)
    print(f"\n[TEXT] Starting VISIBLE TEXT scrape for {total} URLs\n")

    for idx, link in enumerate(urls, start=1):
        print(f"[TEXT] {idx}/{total} → Starting scrape: {link}")
        try:
            await _goto(page, link)
            text_data = await _extract_visible_text(page, link)
            results.append(text_data)
            print(f"[TEXT] {idx}/{total} → Completed: {link}")
        except Exception as e:
            print(f"[TEXT] {idx}/{total} → ERROR on {link}: {e}")
            results.append({"platform": "twitter", "twitter_link": link, "error": str(e)})

    return results
