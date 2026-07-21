import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import get_engine_for_url

async def run():
    url = "https://www.intersport.com.tr/urun/hoka-bondi-9-erkek-siyah-kosu-ayakkabisi/1162011-bkvr/"
    engine = get_engine_for_url(url)
    
    print(f"Engine chosen: {engine.name} (use_browser: {engine.use_browser})")
    
    # We use get_product_data to simulate the exact real-world flow
    data = await engine.get_product_data(url)
    
    print(f"Price: {data['current_price']}")
    print(f"In Stock: {data['in_stock']}")
    print(f"Stock Count: {data['stock_count']}")
    
if __name__ == "__main__":
    asyncio.run(run())
