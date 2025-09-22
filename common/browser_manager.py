# common/browser_manager.py
from .anti_detection import create_stealth_context

async def get_browser(playwright, headless: bool = True):
    """Launch Chromium browser with anti-detection flags."""
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-extensions",
        ],
    )
    return browser

async def get_stealth_page(browser):
    """Create a stealth page using anti-detection context."""
    context = await create_stealth_context(browser)
    page = await context.new_page()
    return page
