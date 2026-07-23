import logging
from typing import Any
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from engines import StoreEngine, parse_price_text

logger = logging.getLogger("shoehunter")


class GoogleShoppingEngine(StoreEngine):
    name = "Google Shopping"
    slug = "google_shopping"
    domains = ["google.com", "google.com.tr"]
    search_path = "https://www.google.com/search?tbm=shop&hl=tr&q={q}"
    js_search = True
    supports_product_detail = False
    supports_cart_price = False
    discovery_method = "shopping_search"
    priority = 100

    async def search(self, query: str) -> list[dict[str, Any]]:
        url = self.search_path.format(q=quote_plus(query))
        from browser_runtime import browser_pool

        try:
            html = await browser_pool.fetch(
                store_slug=self.slug,
                domains=self.domains,
                url=url,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                browser_wait_selector=None,
            )
        except Exception as exc:
            logger.warning("Google Shopping fetch error: %s", exc)
            return []

        return self.parse_shopping_html(html, url)

    def parse_shopping_html(self, html: str, base_url: str = "https://www.google.com/") -> list[dict[str, Any]]:
        soup = BeautifulSoup(html or "", "html.parser")
        cards = soup.select(".sh-dgr__content, .sh-dgr__grid-result, .i0X6df, [data-docid]")
        if not cards:
            cards = soup.select("a[href*='/shopping/product/']")
        if not cards:
            cards = [
                link
                for link in soup.find_all("a", href=True)
                if link.find("img") and any(ch.isdigit() for ch in link.get_text(" ", strip=True))
            ]

        seen: set[str] = set()
        results: list[dict[str, Any]] = []

        for card in cards:
            text_nodes = [text.strip() for text in card.stripped_strings if text.strip()]
            if len(text_nodes) < 2:
                continue

            image = card.find("img")
            image_url = (image.get("src") or image.get("data-src")) if image else None
            href = card.get("href")
            if not href:
                link = card.find("a", href=True)
                href = link["href"] if link else None
            if not href or not image_url:
                continue

            href = urljoin(base_url, href)
            if href in seen:
                continue

            title = None
            price_text = None
            store_name = None
            for text in text_nodes:
                price = parse_price_text(text)
                has_price_symbol = "TL" in text.upper() or "₺" in text or "$" in text
                # Product codes such as JR5220 are numeric-looking but are not prices.
                if price and has_price_symbol:
                    price_text = text
                    continue
                if not title and len(text) > 8:
                    title = text
                elif not store_name and 2 < len(text) < 32:
                    store_name = text

            current_price = parse_price_text(price_text)
            if not title or not current_price:
                continue

            seen.add(href)
            results.append(
                {
                    "title": title[:180],
                    "url": href,
                    "link": href,
                    "score": 60,
                    "image": image_url,
                    "image_url": image_url,
                    "price": current_price,
                    "current_price": current_price,
                    "price_text": price_text,
                    "store": self.name,
                    "store_slug": self.slug,
                    "store_name": store_name or "Google Alışveriş",
                    "source": "google_shopping",
                }
            )

            if len(results) >= 15:
                break

        return results
