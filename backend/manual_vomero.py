import asyncio
import motor.motor_asyncio
from discovery_service import run_watch_discovery

async def main():
    client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
    db = client.shoehunter_ai
    w = await db.watch_queries.find_one({'id': '2292f07c-a1d1-47d0-9855-5ba196cb1b3f'})
    if not w:
        print("Watch not found")
        return
        
    print("Running discovery for watch:", w['canonical_query'])
    scope = w.get("store_scope", [])
    if "google_shopping" not in scope:
        scope.append("google_shopping")
        await db.watch_queries.update_one({'id': w['id']}, {'$set': {'store_scope': scope}})
        w['store_scope'] = scope
        
    result = await run_watch_discovery(db, w)
    print("Discovery complete. Total matching candidates:", result.get('total_matched_candidates', 0))
    
    listings = await db.store_results.find({'watch_id': w['id'], 'source': 'google_shopping'}).to_list(None)
    print(f"Found {len(listings)} GS listings in DB:")
    for l in listings:
        print(f"  {l.get('title')} - {l.get('price')} ({l.get('store_name')})")

if __name__ == '__main__':
    asyncio.run(main())
