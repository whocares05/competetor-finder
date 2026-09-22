"""Idempotency tracking service"""
from typing import Optional
import json
import redis.asyncio as redis
from app.config.settings import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


class IdempotencyService:
    @staticmethod
    async def get_cached_result(key: str) -> Optional[dict]:
        """Fetch previously stored result for an idempotency key."""
        try:
            val = await redis_client.get(f"idempotency:{key}")
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    @staticmethod
    async def store_result(key: str, data: dict, ttl_seconds: int = 86400) -> None:
        """Store idempotency result in Redis for 24h."""
        try:
            await redis_client.set(f"idempotency:{key}", json.dumps(data), ex=ttl_seconds)
        except Exception:
            pass
