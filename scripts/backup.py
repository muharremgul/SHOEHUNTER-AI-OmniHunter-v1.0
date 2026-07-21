import asyncio
import os
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from backup_service import create_json_backup  # noqa: E402


async def main():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    try:
        result = await create_json_backup(client[os.environ.get("DB_NAME", "shoehunter_ai")])
        print(result["path"])
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
