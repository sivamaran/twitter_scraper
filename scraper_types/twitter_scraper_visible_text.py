# twitter_scraper_visible_text.py (FINAL VERSION WITH YOUR LOGIC)

import re, json, time, argparse, asyncio
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from playwright.async_api import Page, TimeoutError

# --------------------------------------------------------------------
# --- ✅ YOUR ORIGINAL HELPER FUNCTIONS (ALL KEPT) ---
# --------------------------------------------------------------------
def _norm(s: Optional[str]) -> str:
    """Normalizes whitespace in a string."""
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()

def _dedupe_keep_order(items: List[str]) -> List[str]:
    """Removes duplicates from a list while preserving original order."""
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def _split_twitter_links(links: List[str]) -> Tuple[List[str], List[str]]:
    """Splits links into external and Twitter/X.com domains."""
    externals, twitters = [], []
    for href in links:
        try:
            if not href.startswith("http"):
                full_href = f"https://www.twitter.com{href}"
                twitters.append(full_href)
                continue
            u = urlparse(href)
            host = (u.netloc or "").lower()
            if "twitter.com" in host or "x.com" in host:
                twitters.append(href)
            else:
                cleaned = f"{u.scheme}://{u.netloc}{u.path}" if u.scheme else href
                externals.append(cleaned.rstrip("/"))
        except Exception:
             if "twitter.com" in href or "x.com" in href:
                twitters.append(href)
             else:
                externals.append(href)
    return _dedupe_keep_order(externals), _dedupe_keep_order(twitters)

EMAIL_RE = re.compile(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", re.I)
PHONE_RE = re.compile(r"(\+?\d{1,3})?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
HASH_RE = re.compile(r"#\w+", re.U | re.I)

def _extract_entities_from_text(text: str) -> Dict[str, List[str]]:
    """Extracts emails, phone numbers, and hashtags from a block of text."""
    return {
        "emails": _dedupe_keep_order(EMAIL_RE.findall(text)),
        "phones": _dedupe_keep_order(PHONE_RE.findall(text)),
        "hashtags": _dedupe_keep_order(HASH_RE.findall(text)),
    }

# --------------------------------------------------------------------
# --- ✅ YOUR ORIGINAL DETAILED EXTRACTOR FUNCTION (KEPT) ---
# --------------------------------------------------------------------
async def extract_visible_text_from_twitter_page(page: Page) -> Dict:
    """Extracts all visible text, links, and usernames from the current Twitter/X page."""
    # Scroll down to trigger comment loading
    for _ in range(8):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)

    # --- Extract Text and Usernames from Tweets (main and replies) ---
    all_text_parts, all_users = [], []
    tweet_containers = page.locator('article[data-testid="tweet"]')
    
    for i in range(await tweet_containers.count()):
        tweet = tweet_containers.nth(i)
        try:
            text_content_locator = tweet.locator('div[data-testid="tweetText"]')
            text_content = _norm(await text_content_locator.inner_text())
            if text_content:
                all_text_parts.append(text_content)

            user_name_locator = tweet.locator('div[data-testid="User-Name"] a').first
            user_handle = _norm(await user_name_locator.get_attribute("href"))
            if user_handle:
                all_users.append(user_handle.lstrip('/'))
        except Exception:
            continue

    lines = _dedupe_keep_order(all_text_parts)
    full_text = "\n".join(lines)
    deduped_users = _dedupe_keep_order(all_users)
    main_author = deduped_users[0] if deduped_users else None
    reply_users = deduped_users[1:] if len(deduped_users) > 1 else []

    # --- Extract All Links ---
    raw_links = []
    anchors = page.locator('a[href]')
    for i in range(await anchors.count()):
        href = await anchors.nth(i).get_attribute("href")
        if href and not any(s in href for s in ["/analytics", "/hashtag/", "/search?q="]):
             raw_links.append(href)

    external_links, twitter_links = _split_twitter_links(_dedupe_keep_order(raw_links))
    entities = _extract_entities_from_text(full_text)

    return {
        "author": main_author, "main_tweet_text": lines[0] if lines else None,
        "text": full_text, "external_links": external_links, "twitter_links": twitter_links,
        "reply_users": reply_users, "emails": entities["emails"], "phones": entities["phones"],
        "hashtags": entities["hashtags"],
    }

# -------------------------------------------------------------------------
# --- 🔄 THE NEW REFACTORED MAIN FUNCTION (REPLACES THE OLD ONE) ---
# -------------------------------------------------------------------------
async def scrape_twitter_visible_text_seq(urls: List[str], page: Page) -> List[Dict]:
    """
    Sequentially scrapes a list of Twitter/X URLs using a PRE-CONFIGURED page object.
    """
    results = []
    for url in urls:
        item = {"platform": "twitter", "twitter_link": url, "scraped_at": int(time.time())}
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=25000)
            await page.wait_for_timeout(2000)

            try:
                close_button = page.locator('[aria-label="Close"], [aria-label="Dismiss"]').first
                if await close_button.is_visible(timeout=5000):
                    await close_button.click()
                    print("Closed a popup.")
            except (TimeoutError, Exception):
                pass 

            extracted = await extract_visible_text_from_twitter_page(page)
            item.update(extracted)
        except Exception as e:
            item["error"] = str(e)
        results.append(item)
    return results

# The `if __name__ == "__main__":` block is removed as this is now a library file.