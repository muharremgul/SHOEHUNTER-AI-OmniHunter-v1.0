import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor.motor_asyncio import AsyncIOMotorClient
from services import batch_check

async def run():
    print("Starting DB fix...")
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.shoehunter_ai
    await batch_check(db, trigger="manual_cleanup")
    print("DB fix complete!")

if __name__ == "__main__":
    asyncio.run(run())
