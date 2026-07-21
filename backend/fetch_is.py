import asyncio
import os
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import get_engine_for_url


async def run():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.shoehunter_ai

    cursor = db.listings.find({"url": {"$regex": "intersport.com.tr"}})
    listings = await cursor.to_list(length=3)

    engine = get_engine_for_url("https://intersport.com.tr")

    for i, listing in enumerate(listings):
        url = listing["url"]
        print(f"Fetching: {url}")
        html = await engine.fetch(url)
        Path(f"is{i}.html").write_text(html, encoding="utf-8")
        print(f"Saved is{i}.html")

    client.close()


if __name__ == "__main__":
    asyncio.run(run())
