import re
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from engines import StoreEngine, _looks_like_bot_challenge, parse_price_text

class GoogleShoppingEngine(StoreEngine):
    name = "Google Shopping"
    slug = "google_shopping"
    domains = ["google.com", "google.com.tr"]
    search_path = "https://www.google.com/search?tbm=shop&hl=tr&q={query}"
    
    js_search = True
    use_browser = True
    search_browser_fallback = True
    supports_product_detail = False
    priority = 100

    async def search(self, query):
        from browser_runtime import browser_pool
        url = self.search_path.format(query=quote_plus(query))
        html = await browser_pool.fetch(
            store_slug=self.slug,
            domains=self.domains,
            url=url,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        if not html or _looks_like_bot_challenge(html):
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        # Google Shopping kartları genellikle class='sh-dgr__content' veya 'i0X6df' vs olur.
        # Daha genel kapsayıcıları da alıyoruz.
        cards = soup.select(".sh-dgr__content, .sh-dgr__grid-result, .i0X6df")
        for card in cards:
            title_el = card.select_one("h3, h4, .tAxDx")
            if not title_el:
                continue
            title = title_el.get_text(" ", strip=True)

            # Fiyat
            price_el = card.select_one(".a8Pemb, [data-price], .OFFNJ")
            price_text = price_el.get_text(" ", strip=True) if price_el else ""
            price = parse_price_text(price_text)
            if not price:
                continue

            # Link
            a_tag = card.find("a", href=True)
            if not a_tag:
                continue
            href = a_tag["href"]
            if href.startswith("/url?"):
                parsed_href = parse_qs(urlparse(href).query)
                if "url" in parsed_href:
                    href = parsed_href["url"][0]
            elif href.startswith("/shopping/product/"):
                href = "https://www.google.com" + href

            # Satıcı adı
            store_el = card.select_one(".aULzUe, .IuHnof, .b071Ce")
            store_name = store_el.get_text(" ", strip=True) if store_el else "Bilinmeyen Satıcı"

            # Resim
            img_el = card.find("img")
            img_url = img_el["src"] if img_el and "src" in img_el.attrs else ""

            results.append({
                "title": title,
                "price": price,
                "url": href,
                "image": img_url,
                "store_name": store_name,
                "source": "google_shopping",
                "in_stock": True,
                "stock_status": "in_stock"
            })
            
            if len(results) >= 15:
                break
                
        return results
