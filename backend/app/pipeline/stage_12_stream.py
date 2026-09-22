"""Pipeline Stage 12: SSE Event Streaming Protocol

Provides dual-mode real-time event broadcasting:
- In-memory event bus for instant zero-dependency local testing.
- Redis PubSub integration for distributed production deployments.
"""
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any, Set
from app.config.settings import settings

logger = logging.getLogger("pipeline.stage_12")

# In-memory subscriber registry for zero-setup local execution
_subscribers: Dict[str, Set[asyncio.Queue]] = {}
_subscriber_lock = asyncio.Lock()

# Lazy Redis client initialization
_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as redis
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            _redis_client = False
    return _redis_client if _redis_client is not False else None


async def emit_sse_event(search_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """Publish an SSE event to in-memory subscribers and Redis PubSub."""
    payload = {"event": event_type, "data": data}
    json_str = json.dumps(payload)

    # 1. Dispatch to all active in-memory listeners for this search job
    queues = _subscribers.get(str(search_id), set()).copy()
    for q in queues:
        try:
            q.put_nowait(payload)
        except Exception:
            pass

    # 2. Dispatch to Redis PubSub if reachable
    redis_client = get_redis_client()
    if redis_client:
        try:
            channel = f"search_events:{search_id}"
            await redis_client.publish(channel, json_str)
        except Exception:
            pass


async def sse_event_generator(search_id: str) -> AsyncGenerator[str, None]:
    """Async generator streaming SSE events to browser clients with keepalive."""
    q: asyncio.Queue = asyncio.Queue()
    sid = str(search_id)

    if sid not in _subscribers:
        _subscribers[sid] = set()
    _subscribers[sid].add(q)

    # Initial connection acknowledgment event
    yield f"event: connected\ndata: {json.dumps({'search_id': sid})}\n\n"

    try:
        while True:
            try:
                # Wait for next event or 15s keepalive timeout
                msg = await asyncio.wait_for(q.get(), timeout=15.0)
                event = msg.get("event", "message")
                data_str = json.dumps(msg.get("data", {}))
                yield f"event: {event}\ndata: {data_str}\n\n"

                if event in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Send SSE ping to prevent connection timeout
                yield ": keepalive ping\n\n"
    finally:
        if sid in _subscribers and q in _subscribers[sid]:
            _subscribers[sid].remove(q)
            if not _subscribers[sid]:
                _subscribers.pop(sid, None)
