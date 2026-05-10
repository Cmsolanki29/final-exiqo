"""Async PostgreSQL connection pool via asyncpg.

Phase 1: Real-time event-driven scoring.
Dependencies: asyncpg.
Performance budget: pool init at startup; individual acquires <1ms.

Why asyncpg alongside psycopg2?
  The existing psycopg2 code is sync and works; we keep it untouched.
  All new Phase 1+ code that is on the async request path uses asyncpg
  to avoid blocking the event loop.  The two pools are independent.
"""

from __future__ import annotations

import logging

import asyncpg

from core.config import get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Create the asyncpg connection pool.  Called once in FastAPI lifespan.

    Gracefully degrades: if Postgres is unreachable (e.g., local dev without
    Docker), the pool is not created and async DB calls will raise RuntimeError
    with a clear message rather than a cryptic NoneType error.
    """
    global _pool
    settings = get_settings()
    try:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=10,
            statement_cache_size=0,  # disable prepared-stmt cache for PgBouncer compat
        )
        logger.info("asyncpg pool initialised (max_size=20)")
    except Exception as exc:
        logger.warning(
            "asyncpg pool init failed — async DB features degraded: %s", exc
        )
        _pool = None


async def close_pool() -> None:
    """Drain and close the pool.  Called in FastAPI lifespan shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the active pool.  Raises RuntimeError if init_pool was never called
    or failed — callers must handle this for graceful degradation.
    """
    if _pool is None:
        raise RuntimeError(
            "asyncpg pool is not initialised. "
            "Check that init_pool() ran during startup and that DATABASE_URL is correct."
        )
    return _pool
