import asyncio; from backend.database import db; async def main(): print(await db.job_queue.update_many({'queue': {'': False}}, {'': {'queue': 'browser'}})); asyncio.run(main())  
