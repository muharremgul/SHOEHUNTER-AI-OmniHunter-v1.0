import argparse
import asyncio
import os
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from restore_service import inspect_backup, restore_json_backup  # noqa: E402


async def main():
    parser = argparse.ArgumentParser(description="ShoeHunter JSON yedegini geri yukler")
    parser.add_argument("path")
    parser.add_argument("--apply", action="store_true", help="Onizleme yerine geri yuklemeyi uygula")
    parser.add_argument("--replace", action="store_true", help="Uygulama koleksiyonlarini once temizle")
    args = parser.parse_args()
    summary = inspect_backup(args.path)
    if not args.apply:
        print("Onizleme tamamlandi. Veri degistirilmedi.")
        print(summary)
        return
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    try:
        restored = await restore_json_backup(
            client[os.environ.get("DB_NAME", "shoehunter_ai")],
            args.path,
            replace=args.replace,
        )
        print(restored)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
