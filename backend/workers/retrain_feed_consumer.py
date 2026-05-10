"""RetrainFeedConsumer — accumulates feedback labels and triggers retraining.

Phase 8: Feedback Flywheel.
Dependencies: BaseConsumer (Phase 1), Redis (Phase 1), APScheduler (Phase 2),
              core/config.py.
Performance budget: handle() < 5ms per event (Redis INCR only).

Why a separate retrain trigger?
  Retraining is expensive (~5–30 minutes).  We don't retrain on every label —
  instead we accumulate labels in a Redis counter and retrain only when a
  meaningful batch (>100 new labels) has arrived since the last retrain.
  This mirrors how production systems handle continuous label streams: they
  batch labels into training windows rather than triggering a retrain per report.

Counter semantics:
  Redis key `retrain:pending_labels` is incremented on each FEEDBACK_RECEIVED
  event.  When the counter crosses `RETRAIN_LABEL_THRESHOLD` (default 100), the
  consumer enqueues a retrain task via `retrain_scheduler.run_now()` and resets
  the counter (GETDEL + SET 0 pattern, atomic via pipeline).

Retrain deduplication:
  A second Redis key `retrain:running` (TTL 2 hours) prevents concurrent
  retrains.  If a retrain is already in progress, the consumer logs and skips.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from core.redis import get_redis  # module-level so tests can patch

logger = logging.getLogger(__name__)

# Default: trigger retrain after this many new labels since the last one.
_DEFAULT_RETRAIN_THRESHOLD = 100
_RETRAIN_COUNTER_KEY = "retrain:pending_labels"
_RETRAIN_LOCK_KEY = "retrain:running"
_RETRAIN_LOCK_TTL_SEC = 7200  # 2 hours max for a retrain run


class RetrainFeedConsumer:
    """Consumes FEEDBACK_RECEIVED events and triggers retraining.

    Lifecycle:
      1. Instantiated at startup in main.py.
      2. start() is awaited as an asyncio background task.
      3. On each FEEDBACK_RECEIVED event:
         a. Increment `retrain:pending_labels` counter.
         b. If counter > threshold AND no retrain is running:
            → reset counter, set lock, call retrain_scheduler.run_now().
    """

    def __init__(self) -> None:
        self._threshold: int = _DEFAULT_RETRAIN_THRESHOLD
        self._running: bool = False

    async def start(self) -> None:
        """Start consuming FEEDBACK_RECEIVED events in a loop.

        Degrades gracefully: if Redis is unavailable, sleeps and retries.
        """
        from services.event_bus.publisher import TOPIC_FEEDBACK_RECEIVED as FEEDBACK_RECEIVED

        self._running = True
        logger.info("retrain_feed_consumer.started threshold=%d", self._threshold)

        stream_key = FEEDBACK_RECEIVED
        group_name = "retrain_feed_group"
        consumer_name = "retrain_feed_consumer_0"
        last_id = "0"  # read from beginning on first start

        while self._running:
            try:
                redis = get_redis()
                if redis is None:
                    await asyncio.sleep(5)
                    continue

                # Ensure consumer group exists
                try:
                    await redis.xgroup_create(stream_key, group_name, id="0", mkstream=True)
                except Exception:
                    pass  # group already exists

                # Read up to 10 events (non-blocking, poll every 5s)
                messages = await redis.xreadgroup(
                    groupname=group_name,
                    consumername=consumer_name,
                    streams={stream_key: ">"},
                    count=10,
                    block=5000,
                )

                if not messages:
                    continue

                for stream, entries in messages:
                    for msg_id, fields in entries:
                        try:
                            await self._handle(fields)
                            await redis.xack(stream_key, group_name, msg_id)
                        except Exception as exc:
                            logger.warning(
                                "retrain_feed_consumer.handle_failed msg=%s err=%s",
                                msg_id, exc,
                            )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("retrain_feed_consumer.loop_error: %s", exc)
                await asyncio.sleep(5)

        logger.info("retrain_feed_consumer.stopped")

    def stop(self) -> None:
        """Signal the consumer loop to exit."""
        self._running = False

    async def _handle(self, fields: dict[str, Any]) -> None:
        """Process one FEEDBACK_RECEIVED event.

        Increments the pending-labels counter.  If the counter crosses the
        threshold and no retrain is running, triggers out-of-band retraining.

        Args:
            fields: Event payload from Redis Streams (string key → string value).
        """
        redis = get_redis()
        if redis is None:
            return

        # Increment label counter
        new_count = await redis.incr(_RETRAIN_COUNTER_KEY)

        logger.debug(
            "retrain_feed_consumer.label_counted pending=%d threshold=%d",
            new_count, self._threshold,
        )

        if new_count < self._threshold:
            return

        # Check if a retrain is already running
        already_running = await redis.exists(_RETRAIN_LOCK_KEY)
        if already_running:
            logger.info(
                "retrain_feed_consumer: threshold crossed (%d) but retrain already running",
                new_count,
            )
            return

        # Atomically reset counter and set lock
        pipe = redis.pipeline(transaction=True)
        await pipe.set(_RETRAIN_COUNTER_KEY, 0)
        await pipe.set(_RETRAIN_LOCK_KEY, "1", ex=_RETRAIN_LOCK_TTL_SEC)
        await pipe.execute()

        logger.info(
            "retrain_feed_consumer: threshold crossed (%d/%d) — triggering retrain",
            new_count, self._threshold,
        )

        # Trigger retraining as a background task (non-blocking)
        asyncio.create_task(self._run_retrain())

    async def _run_retrain(self) -> None:
        """Background task: call retrain_scheduler.run_now() and release lock."""
        try:
            from workers.retrain_scheduler import retrain_scheduler
            logger.info("retrain_feed_consumer: starting out-of-band retrain")
            await retrain_scheduler.run_now()
            logger.info("retrain_feed_consumer: out-of-band retrain complete")
        except Exception as exc:
            logger.warning("retrain_feed_consumer: retrain failed: %s", exc)
        finally:
            try:
                _r = get_redis()
                if _r is not None:
                    await _r.delete(_RETRAIN_LOCK_KEY)
            except Exception as exc:
                logger.debug("retrain_feed_consumer: lock release failed: %s", exc)

    @classmethod
    def get_pending_label_count(cls) -> int:
        """Synchronously read the pending label counter (for admin dashboard).

        Returns 0 if Redis is unavailable.
        """
        import asyncio
        try:
            redis = get_redis()
            if redis is None:
                return 0
            # Run in event loop if available, else return 0
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return 0  # can't run sync in async context; use async version instead
            val = loop.run_until_complete(redis.get(_RETRAIN_COUNTER_KEY))
            return int(val or 0)
        except Exception:
            return 0


# Module-level singleton
retrain_feed_consumer = RetrainFeedConsumer()
