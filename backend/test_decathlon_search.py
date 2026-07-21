import asyncio
from engines import get_engine_for_url, ENGINES
from urllib.parse import quote_plus

async def main():
    engine = next(e for e in ENGINES if e.name == "Decathlon")
    search_query = "kalenji"
    print(f"Testing static search for: {engine.name}")
    try:
        results = await asyncio.wait_for(engine.search(search_query), timeout=15)
        print(f"Status: ok, {len(results)} results found.")
        for item in results:
            print(f"- {item['title']} : {item['url']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
