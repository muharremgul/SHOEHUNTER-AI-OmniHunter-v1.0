import asyncio
from server import db

async def main():
    docs = await db.listings.find({"store": "Intersport"}).to_list(10)
    for d in docs:
        sizes = d.get("last_sizes")
        if sizes:
            stock_sizes = [s['name'] for s in sizes if s.get('in_stock')]
            print(f"{d.get('title')}: {len(sizes)} sizes found, in stock: {stock_sizes}")
        else:
            print(f"{d.get('title')}: NO SIZES FOUND")

if __name__ == "__main__":
    asyncio.run(main())
