"""Send one controlled ShopHunter notification to registered Android devices.

The script never prints installation IDs or device credentials. It is intended
for an explicit, local end-to-end delivery check after a phone has registered.
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from fcm_service import send_fcm_alert  # noqa: E402


async def main() -> int:
    client = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=2000,
        tz_aware=True,
    )
    db = client[os.environ.get("DB_NAME", "shoehunter_ai")]
    try:
        registered = await db.mobile_devices.count_documents(
            {"enabled": True, "fcm_fid": {"$type": "string", "$ne": ""}}
        )
        if registered < 1:
            print(json.dumps({"sent": False, "registered_devices": 0, "reason": "kayitli_cihaz_yok"}))
            return 2

        now = datetime.now(UTC)
        alert = {
            "id": f"fcm-device-test-{uuid4()}",
            "alert_type": "system_test",
            "title": "ShopHunter Radar bildirim testi",
            "product_name": "Firebase bildirimi başarıyla ulaştı",
            "store": "ShopHunter-Radar",
            "sizes": ["TEST"],
            "created_at": now,
        }
        result = await send_fcm_alert(db, alert)
        safe_result = {
            "sent": bool(result.get("sent")),
            "registered_devices": registered,
            "sent_count": int(result.get("sent_count") or 0),
            "failure_count": int(result.get("failure_count") or 0),
            "error": result.get("error") or result.get("reason"),
            "test_alert_id": alert["id"],
            "sent_at": now.isoformat(),
        }
        print(json.dumps(safe_result, ensure_ascii=False))
        return 0 if safe_result["sent"] else 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
