import asyncio; from backend.database import db; async def main(): print(await db.watch_queries.count_documents({'raw_query': {'': 'zegama', '': 'i'}})); asyncio.run(main())  
