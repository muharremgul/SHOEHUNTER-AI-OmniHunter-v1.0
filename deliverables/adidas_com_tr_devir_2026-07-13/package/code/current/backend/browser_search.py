import asyncio

from engines import _looks_like_bot_challenge


PER_ENGINE_TIMEOUT_SECONDS = 34


def _status_from_error(message):
    lowered = str(message).lower()
    if "403" in lowered or "429" in lowered or "captcha" in lowered or "bot" in lowered:
        return "blocked"
    if "404" in lowered:
        return "not_found"
    if "timeout" in lowered or "zaman" in lowered:
        return "timeout"
    return "error"


async def rendered_search_batch(engine_query_urls):
    """Render known-store search pages through the shared browser pool."""

    async def render_one(engine, url, query):
        try:
            html = await asyncio.wait_for(engine.fetch_with_browser(url), timeout=PER_ENGINE_TIMEOUT_SECONDS)
            if _looks_like_bot_challenge(html):
                return {
                    "store": engine.name,
                    "status": "blocked",
                    "results": [],
                    "error": "Bot korumasi",
                    "engine": "browser_pool",
                }
            results = engine.parse_search(html, query, url)
            return {
                "store": engine.name,
                "status": "ok",
                "results": results,
                "engine": "browser_pool",
            }
        except asyncio.TimeoutError:
            return {
                "store": engine.name,
                "status": "timeout",
                "results": [],
                "error": "Tarayici motoru zaman asimi",
                "engine": "browser_pool",
            }
        except Exception as exc:
            message = str(exc)[:180]
            return {
                "store": engine.name,
                "status": _status_from_error(message),
                "results": [],
                "error": message,
                "engine": "browser_pool",
            }

    return list(await asyncio.gather(*[render_one(engine, url, query) for engine, url, query in engine_query_urls]))
