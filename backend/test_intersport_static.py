import asyncio
import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engines import get_engine_for_url


async def run():
    url = "https://www.intersport.com.tr/urun/hoka-bondi-9-erkek-siyah-kosu-ayakkabisi/1162011-bkvr/"
    engine = get_engine_for_url(url)

    print("Fetching static HTML with the configured store engine...")
    html = await engine.fetch(url)

    matches = re.search(r"var\s+product\s*=\s*(\{.*?\});", html, re.DOTALL)
    if matches:
        print("Found 'product' variable!")
        data = json.loads(matches.group(1))
        print("Variants:", data.get("variants"))
        return

    matches = re.search(r"var\s+GLOBALS\s*=\s*(\{.*?\});", html, re.DOTALL)
    if matches:
        print("Found 'GLOBALS' variable!")
        print(matches.group(1)[:1500])
    else:
        print("No JS objects found :(")


if __name__ == "__main__":
    asyncio.run(run())
