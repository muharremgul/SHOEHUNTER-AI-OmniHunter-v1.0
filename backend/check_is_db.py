import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.shoehunter_ai
    
    cursor = db.listings.find({"url": {"$regex": "intersport.com.tr"}})
    listings = await cursor.to_list(length=10)
    
    print(f"Found {len(listings)} Intersport listings:")
    for l in listings:
        print(f"Price: {l.get('last_price')}, InStock: {l.get('last_in_stock')}, Error: {l.get('last_error')}")

if __name__ == "__main__":
    asyncio.run(run())
