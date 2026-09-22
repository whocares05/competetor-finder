"""Scheduled Market Map Refresh Worker Process"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("refresh_worker")


async def main():
    logger.info("Market map refresh worker initialized...")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
