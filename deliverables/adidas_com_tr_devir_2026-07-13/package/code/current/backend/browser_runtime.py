import asyncio
import os

from security import validate_remote_url


MAX_HTML_BYTES = max(1024 * 1024, int(os.environ.get("MAX_RESPONSE_BYTES", str(5 * 1024 * 1024))))
GLOBAL_BROWSER_CONCURRENCY = max(1, int(os.environ.get("GLOBAL_BROWSER_CONCURRENCY", "2")))
STORE_BROWSER_CONCURRENCY = max(1, int(os.environ.get("STORE_BROWSER_CONCURRENCY", "1")))


class BrowserPool:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._contexts = {}
        self._global_sem = asyncio.Semaphore(GLOBAL_BROWSER_CONCURRENCY)
        self._store_sems = {}

    async def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            return
        async with self._lock:
            if self._browser and self._browser.is_connected():
                return
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError("Playwright kurulu degil") from exc
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )

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

    async def fetch(self, *, store_slug, domains, url, user_agent, timeout_ms=30000):
        await validate_remote_url(url, domains)
        store_sem = self._store_sems.setdefault(store_slug, asyncio.Semaphore(STORE_BROWSER_CONCURRENCY))
        async with self._global_sem, store_sem:
            context = await self._context(store_slug, user_agent)
            page = await context.new_page()

            async def block_heavy(route):
                if route.request.resource_type in {"media", "font"}:
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
                await validate_remote_url(page.url, domains)
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


browser_pool = BrowserPool()


async def shutdown_browser_pool():
    await browser_pool.close()
