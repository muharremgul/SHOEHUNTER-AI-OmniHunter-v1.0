import asyncio
from server import app
from httpx import AsyncClient

async def main():
    async with AsyncClient(app=app, base_url="http://test") as client:
        print("Calling /api/search...")
        response = await client.post("/api/search", json={"query": "brooks 23", "use_ai": False})
        print("Status:", response.status_code)
        if response.status_code != 200:
            print("Response:", response.text)
        else:
            data = response.json()
            print("Total results:", data.get("total_results"))
            for s in data.get("stores", []):
                print(f"{s['store']}: {s['status']} - {len(s['results'])} results")
                if s['error']: print("  Error:", s['error'])

if __name__ == "__main__":
    asyncio.run(main())
