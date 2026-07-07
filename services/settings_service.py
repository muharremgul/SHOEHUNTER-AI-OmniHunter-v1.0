import json
from pathlib import Path
from copy import deepcopy

class SettingsService:
    SETTINGS_PATH = Path("data/settings.json")

    DEFAULTS = {
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
        },
        "scheduler": {
            "enabled": False,
            "interval_minutes": 60,
        },
    }

    @classmethod
    def load(cls) -> dict:
        cls.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

        if not cls.SETTINGS_PATH.exists():
            cls.save(deepcopy(cls.DEFAULTS))
            return deepcopy(cls.DEFAULTS)

        try:
            with cls.SETTINGS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = deepcopy(cls.DEFAULTS)

        merged = deepcopy(cls.DEFAULTS)

        for key, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value

        return merged

    @classmethod
    def save(cls, data: dict) -> None:
        cls.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

        with cls.SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def update_telegram(cls, enabled: bool, bot_token: str, chat_id: str, preserve_empty_token: bool = True) -> None:
        data = cls.load()
        current_token = data.get("telegram", {}).get("bot_token", "")

        if preserve_empty_token and not bot_token:
            bot_token = current_token

        data["telegram"] = {
            "enabled": enabled,
            "bot_token": bot_token,
            "chat_id": chat_id,
        }

        cls.save(data)

    @classmethod
    def update_scheduler(cls, enabled: bool, interval_minutes: int) -> None:
        data = cls.load()

        # Süreyi 1 dakikaya indirme limiti eklendi
        if interval_minutes < 1:
            interval_minutes = 1

        data["scheduler"] = {
            "enabled": enabled,
            "interval_minutes": interval_minutes,
        }

        cls.save(data)

    @staticmethod
    def mask_token(token: str) -> str:
        if not token:
            return ""
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"
