"""Search Execution Worker Process

Pulls queued search tasks from DB, executes stages 1-13 via Pipeline Runner,
settles credits, and emits SSE events.
"""
import asyncio
import logging
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.search import Search
from app.pipeline.runner import run_search_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("search_worker")


async def poll_and_process_jobs():
    """Poll database for queued search jobs and execute them."""
    logger.info("Search worker initialized and polling for jobs...")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                query = select(Search).where(Search.status == "queued").limit(5)
                res = await db.execute(query)
                queued_searches = res.scalars().all()
                
                for s in queued_searches:
                    logger.info(f"Worker picked up queued search: {s.id} ({s.query})")
                    # Run in background or await sequentially
                    await run_search_pipeline(s.id)
        except Exception as e:
            logger.error(f"Worker polling error: {e}")

        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(poll_and_process_jobs())
