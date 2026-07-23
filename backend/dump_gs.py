import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from browser_runtime import browser_pool

async def main():
    print("Fetching Google Shopping HTML...")
    url = "https://www.google.com/search?tbm=shop&q=vomero+18"
    html = await browser_pool.fetch(
        store_slug="google_shopping",
        domains=["google.com"],
        url=url,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        browser_wait_selector=None
    )
    with open("gs_vomero.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved {len(html)} bytes to gs_vomero.html")

if __name__ == '__main__':
    asyncio.run(main())
