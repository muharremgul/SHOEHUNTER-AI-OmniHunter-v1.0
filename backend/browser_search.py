import asyncio
import math
import os

from browser_runtime import GLOBAL_BROWSER_CONCURRENCY
from engines import _looks_like_bot_challenge

PER_ENGINE_BUDGET_SECONDS = max(20, int(os.environ.get("BROWSER_ENGINE_BUDGET_SECONDS", "45")))
BROWSER_BATCH_MAX_SECONDS = max(
    PER_ENGINE_BUDGET_SECONDS,
    int(os.environ.get("BROWSER_BATCH_MAX_SECONDS", "420")),
)


def _status_from_error(message):
    lowered = str(message).lower()
    if "403" in lowered or "429" in lowered or "captcha" in lowered or "bot" in lowered:
        return "blocked"
    if "404" in lowered:
        return "not_found"
    if "timeout" in lowered or "zaman" in lowered:
        return "timeout"
    if "winerror 5" in lowered or "permissionerror" in lowered:
        return "runtime_error"
    if "all connection attempts failed" in lowered or "name or service not known" in lowered:
        return "network_error"
    return "error"


def browser_batch_timeout(item_count):
    """Return a deadline aligned with the browser pool's real concurrency."""

    if item_count <= 0:
        return 0
    waves = math.ceil(item_count / GLOBAL_BROWSER_CONCURRENCY)
    return min(BROWSER_BATCH_MAX_SECONDS, (waves * PER_ENGINE_BUDGET_SECONDS) + 10)


async def rendered_search_batch(engine_query_urls, overall_timeout_seconds=None):
    """Render store searches without timing out tasks while they wait in line.

    A small worker queue mirrors the browser pool's actual concurrency.  The
    previous implementation started every per-store timeout immediately, so
    later stores could expire before they ever acquired a browser slot.  If
    the overall deadline is reached, completed stores are retained and only
    unfinished entries are marked as timed out.
    """

    entries = list(engine_query_urls)
    if not entries:
        return []

    async def render_one(engine, url, query):
        try:
            html = await engine.fetch_with_browser(url)
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
        except TimeoutError:
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

    results = [None] * len(entries)
    queue = asyncio.Queue()
    for index, entry in enumerate(entries):
        queue.put_nowait((index, entry))

    async def worker():
        while True:
            try:
                index, (engine, url, query) = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                results[index] = await render_one(engine, url, query)
            finally:
                queue.task_done()

    worker_count = min(len(entries), GLOBAL_BROWSER_CONCURRENCY)
    workers = [asyncio.create_task(worker()) for _ in range(worker_count)]
    timeout = overall_timeout_seconds
    if timeout is None and len(entries) > 1:
        timeout = browser_batch_timeout(len(entries))
    done, pending = await asyncio.wait(workers, timeout=timeout)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        # render_one converts store failures into result dictionaries.  This
        # only surfaces programming errors in the queue worker itself.
        task.result()

    for index, result in enumerate(results):
        if result is not None:
            continue
        engine = entries[index][0]
        results[index] = {
            "store": engine.name,
            "status": "capacity_timeout",
            "results": [],
            "error": "Tarayici kapasite sirasi zaman asimi",
            "engine": "browser_pool",
        }
    return results
