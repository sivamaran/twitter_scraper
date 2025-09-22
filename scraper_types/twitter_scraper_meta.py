# scraper_types/twitter_scraper_meta.py
import re, time
from typing import List, Dict, Optional
from urllib.parse import urlparse
from playwright.async_api import Page
from common.anti_detection import goto_resilient

def _is_twitter(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "twitter.com" in host or "x.com" in host

def _dedupe(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for s in seq:
        if s not in seen:
            seen.add(s); out.append(s)
    return out

def _compact_to_int(s: Optional[str]) -> Optional[int]:
    if not s: return None
    t = s.strip().lower().replace(",", "")
    m = re.match(r"^(\d+(?:\.\d+)?)([km])?$", t)
    if not m: return None
    num, suf = float(m.group(1)), m.group(2)
    return int(num * (1_000 if suf == "k" else 1_000_000 if suf == "m" else 1))

def _contacts(text: Optional[str]) -> Dict[str, List[str]]:
    if not text: return {"emails": [], "phones": []}
    emails = list({m.group(0) for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)})
    phones = list({m.group(0) for m in re.finditer(r"\+?\d[\d\s().\-]{8,}\d", text)})
    return {"emails": emails, "phones": phones}

NAME_SEL = ["div[data-testid='UserName'] span"]
HANDLE_SEL = ["div[data-testid='UserName'] div span:has-text('@')"]
BIO_SEL = ["div[data-testid='UserDescription'] span"]
FOLLOWERS_SEL = ["a[href$='/followers'] span"]
FOLLOWING_SEL = ["a[href$='/following'] span"]

async def _first_text(page: Page, selectors: List[str]) -> Optional[str]:
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=5000)
            txt = (await el.text_content() or "").strip()
            if txt: return txt
        except Exception: pass
    return None

async def _extract_profile(page: Page, url: str) -> Dict:
    name = await _first_text(page, NAME_SEL)
    handle = await _first_text(page, HANDLE_SEL) or "@" + url.rstrip("/").split("/")[-1]
    bio = await _first_text(page, BIO_SEL)
    followers = await _first_text(page, FOLLOWERS_SEL)
    following = await _first_text(page, FOLLOWING_SEL)

    return {
        "platform": "twitter",
        "twitter_link": url,
        "name": name,
        "handle": handle,
        "bio": bio,
        "followers": followers,
        "followers_num": _compact_to_int(followers),
        "following": following,
        "following_num": _compact_to_int(following),
        "scraped_at": int(time.time()),
    }

async def scrape_twitter_profiles_async(urls: List[str], page: Page) -> List[Dict]:
    results: List[Dict] = []
    for link in _dedupe(urls):
        if not _is_twitter(link): continue
        ok = await goto_resilient(page, link)
        if not ok:
            results.append({"twitter_link": link, "error": "Navigation failed"})
            continue
        results.append(await _extract_profile(page, link))
    return results
