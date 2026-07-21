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
        
        # Get all pz-button elements
        html = await page.evaluate('''() => {
            const elements = document.querySelectorAll('pz-button');
            let res = [];
            for (let el of elements) {
                res.push(el.outerHTML);
            }
            return res;
        }''')
        
        print(f"Found {len(html)} pz-buttons")
        for tag in html:
            print(tag[:200])
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
