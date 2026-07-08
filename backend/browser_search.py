import asyncio

from engines import HEADERS, _looks_like_bot_challenge

_sem = asyncio.Semaphore(3)
PER_ENGINE_TIMEOUT_SECONDS = 34


async def rendered_search_batch(engine_query_urls):
    """engine_query_urls: list of (engine, search_url, query). Returns store result dicts."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return [
            {"store": e.name, "status": "error", "results": [], "error": "Playwright kurulu degil"}
            for e, _, _ in engine_query_urls
        ]

    results = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="tr-TR",
                viewport={"width": 1366, "height": 900},
            )

            # Helper to apply stealth safely without crashing if not installed
            async def _apply_stealth(pg):
                try:
                    from playwright_stealth.stealth import Stealth
                    await Stealth().apply_stealth_async(pg)
                except Exception:
                    pass

            async def render_one(engine, url, query):
                page = await context.new_page()
                await _apply_stealth(page)
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=18000)
                    status_code = response.status if response else None
                    if status_code in (403, 429):
                        return {"store": engine.name, "status": "blocked", "results": [], "error": f"HTTP {status_code}", "engine": "playwright"}
                    if status_code and status_code >= 400:
                        return {"store": engine.name, "status": "error", "results": [], "error": f"HTTP {status_code}", "engine": "playwright"}
                    try:
                        await page.wait_for_load_state("networkidle", timeout=6000)
                    except Exception:
                        pass
                    await page.mouse.wheel(0, 1200)
                    await page.wait_for_timeout(3000)
                    title = (await page.title()) or ""
                    title_key = title.lower().replace("\u011f", "g")
                    if any(k in title_key for k in ["recaptcha", "captcha", "robot", "dogrulama", "kontrol ediliyor"]):
                        return {"store": engine.name, "status": "blocked", "results": [], "error": "Captcha/bot korumasi", "engine": "playwright"}
                    html = await page.content()
                    if _looks_like_bot_challenge(html):
                        return {"store": engine.name, "status": "blocked", "results": [], "error": "Bot korumasi", "engine": "playwright"}
                    res = engine.parse_search(html, query, url)
                    return {"store": engine.name, "status": "ok", "results": res, "engine": "playwright"}
                except Exception as exc:
                    msg = str(exc)[:150]
                    status = "blocked" if "403" in msg or "429" in msg else "error"
                    return {"store": engine.name, "status": status, "results": [], "error": msg, "engine": "playwright"}
                finally:
                    await page.close()

            async def one(engine, url, query):
                async with _sem:
                    try:
                        return await asyncio.wait_for(render_one(engine, url, query), timeout=PER_ENGINE_TIMEOUT_SECONDS)
                    except asyncio.TimeoutError:
                        return {"store": engine.name, "status": "timeout", "results": [], "error": "Tarayici motoru zaman asimi", "engine": "playwright"}

            results = list(
                await asyncio.gather(*[one(e, u, q) for e, u, q in engine_query_urls])
            )
            await browser.close()
    except Exception as exc:
        return [
            {"store": e.name, "status": "error", "results": [], "error": f"Tarayici motoru hatasi: {str(exc)[:100]}"}
            for e, _, _ in engine_query_urls
        ]
    return results
