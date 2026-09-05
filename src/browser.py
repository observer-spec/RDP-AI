"""Playwright browser singleton (extracted from server.py)."""

browser_instance = None
browser_page = None
playwright_obj = None


async def get_browser_page():
    global browser_instance, browser_page, playwright_obj
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "Playwright is not installed"

    if browser_page is None or browser_page.is_closed():
        if playwright_obj is None:
            playwright_obj = await async_playwright().start()
        browser_instance = await playwright_obj.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser_instance.new_context(viewport={"width": 1920, "height": 1080})
        browser_page = await context.new_page()

    return browser_page, None
