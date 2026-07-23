import asyncio, json; from backend.database import db; async def main(): print(list(await db.job_queue.find({'status': 'pending'}).to_list(10))); asyncio.run(main())  
