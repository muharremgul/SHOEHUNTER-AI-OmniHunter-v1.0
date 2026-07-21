import asyncio
from playwright.async_api import async_playwright

async def run():
    url = "https://www.intersport.com.tr/urun/hoka-bondi-9-erkek-siyah-kosu-ayakkabisi/1162011-bkvr/"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        await page.wait_for_timeout(5000)
        
        text = await page.evaluate("document.body.innerText")
        
        with open("intersport_text.txt", "w", encoding="utf-8") as f:
            f.write(text)
            
        print("Body text saved to intersport_text.txt")
        print("Contains 'Sepete Ekle'?", "sepete ekle" in text.lower())
        print("Contains 'Sepet'?", "sepet" in text.lower())
        print("Contains 'Tükendi' or 'Stok Yok'?", "tükendi" in text.lower() or "stok yok" in text.lower() or "gelince haber ver" in text.lower())
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
