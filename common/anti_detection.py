# common/anti_detection.py
import random
import asyncio
from playwright.async_api import TimeoutError as PWTimeout

USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    # Linux Chrome
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.117 Safari/537.36",
]

async def goto_resilient(page, url: str, retries: int = 3, timeout: int = 30000):
    """Navigate to a page with retries + human-like delays."""
    for attempt in range(retries):
        try:
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 4))  # mimic human pause
            return True
        except PWTimeout:
            wait_time = 2 ** attempt
            print(f"⚠️ Timeout loading {url}, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
    print(f"❌ Failed to load {url} after {retries} retries")
    return False

async def create_stealth_context(browser):
    """Create stealth browser context with random UA, viewport, and webdriver patch."""
    ua = random.choice(USER_AGENTS)
    viewport = {
        "width": random.randint(1280, 1600),
        "height": random.randint(720, 900),
    }

    context = await browser.new_context(
        user_agent=ua,
        viewport=viewport,
        locale="en-US",
    )

    # Patch webdriver property
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return context
