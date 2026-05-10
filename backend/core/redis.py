"""Async Redis client factory.

Phase 1: Real-time event-driven scoring.
Dependencies: redis[hiredis] >= 5.0.

Why a module-level singleton?
  Creating a Redis connection on every request adds latency; a shared client
  with connection-pool semantics keeps p99 under budget.

Graceful degradation:
  Redis is NOT required for the application to start.  If REDIS_URL is
  unreachable, the client is None and callers that check `get_redis()` must
  fall back to DB-only mode (e.g. EventPublisher skips the XADD and writes
  directly to the events table).
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from core.config import get_settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """Create and ping the Redis client.  Called once in FastAPI lifespan."""
    global _client
    settings = get_settings()
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        await client.ping()
        _client = client
        logger.info("Redis client connected to %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning(
            "Redis not available — event bus will use DB-only durability: %s", exc
        )
        _client = None


async def close_redis() -> None:
    """Close the Redis connection.  Called in FastAPI lifespan shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Redis client closed")


def get_redis() -> aioredis.Redis | None:
    """Return the Redis client, or None if Redis is unavailable.

    Callers MUST handle None and provide a degraded path — never assume Redis
    is reachable in all environments.
    """
    return _client
