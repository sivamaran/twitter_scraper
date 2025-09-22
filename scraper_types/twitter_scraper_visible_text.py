# scraper_types/twitter_scraper_visible_text.py
import re, time
from typing import List, Dict
from common.anti_detection import goto_resilient

async def scrape_twitter_visible_text_seq(urls: List[str], page) -> List[Dict]:
    results: List[Dict] = []
    for url in urls:
        ok = await goto_resilient(page, url)
        if not ok:
            results.append({"twitter_link": url, "error": "Navigation failed"})
            continue

        # Grab tweets text
        tweet_texts = []
        try:
            els = await page.query_selector_all("article div[data-testid='tweetText']")
            for el in els[:3]:  # limit to few tweets
                txt = (await el.text_content() or "").strip()
                if txt: tweet_texts.append(txt)
        except Exception:
            pass

        results.append({
            "platform": "twitter",
            "twitter_link": url,
            "main_tweet_text": tweet_texts[0] if tweet_texts else None,
            "text": "\n".join(tweet_texts),
            "scraped_at": int(time.time())
        })
    return results
