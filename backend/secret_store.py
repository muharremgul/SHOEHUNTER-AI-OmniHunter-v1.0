import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

ROOT_DIR = Path(__file__).resolve().parent
KEY_FILE = Path(os.environ.get("SECRET_KEY_FILE", ROOT_DIR / ".shoehunter.key"))


def _key():
    configured = os.environ.get("APP_SECRET_KEY", "").strip()
    if configured:
        raw = configured.encode("utf-8")
        try:
            Fernet(raw)
            return raw
        except ValueError:
            import hashlib

            return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


def encrypt_secret(value):
    if not value:
        return None
    return Fernet(_key()).encrypt(str(value).encode("utf-8")).decode("ascii")


def decrypt_secret(value):
    if not value:
        return ""
    try:
        return Fernet(_key()).decrypt(str(value).encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, OSError):
        return ""


async def set_secret(db, name, value):
    await db.secrets.update_one(
        {"name": name},
        {"$set": {"name": name, "ciphertext": encrypt_secret(value)}},
        upsert=True,
    )


async def get_secret(db, name):
    doc = await db.secrets.find_one({"name": name}, {"_id": 0, "ciphertext": 1})
    stored = decrypt_secret((doc or {}).get("ciphertext"))
    if stored:
        return stored
    if name == "telegram_bot_token" and os.environ.get("TELEGRAM_BOT_TOKEN"):
        return os.environ["TELEGRAM_BOT_TOKEN"].strip()
    return ""


async def migrate_legacy_telegram_secret(db):
    settings = await db.settings.find_one({"id": "main"}, {"_id": 0, "telegram.bot_token": 1})
    legacy = ((settings or {}).get("telegram") or {}).get("bot_token")
    if legacy:
        existing = await get_secret(db, "telegram_bot_token")
        if not existing:
            await set_secret(db, "telegram_bot_token", legacy)
        await db.settings.update_one({"id": "main"}, {"$unset": {"telegram.bot_token": ""}})
