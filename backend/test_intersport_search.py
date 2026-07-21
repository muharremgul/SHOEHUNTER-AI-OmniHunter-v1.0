import asyncio
from browser_search import rendered_search_batch
from engines import get_engine_for_url, ENGINES
from urllib.parse import quote_plus

async def main():
    engine = next(e for e in ENGINES if e.name == "Intersport")
    # Simulate adding search_path
    engine.search_path = "https://www.intersport.com.tr/list/?search_text={q}"
    engine.js_search = True

    search_query = "brooks 23"
    js_batch = [(engine, engine.search_path.format(q=quote_plus(search_query)), search_query)]
    
    print(f"Testing search for: {engine.name}")
    results = await rendered_search_batch(js_batch)
    for r in results:
        print(f"Status: {r['status']}")
        for item in r.get('results', []):
            print(f"- {item['title']} : {item['url']}")

if __name__ == "__main__":
    asyncio.run(main())
