import re
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse
from playwright.async_api import TimeoutError as PWTimeout, Page

# --- Utilities ---
def _is_twitter(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return "twitter.com" in host or "x.com" in host
    except Exception:
        return False

def _dedupe(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

def _compact_to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    t = s.strip().lower().replace(",", "")
    m = re.match(r"^(\d+(?:\.\d+)?)([km])?$", t)
    if not m:
        digits = re.sub(r"[^\d]", "", t)
        return int(digits) if digits else None
    num = float(m.group(1))
    suf = m.group(2)
    if suf == "k":
        num *= 1_000
    elif suf == "m":
        num *= 1_000_000
    return int(num)

def _contacts(text: Optional[str]) -> Dict[str, List[str]]:
    if not text:
        return {"emails": [], "phones": []}
    emails = list({m.group(0) for m in re.finditer(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)})
    phones = list({m.group(0) for m in re.finditer(r"\+?\d[\d\s().\-]{8,}\d", text)})
    return {"emails": emails, "phones": phones}

# --- Playwright helpers ---
async def _goto(page: Page, url: str):
    await page.goto(url, wait_until="domcontentloaded", timeout=35000)
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

async def _first_text(page: Page, selectors: List[str], timeout_ms: int = 6000) -> Optional[str]:
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=timeout_ms, state="attached")
            txt = (await el.text_content() or "").strip()
            if txt:
                return txt
        except Exception:
            pass
    return None

# --- Selectors ---
NAME_SEL = ["div[data-testid='UserName'] span"]
HANDLE_SEL = ["div[data-testid='UserName'] div span:has-text('@')"]
BIO_SEL = ["div[data-testid='UserDescription'] span"]
FOLLOWERS_SEL = ["a[href$='/verified_followers'] span", "a[href$='/followers'] span"]
FOLLOWING_SEL = ["a[href$='/following'] span"]

# --- Extract profile ---
async def _extract_profile(page: Page, url: str) -> Dict:
    name = await _first_text(page, NAME_SEL)
    handle = await _first_text(page, HANDLE_SEL)
    if not handle and url:
        handle = "@" + url.rstrip("/").split("/")[-1]

    bio = await _first_text(page, BIO_SEL)
    followers = await _first_text(page, FOLLOWERS_SEL)
    following = await _first_text(page, FOLLOWING_SEL)

    followers_num = _compact_to_int(followers)
    following_num = _compact_to_int(following)

    text_blob = " ".join([name or "", handle or "", bio or ""])
    contacts = _contacts(text_blob)

    result = {
        "platform": "twitter", "twitter_link": url, "name": name, "handle": handle,
        "bio": bio, "followers": followers, "followers_num": followers_num,
        "following": following, "following_num": following_num,
        "emails": contacts["emails"], "phones": contacts["phones"],
        "scraped_at": int(time.time())
    }

    if not (name or bio):
        result["error"] = "Failed to extract"
    return result

# --- Main META scraper ---
async def scrape_twitter_profiles_async(urls: List[str], page: Page) -> List[Dict]:
    norm = _dedupe([u.strip() for u in urls if u and _is_twitter(u)])
    results: List[Dict] = []

    total = len(norm)
    print(f"\n[META] Starting META scrape for {total} URLs\n")

    for idx, link in enumerate(norm, start=1):
        print(f"[META] {idx}/{total} → Starting scrape: {link}")
        try:
            await _goto(page, link)
            profile = await _extract_profile(page, link)
            results.append(profile)
            print(f"[META] {idx}/{total} → Completed: {link}")
        except PWTimeout:
            print(f"[META] {idx}/{total} → TIMEOUT: {link}")
            results.append({"platform": "twitter", "twitter_link": link, "error": "Navigation timeout"})
        except Exception as e:
            print(f"[META] {idx}/{total} → ERROR on {link}: {e}")
            results.append({"platform": "twitter", "twitter_link": link, "error": str(e)})

    return results
