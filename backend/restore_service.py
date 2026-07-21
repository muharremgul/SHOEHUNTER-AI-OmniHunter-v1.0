import json
from datetime import datetime
from pathlib import Path

from backup_service import BACKUP_COLLECTIONS, verify_backup


IDENTITY_FIELDS = {
    "store_health": "store_slug",
    "settings": "id",
    "user_profile": "id",
}


def inspect_backup(path):
    verify_backup(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "schema_version": payload["schema_version"],
        "created_at": payload.get("created_at"),
        "collections": {name: len(rows) for name, rows in payload["collections"].items()},
    }


def _restore_datetimes(value, key=None):
    if isinstance(value, dict):
        return {child_key: _restore_datetimes(child, child_key) for child_key, child in value.items()}
    if isinstance(value, list):
        return [_restore_datetimes(child) for child in value]
    if isinstance(value, str) and key and (key.endswith("_at") or key in {"run_at", "lease_until", "expires_at"}):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


async def restore_json_backup(db, path, *, replace=False):
    verify_backup(path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    restored = {}
    for name in BACKUP_COLLECTIONS:
        rows = payload["collections"].get(name, [])
        if replace:
            await db[name].delete_many({})
        count = 0
        for raw in rows:
            document = _restore_datetimes(raw)
            identity_field = IDENTITY_FIELDS.get(name, "id")
            identity = document.get(identity_field)
            if identity is None:
                continue
            await db[name].replace_one({identity_field: identity}, document, upsert=True)
            count += 1
        restored[name] = count
    return restored
