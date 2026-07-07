import asyncio
from curl_cffi import requests as cffi_requests
import requests
from playwright.async_api import async_playwright

TEST_URLS = {
    "Nike": "https://www.nike.com.tr/w/erkek-ayakkabilar-nik1zy7ok",
    "Puma": "https://tr.puma.com/tr/tr/pd/suede-classic-xxi-erkek-spor-ayakkabi/374915_01.html",
    "New Balance": "https://www.newbalance.com.tr/bb550ncg-bb550ncg-40618"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

async def check_playwright(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent=HEADERS["User-Agent"])
            page = await context.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            html = await page.content()
            await browser.close()
            return resp.status, len(html)
    except Exception as e:
        return "Error", str(e)

async def main():
    print("--- MAĞAZA BAĞLANTI TESTİ ---\n")
    for name, url in TEST_URLS.items():
        print(f"[{name}] Test ediliyor...")
        
        # 1. Standart Requests
        try:
            r1 = requests.get(url, headers=HEADERS, timeout=10)
            print(f"  -> requests: HTTP {r1.status_code} | Uzunluk: {len(r1.text)}")
        except Exception as e:
            print(f"  -> requests: HATA ({str(e)})")
            
        # 2. Curl_cffi (Impersonate)
        try:
            r2 = cffi_requests.get(url, impersonate="chrome110", timeout=10)
            print(f"  -> curl_cffi: HTTP {r2.status_code} | Uzunluk: {len(r2.text)}")
        except Exception as e:
            print(f"  -> curl_cffi: HATA ({str(e)})")
            
        # 3. Playwright (Headless)
        pw_status, pw_len = await check_playwright(url)
        print(f"  -> playwright: HTTP {pw_status} | Uzunluk: {pw_len}\n")

if __name__ == "__main__":
    asyncio.run(main())
