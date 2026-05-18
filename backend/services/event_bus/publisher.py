"""Event publisher — writes to Redis Streams + events table for durability.

Phase 1: Real-time event-driven scoring.
Dependencies: redis[hiredis], asyncpg, structlog.
Performance budget: publish() must complete in <5ms (Redis XADD is O(log N)).

Design decisions:
  - Redis Streams is the low-latency fanout path.
  - The Postgres events table is the durability path; consumers can replay from
    it if Redis loses data or a consumer restarts.
  - If Redis is unavailable, publish() falls back to DB-only (no exception raised
    to the caller — the transaction should succeed even without the event bus).
  - MAXLEN 10000 per stream keeps memory bounded; increase in prod.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from core.redis import get_redis

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Topic constants — use these everywhere; never raw strings.
# ------------------------------------------------------------------ #
TOPIC_TRANSACTIONS_SCORED = "transactions_scored"
TOPIC_ALERTS_CREATED = "alerts_created"
TOPIC_FEEDBACK_RECEIVED = "feedback_received"
TOPIC_MODELS_DEPLOYED = "models_deployed"

# Kept together for import convenience
ALL_TOPICS = (
    TOPIC_TRANSACTIONS_SCORED,
    TOPIC_ALERTS_CREATED,
    TOPIC_FEEDBACK_RECEIVED,
    TOPIC_MODELS_DEPLOYED,
)


class EventPublisher:
    """Publishes domain events to Redis Streams with Postgres fallback.

    Usage::

        publisher = EventPublisher()
        await publisher.publish(TOPIC_TRANSACTIONS_SCORED, {"txn_id": 42, ...})

    The class is designed as a thin wrapper so it is easy to swap the backend
    (e.g., to Kafka) in production without changing call sites.
    """

    def __init__(self, db_pool=None) -> None:
        """
        Args:
            db_pool: optional asyncpg Pool for DB-side durability writes.
                     Pass None to skip DB persistence (test / degraded mode).
        """
        self._pool = db_pool

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish an event to Redis Stream and persist to Postgres events table.

        Never raises — failures are logged as warnings so the calling
        transaction is not rolled back due to an event bus problem.

        Args:
            topic:   One of the TOPIC_* constants.
            payload: Serialisable dict; must not contain non-JSON types.
        """
        payload_json = json.dumps(payload, default=str)

        # -------- Redis Streams (low-latency fanout) -------- #
        redis = get_redis()
        if redis is not None:
            try:
                await redis.xadd(
                    topic,
                    {"payload": payload_json, "ts": datetime.now(timezone.utc).isoformat()},
                    maxlen=10_000,
                    approximate=True,
                )
            except Exception as exc:
                logger.warning(
                    "event_publish_redis_failed topic=%s error=%s", topic, exc
                )

        # -------- Postgres durability (survives Redis restart) -------- #
        if self._pool is not None:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO events (topic, payload)
                        VALUES ($1, $2::jsonb)
                        """,
                        topic,
                        payload_json,
                    )
            except Exception as exc:
                logger.warning(
                    "event_publish_db_failed topic=%s error=%s", topic, exc
                )

        logger.debug("event_published topic=%s", topic)

        # -------- No-Redis: in-process dispatch (Phase 1 / 8 fallback) -------- #
        if redis is None:
            try:
                from services.event_bus.local_bus import dispatch, setup_default_handlers

                setup_default_handlers()
                await dispatch(topic, payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "event_publish_local_dispatch_failed topic=%s error=%s",
                    topic,
                    exc,
                )

    def set_pool(self, pool) -> None:
        """Inject the asyncpg pool after the publisher is created (used in lifespan)."""
        self._pool = pool


# Module-level singleton — import and use directly.
event_publisher = EventPublisher()
