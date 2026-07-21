import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import get_engine_for_url
from bs4 import BeautifulSoup

async def run():
    url = "https://www.intersport.com.tr/urun/hoka-bondi-9-erkek-siyah-kosu-ayakkabisi/1162011-bkvr/"
    engine = get_engine_for_url(url)
    
    print("Fetching with browser...")
    html = await engine.fetch_with_browser(url)
    soup = BeautifulSoup(html, "lxml")
    
    print("ALL BUTTONS:")
    for btn in soup.find_all("button"):
        print(f"Button text: {btn.text.strip()}, classes: {btn.get('class')}, id: {btn.get('id')}, disabled: {btn.has_attr('disabled')}")
        
    print("\nALL LABELS/SPANS IN PRODUCT INFO:")
    prod_info = soup.find("div", class_="product-info") or soup.find("div", class_="product-detail")
    if prod_info:
        for el in prod_info.find_all(["span", "label", "div"]):
            if el.get("class"):
                print(f"{el.name}.{'.'.join(el.get('class'))}: {el.text.strip()[:50]}")

if __name__ == "__main__":
    asyncio.run(run())
