"""Apply idempotent ShoeHunter database migrations and indexes."""

import asyncio
import os
from pathlib import Path

from database_setup import ensure_database
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=2000,
        tz_aware=True,
    )
    try:
        await ensure_database(client[os.environ.get("DB_NAME", "shoehunter_ai")])
        print("safe_migrations_applied")
    finally:
        client.close()


if __name__ == "__main__":
    load_dotenv(Path(__file__).with_name(".env"))
    asyncio.run(main())
