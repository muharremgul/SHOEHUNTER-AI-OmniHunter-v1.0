import requests
from services.settings_service import SettingsService

class TelegramService:
    API_BASE = "https://api.telegram.org/bot{token}/{method}"

    @staticmethod
    def get_settings():
        settings = SettingsService.load()
        return settings.get("telegram", {})

    @staticmethod
    def is_configured() -> bool:
        telegram = TelegramService.get_settings()
        return bool(
            telegram.get("enabled")
            and telegram.get("bot_token")
            and telegram.get("chat_id")
        )

    @staticmethod
    def send_message(text: str) -> dict:
        telegram = TelegramService.get_settings()

        if not telegram.get("enabled"):
            return {"sent": False, "skipped": True, "reason": "telegram_disabled"}

        token = telegram.get("bot_token", "").strip()
        chat_id = telegram.get("chat_id", "").strip()

        if not token or not chat_id:
            return {"sent": False, "skipped": True, "reason": "missing_token_or_chat_id"}

        url = TelegramService.API_BASE.format(token=token, method="sendMessage")

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get("ok"):
                return {"sent": True}

            return {"sent": False, "error": str(data)}

        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    @staticmethod
    def send_test_message() -> dict:
        return TelegramService.send_message(
            "👟 <b>ShoeHunter AI</b>\nTelegram bağlantısı çalışıyor. Bot hâlâ ayakkabı kovalamaya razı, ne büyük fedakârlık."
        )

    @staticmethod
    def send_alerts(alerts) -> dict:
        if not alerts:
            return {"sent": False, "skipped": True, "reason": "no_alerts"}

        results = []

        for alert in alerts:
            product_name = alert.product.display_name if alert.product else "Ürün"
            store_name = alert.listing.store.name if alert.listing and alert.listing.store else "Mağaza"

            price_text = f"{alert.price:.2f} TL" if alert.price is not None else "-"
            target_text = f"{alert.target_price:.2f} TL" if alert.target_price is not None else "-"
            
            product_link = alert.listing.url if alert.listing and alert.listing.url else ""

            message = (
                "👟 <b>ShoeHunter AI İndirim Yakaladı!</b>\n\n"
                f"<b>Ürün:</b> {product_name}\n"
                f"<b>Mağaza:</b> {store_name}\n"
                f"<b>Güncel fiyat:</b> {price_text} 🔥\n"
                f"<b>Hedef fiyat:</b> {target_text}\n\n"
            )
            
            if product_link:
                message += f"🛒 <a href='{product_link}'>HEMEN SATIN AL (Ürüne Git)</a>\n\n"
                
            message += "Not: Bu sürüm stoktan bağımsız fiyat uyarısı gönderir."

            results.append(TelegramService.send_message(message))

        sent_count = sum(1 for item in results if item.get("sent"))

        if sent_count == len(results):
            return {"sent": True, "count": sent_count}

        first_error = next((item.get("error") for item in results if item.get("error")), None)
        first_skip = next((item.get("reason") for item in results if item.get("skipped")), None)

        if first_skip:
            return {"sent": False, "skipped": True, "reason": first_skip}

        return {"sent": False, "error": first_error or "unknown_error"}
