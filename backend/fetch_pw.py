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
        
        html = await page.content()
        with open("is_pw.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved is_pw.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
