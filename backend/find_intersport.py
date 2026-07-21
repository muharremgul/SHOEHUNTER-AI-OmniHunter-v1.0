import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.shoehunter_ai
    
    cursor = db.listings.find({"url": {"$regex": "intersport.com.tr"}, "last_in_stock": True})
    listings = await cursor.to_list(length=10)
    
    print(f"Found {len(listings)} IN-STOCK Intersport listings")
    for l in listings:
        print(f"URL: {l['url']}")

if __name__ == "__main__":
    asyncio.run(run())
