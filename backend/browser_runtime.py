import asyncio
import os
import time

from security import validate_remote_url

MAX_HTML_BYTES = max(1024 * 1024, int(os.environ.get("MAX_RESPONSE_BYTES", str(5 * 1024 * 1024))))
GLOBAL_BROWSER_CONCURRENCY = max(1, int(os.environ.get("GLOBAL_BROWSER_CONCURRENCY", "3")))
STORE_BROWSER_CONCURRENCY = max(1, int(os.environ.get("STORE_BROWSER_CONCURRENCY", "1")))


class BrowserPool:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._contexts = {}
        self._global_sem = asyncio.Semaphore(GLOBAL_BROWSER_CONCURRENCY)
        self._store_sems = {}
        self._launch_error = None
        self._launch_retry_after = 0.0

    def _raise_cached_launch_error(self):
        if self._launch_error and time.monotonic() < self._launch_retry_after:
            raise RuntimeError(self._launch_error)

    async def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            return
        self._raise_cached_launch_error()
        async with self._lock:
            if self._browser and self._browser.is_connected():
                return
            self._raise_cached_launch_error()
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError("Playwright kurulu degil") from exc
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled"
                    ],
                    ignore_default_args=["--enable-automation"]
                )
            except Exception as exc:
                self._browser = None
                if self._playwright:
                    try:
                        await self._playwright.stop()
                    except Exception:
                        pass
                self._playwright = None
                self._launch_error = f"Tarayici calisma ortami baslatilamadi: {str(exc)[:240]}"
                self._launch_retry_after = time.monotonic() + 60
                raise RuntimeError(self._launch_error) from exc
            self._launch_error = None
            self._launch_retry_after = 0.0

    async def _context(self, store_slug, user_agent):
        await self._ensure_browser()
        context = self._contexts.get(store_slug)
        if context:
            return context
        async with self._lock:
            context = self._contexts.get(store_slug)
            if not context:
                context = await self._browser.new_context(
                    user_agent=user_agent,
                    locale="tr-TR",
                    viewport={"width": 1366, "height": 900},
                    service_workers="block",
                )
                self._contexts[store_slug] = context
        return context

    async def fetch(
        self,
        *,
        store_slug,
        domains,
        url,
        user_agent,
        timeout_ms=30000,
        browser_wait_selector=None,
        screenshot_path=None,
    ):
        await validate_remote_url(url, domains)
        store_sem = self._store_sems.setdefault(store_slug, asyncio.Semaphore(STORE_BROWSER_CONCURRENCY))
        async with self._global_sem, store_sem:
            context = await self._context(store_slug, user_agent)
            page = await context.new_page()
            try:
                from playwright_stealth.stealth import Stealth
                await Stealth().apply_stealth_async(page)
            except ImportError as e:
                import logging
                logging.getLogger("shoehunter").warning(f"Stealth import failed: {e}")

            async def block_heavy(route):
                if route.request.resource_type in {"media", "font"} and not screenshot_path:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", block_heavy)
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if response and response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                try:
                    await page.wait_for_load_state("networkidle", timeout=7000)
                except Exception:
                    pass
                if browser_wait_selector:
                    try:
                        await page.wait_for_selector(browser_wait_selector, timeout=5000)
                    except Exception:
                        pass
                await validate_remote_url(page.url, domains)
                
                # Take screenshot if requested
                if screenshot_path:
                    try:
                        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                        await page.screenshot(path=screenshot_path, full_page=False)
                    except Exception as e:
                        import logging
                        logging.getLogger("shoehunter").error(f"Screenshot failed: {e}")
                
                html = await page.content()
                if len(html.encode("utf-8")) > MAX_HTML_BYTES:
                    raise RuntimeError("Urun sayfasi izin verilen boyutu asti")
                return html
            finally:
                await page.close()

    async def close(self):
        for context in list(self._contexts.values()):
            try:
                await context.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._launch_error = None
        self._launch_retry_after = 0.0


browser_pool = BrowserPool()


async def shutdown_browser_pool():
    await browser_pool.close()
