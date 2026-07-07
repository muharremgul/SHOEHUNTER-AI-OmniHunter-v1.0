import asyncio

from engines import HEADERS

_sem = asyncio.Semaphore(3)


async def rendered_search_batch(engine_query_urls):
    """engine_query_urls: list of (engine, search_url, query). Returns store result dicts."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return [
            {"store": e.name, "status": "error", "results": [], "error": "Playwright kurulu değil"}
            for e, _, _ in engine_query_urls
        ]

    results = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="tr-TR",
                viewport={"width": 1366, "height": 900},
            )

            async def one(engine, url, query):
                async with _sem:
                    page = await context.new_page()
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except Exception:
                            pass
                        await page.mouse.wheel(0, 1200)
                        await page.wait_for_timeout(3500)
                        title = (await page.title()) or ""
                        if any(k in title.lower() for k in ["recaptcha", "captcha", "robot", "doğrulama", "kontrol ediliyor"]):
                            return {"store": engine.name, "status": "blocked", "results": [], "error": "Captcha/bot koruması", "engine": "playwright"}
                        html = await page.content()
                        res = engine.parse_search(html, query, url)
                        return {"store": engine.name, "status": "ok", "results": res, "engine": "playwright"}
                    except Exception as exc:
                        msg = str(exc)[:150]
                        status = "blocked" if "403" in msg or "429" in msg else "error"
                        return {"store": engine.name, "status": status, "results": [], "error": msg, "engine": "playwright"}
                    finally:
                        await page.close()

            results = list(
                await asyncio.gather(*[one(e, u, q) for e, u, q in engine_query_urls])
            )
            await browser.close()
    except Exception as exc:
        return [
            {"store": e.name, "status": "error", "results": [], "error": f"Tarayıcı motoru hatası: {str(exc)[:100]}"}
            for e, _, _ in engine_query_urls
        ]
    return results
