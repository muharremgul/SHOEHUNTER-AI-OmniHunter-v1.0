import asyncio
from curl_cffi import requests
from bs4 import BeautifulSoup

async def main():
    print("Fetching Google Shopping via curl_cffi...")
    async with requests.AsyncSession(impersonate="chrome110") as session:
        response = await session.get("https://www.google.com/search?tbm=shop&hl=tr&q=vomero+18")
        print(f"Status: {response.status_code}")
        with open("gs_vomero_curl.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(".sh-dgr__content, .sh-dgr__grid-result, .i0X6df, div[data-docid]")
        print(f"Found {len(cards)} cards.")
        if len(cards) > 0:
            print("Title 1:", cards[0].select_one("h3, h4, .tAxDx, .Xjkr3b").get_text(strip=True) if cards[0].select_one("h3, h4, .tAxDx, .Xjkr3b") else "No title")
            
if __name__ == "__main__":
    asyncio.run(main())
