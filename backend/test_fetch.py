import asyncio
from engines import StoreEngine

async def main():
    e = StoreEngine()
    print("Fetching...")
    html = await e.fetch("https://www.google.com")
    print(f"Success! HTML len: {len(html)}")

if __name__ == "__main__":
    asyncio.run(main())
