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
        
        # Evaluate to find element with "SEPETE EKLE"
        html = await page.evaluate('''() => {
            const elements = document.querySelectorAll('*');
            for (let el of elements) {
                if (el.children.length === 0 && el.textContent.trim().toUpperCase() === "SEPETE EKLE") {
                    return el.parentElement.outerHTML;
                }
            }
            return "Not found exact match. Trying includes...";
        }''')
        
        print(html)
        
        if "Not found" in html:
            html = await page.evaluate('''() => {
                const elements = document.querySelectorAll('*');
                for (let el of elements) {
                    if (el.children.length === 0 && el.textContent.toUpperCase().includes("SEPETE")) {
                        return el.parentElement.outerHTML;
                    }
                }
                return "Still not found.";
            }''')
            print(html)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
