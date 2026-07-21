import asyncio
import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stores.adidas import AdidasEngine


async def test_adidas():
    engine = AdidasEngine()
    url = "https://www.adidas.com.tr/tr/adizero-aruku/JQ1616.html"
    print(f"Fetching URL with the configured Adidas engine: {url}")
    html = await engine.fetch(url)

    print(f"HTML Length: {len(html)}")

    soup = BeautifulSoup(html, "lxml")
    json_lds = soup.find_all("script", type="application/ld+json")
    print(f"Found {len(json_lds)} JSON-LD scripts.")

    import json

    for i, script in enumerate(json_lds):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                print(f"[{i}] type: {data.get('@type')}")
                if data.get("@type") == "ProductGroup":
                    print("  -> Found ProductGroup!")
                    print("  -> hasVariant keys:", data.get("hasVariant", [])[:1])
            elif isinstance(data, list):
                print(f"[{i}] type: list, length: {len(data)}")
        except Exception as e:
            print(f"[{i}] JSON Parse Error: {e}")

    print("\n--- Running Engine Parse ---")
    result = engine.parse(html, url)
    print("Price:", result.get("current_price"))
    print("Stock Count:", result.get("stock_count"))
    print("In Stock:", result.get("in_stock"))
    print("Sizes:", len(result.get("sizes", [])))


if __name__ == "__main__":
    asyncio.run(test_adidas())
