import asyncio
from playwright.async_api import async_playwright

async def run():
    url = "https://www.intersport.com.tr/urun/hoka-bondi-9-erkek-siyah-kosu-ayakkabisi/1162011-bkvr/"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Wait for a bit to let JS render
        await page.wait_for_timeout(5000)
        
        # Scroll down a bit
        await page.mouse.wheel(0, 500)
        await page.wait_for_timeout(2000)
        
        # Take screenshot
        await page.screenshot(path="intersport_debug.png", full_page=True)
        print("Screenshot saved to intersport_debug.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
