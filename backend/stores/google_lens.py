import logging
import os
import tempfile
from typing import Any

import httpx
from bs4 import BeautifulSoup

from engines import StoreEngine, parse_price_text

logger = logging.getLogger("shoehunter")


class GoogleLensEngine(StoreEngine):
    name = "Google Lens"
    slug = "google_lens"
    domains = ["google.com", "lens.google.com"]
    search_path = "https://lens.google.com/upload"
    supports_product_detail = False
    supports_cart_price = False
    discovery_method = "visual_search"

    async def search(self, query: str) -> list[dict[str, Any]]:
        return []

    async def search_image(self, image_data: bytes, content_type: str) -> list[dict[str, Any]]:
        """Return visually similar public shopping candidates from a user-supplied image."""

        upload_url = "https://lens.google.com/v3/upload?ep=ccm"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        ext = ".jpg"
        lowered_type = (content_type or "").lower()
        if "png" in lowered_type:
            ext = ".png"
        elif "webp" in lowered_type:
            ext = ".webp"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as handle:
                files = {"encoded_image": ("upload" + ext, handle, content_type or "image/jpeg")}
                async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
                    response = await client.post(
                        upload_url,
                        headers=headers,
                        files=files,
                        follow_redirects=True,
                    )
            if response.status_code >= 400:
                logger.warning("Google Lens upload failed with status %s", response.status_code)
                return []
            final_url = str(response.url)
        except Exception as exc:
            logger.warning("Google Lens upload error: %s", exc)
            return []
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        from browser_runtime import browser_pool

        try:
            html = await browser_pool.fetch(
                store_slug=self.slug,
                domains=self.domains,
                url=final_url,
                user_agent=headers["User-Agent"],
                browser_wait_selector=None,
            )
        except Exception as exc:
            logger.warning("Google Lens fetch error: %s", exc)
            raise RuntimeError(f"Google Lens sonuclari alinamadi veya erisim korumasina takildi: {exc}") from exc

        lowered_html = html[:12000].lower()
        if "captcha" in lowered_html or "unusual traffic" in lowered_html or "recaptcha" in lowered_html:
            raise RuntimeError("Google Lens erisim korumasi tespit edildi.")

        return self.parse_lens_html(html)

    def parse_lens_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html or "", "html.parser")
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for card in soup.find_all("a", href=True):
            href = card["href"]
            if not href.startswith("http") or "google.com" in href:
                continue

            image = card.find("img")
            image_url = (image.get("src") or image.get("data-src")) if image else None
            if not image_url or (image_url.startswith("data:image") and len(image_url) < 500):
                continue

            text_nodes = [text.strip() for text in card.stripped_strings if text.strip()]
            if len(text_nodes) < 2:
                continue

            title = None
            price_text = None
            store_name = None
            for text in text_nodes:
                has_price_symbol = "TL" in text.upper() or "₺" in text or "$" in text
                has_price_punctuation = ("," in text or "." in text) and any(ch.isdigit() for ch in text)
                if has_price_symbol or has_price_punctuation:
                    if not price_text and any(ch.isdigit() for ch in text):
                        price_text = text
                    continue
                if not title and len(text) > 8:
                    title = text
                elif not store_name and 2 < len(text) < 28:
                    store_name = text

            if not title or not price_text or href in seen:
                continue

            seen.add(href)
            results.append(
                {
                    "title": title,
                    "price": price_text,
                    "current_price": parse_price_text(price_text),
                    "store_name": store_name or "Satıcı",
                    "link": href,
                    "url": href,
                    "image_url": image_url,
                    "image": image_url,
                    "source": "google_lens",
                }
            )

            if len(results) >= 15:
                break

        return results
