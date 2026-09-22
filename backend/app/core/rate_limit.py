"""Rate Limiting and Token Bucket Management"""
from typing import Optional
import redis.asyncio as redis
from app.config.settings import settings

# Global async Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


class TokenBucketRateLimiter:
    """Redis-backed distributed token bucket rate limiter."""

    def __init__(self, key_prefix: str, capacity: int, refill_rate_per_sec: float):
        self.key_prefix = key_prefix
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec

    async def acquire(self, identifier: str, tokens: int = 1) -> bool:
        """Attempt to acquire tokens from the bucket.
        
        Returns True if acquired, False if rate limited.
        """
        # In Stage 1, we provide a clean interface with local/redis check
        try:
            key = f"rate_limit:{self.key_prefix}:{identifier}"
            current = await redis_client.get(key)
            if current is None:
                await redis_client.set(key, self.capacity - tokens, ex=60)
                return True
            
            val = int(current)
            if val >= tokens:
                await redis_client.decrby(key, tokens)
                return True
            return False
        except Exception:
            # Degrade gracefully if Redis is temporarily unreachable
            return True


# Default instance limiters
api_rate_limiter = TokenBucketRateLimiter("api_user", capacity=60, refill_rate_per_sec=1.0)
org_rate_limiter = TokenBucketRateLimiter("api_org", capacity=120, refill_rate_per_sec=2.0)
