"""Run one existing Product Radar watch and print its evidence summary.

This diagnostic intentionally uses the same discovery service as the API.  It
does not bypass store access controls and is useful when the UI session is not
available during a local maintenance test.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from browser_runtime import shutdown_browser_pool
from discovery_service import run_watch_discovery
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


async def main(watch_id: str) -> None:
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    try:
        watch = await db.watch_queries.find_one({"id": watch_id}, {"_id": 0})
        if not watch:
            raise SystemExit(f"Radar kaydi bulunamadi: {watch_id}")
        result = await run_watch_discovery(db, watch)
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    finally:
        await shutdown_browser_pool()
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("watch_id")
    arguments = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    asyncio.run(main(arguments.watch_id))
