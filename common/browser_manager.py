"""
Twitter Browser Manager - async Playwright wrapper with anti-detection features
Drop-in replacement for your project's browser management.
Requires: playwright (async_api), fake-useragent (optional), or you can pass your own UA.

Usage (example):
    from common.browser_manager import BrowserManager
    mgr = BrowserManager(headless=True, enable_anti_detection=True)
    await mgr.launch()
    page = await mgr.new_page()
    await page.goto("https://x.com/elonmusk")
    # ... use page
    await mgr.close()
"""

import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

# Optional dependency: fake_useragent. If unavailable, fallback to a simple UA list.
try:
    from fake_useragent import UserAgent  # type: ignore
    _FAKE_UA = UserAgent()
except Exception:
    _FAKE_UA = None

# Small fallback UA list – kept purposefully short; add more as needed.
FALLBACK_UAS = [
    # desktop Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    # mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    # desktop Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
]

DEFAULT_VIEWPORT = {"width": 1280, "height": 800}


class BrowserManager:
    def __init__(
        self,
        headless: bool = True,
        enable_anti_detection: bool = True,
        is_mobile: bool = False,
        slow_mo: Optional[int] = None,
        proxy: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None,
        cookies_path: Optional[str] = None,
    ) -> None:
        """
        :param headless: run browser headless
        :param enable_anti_detection: enable UA rotation + init script spoofing
        :param is_mobile: emulate mobile viewport and UA
        :param slow_mo: slowdown in ms for actions (for debugging/human sim)
        :param proxy: dict like {"server": "http://...", "username": "...", "password": "..."}
        :param user_agent: override UA selection
        :param cookies_path: optional path to load/save cookies JSON
        """
        self.headless = headless
        self.enable_anti_detection = enable_anti_detection
        self.is_mobile = is_mobile
        self.slow_mo = slow_mo
        self.proxy = proxy
        self._provided_user_agent = user_agent
        self.cookies_path = Path(cookies_path) if cookies_path else None

        # Playwright internals
        self._playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        # chosen UA
        self.user_agent = user_agent or self._pick_user_agent(is_mobile)

    def _pick_user_agent(self, is_mobile: bool) -> str:
        if self._provided_user_agent:
            return self._provided_user_agent

        # try fake_useragent first
        if _FAKE_UA:
            try:
                if is_mobile:
                    return _FAKE_UA.random.replace("Windows NT 10.0; Win64; x64", "Android 12")
                return _FAKE_UA.random
            except Exception:
                pass

        # fallback pick
        ua = random.choice(FALLBACK_UAS)
        if is_mobile:
            # quick mobile UA hack
            ua = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.62 Mobile Safari/537.36"
        return ua

    async def launch(self) -> None:
        """Start Playwright and launch a browser instance (Chromium)."""
        self._playwright = await async_playwright().start()
        launch_args = {"headless": self.headless}
        if self.slow_mo:
            launch_args["slow_mo"] = self.slow_mo
        if self.proxy:
            launch_args["proxy"] = self.proxy

        # Use Chromium by default (best compatibility with stealth tricks)
        self.browser = await self._playwright.chromium.launch(**launch_args)
        await self._create_context()

    async def _create_context(self) -> None:
        if not self.browser:
            raise RuntimeError("Browser is not launched. Call launch() first.")

        context_opts: Dict[str, Any] = {
            "viewport": DEFAULT_VIEWPORT if not self.is_mobile else {"width": 360, "height": 800},
            "user_agent": self.user_agent,
            # default permissions for Twitter: allow notifications only if needed
            "permissions": [],
            "locale": "en-US",
        }

        # Chromium-specific: reduce detection surface by disabling automation flags
        # Note: Playwright launches a real browser, but we further mitigate detection via init scripts below.
        self.context = await self.browser.new_context(**context_opts)

        if self.enable_anti_detection:
            await self._apply_anti_detection(self.context)

        # load cookies if path provided
        if self.cookies_path and self.cookies_path.exists():
            await self.load_cookies(self.cookies_path)

    async def new_page(self) -> Page:
        """Create and return a new Page object from the managed context."""
        if not self.context:
            raise RuntimeError("Context missing. Did you call launch()?")

        page = await self.context.new_page()
        # Some helpful defaults for Twitter scraping
        await page.set_viewport_size(self.context.viewport_size or DEFAULT_VIEWPORT)
        # small random delay to avoid synchronized patterns
        await self._random_delay(0.2, 0.6)
        return page

    async def close(self) -> None:
        """Close context, browser and stop playwright."""
        try:
            if self.context:
                # Save cookies if configured
                if self.cookies_path:
                    await self.save_cookies(self.cookies_path)
                await self.context.close()
            if self.browser:
                await self.browser.close()
        finally:
            if self._playwright:
                await self._playwright.stop()

    # ---------------- Anti-detection helpers ----------------
    async def _apply_anti_detection(self, context: BrowserContext) -> None:
        """
        Injects scripts & overrides to make the context appear more human:
          - navigator.webdriver = undefined
          - languages / plugins override
          - webgl / hardwareConcurrency tweaks (minimal)
        """
        # Init script to run before any page scripts
        init_script = """
        // navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        // languages
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        // plugins - fake a few plugins
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        // Chrome object
        window.chrome = window.chrome || { runtime: {} };
        // permissions query shim
        const _exec = window.navigator.permissions.query;
        if (_exec) {
            const origQuery = _exec.bind(navigator.permissions);
            navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : origQuery(parameters)
            );
        }
        """

        try:
            await context.add_init_script(init_script)
        except Exception:
            # older playwright versions may behave differently
            pass

        # Optionally, set extra headers (referer, accept-language) across context
        headers = {
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://twitter.com/",
        }
        try:
            await context.set_extra_http_headers(headers)
        except Exception:
            # Some drivers may not support set_extra_http_headers
            pass

    # ---------------- Human behavior helpers ----------------
    async def execute_human_like_behavior(self, page: Page, *,
                                          scroll_depth: int = 3,
                                          max_pause: float = 1.2) -> None:
        """Simulate reading/scrolling/hovering to appear human."""
        try:
            for _ in range(scroll_depth):
                # small scroll amount with ease
                scroll_amount = random.randint(200, 800)
                await page.mouse.wheel(0, scroll_amount)
                await self._random_delay(0.4, max_pause)
                # small random mouse moves
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await page.mouse.move(x, y, steps=random.randint(5, 15))
                await self._random_delay(0.1, 0.5)
        except Exception:
            # non-fatal if page doesn't support mouse interactions (e.g. already closed)
            pass

    async def type_like_a_human(self, page: Page, selector: str, text: str) -> None:
        """Type into an input using human-like delays."""
        await page.focus(selector)
        for ch in text:
            await page.keyboard.type(ch)
            await self._random_delay(0.03, 0.18)

    async def click_like_a_human(self, page: Page, selector: str) -> None:
        """Click with random small delay and jitter in coordinates."""
        box = await page.query_selector(selector)
        if not box:
            await page.click(selector)  # may raise
            return
        bounding = await box.bounding_box()
        if bounding:
            x = bounding["x"] + random.uniform(2, bounding["width"] - 2)
            y = bounding["y"] + random.uniform(2, bounding["height"] - 2)
            await page.mouse.click(x, y)
        else:
            await page.click(selector)

    # ---------------- Cookie utilities ----------------
    async def save_cookies(self, path: Path) -> None:
        """Save context cookies to path (JSON)."""
        if not self.context:
            return
        cookies = await self.context.cookies()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
        except Exception:
            pass

    async def load_cookies(self, path: Path) -> None:
        """Load cookies (if any) into current context. Note: must be called when context exists."""
        if not self.context or not path.exists():
            return
        try:
            with path.open("r", encoding="utf-8") as f:
                cookies = json.load(f)
            # ensure domain path matches (Playwright expects domain in cookie)
            await self.context.add_cookies(cookies)
        except Exception:
            # best-effort only
            pass

    # ---------------- Utilities ----------------
    async def screenshot(self, page: Page, path: str) -> None:
        try:
            await page.screenshot(path=path, full_page=True)
        except Exception:
            pass

    async def wait_for_selector(self, page: Page, selector: str, timeout: int = 10000) -> Optional[Any]:
        try:
            return await page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            return None

    async def _random_delay(self, a: float = 0.1, b: float = 0.5) -> None:
        await asyncio.sleep(random.uniform(a, b))


# ---------------- Simple CLI test helper ----------------
if __name__ == "__main__":
    # Quick manual test: launch, open X, screenshot, close
    async def _test():
        mgr = BrowserManager(headless=True, enable_anti_detection=True, cookies_path="./tmp/twitter_cookies.json")
        await mgr.launch()
        page = await mgr.new_page()
        await page.goto("https://x.com")
        await mgr.execute_human_like_behavior(page, scroll_depth=2)
        await mgr.screenshot(page, "tmp/x_home.png")
        await mgr.close()

    asyncio.run(_test())
