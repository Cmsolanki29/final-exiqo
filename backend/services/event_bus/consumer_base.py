"""Abstract base class for Redis Streams consumers.

Phase 1: Real-time event-driven scoring.
Dependencies: redis[hiredis], asyncpg.
Performance budget: each handle() call should complete in <100ms.

Design decisions:
  - Uses Redis consumer groups (XREADGROUP) so multiple instances can run
    without double-processing.  Auto-ack on success; retry up to 3 times on
    failure; dead-letter after that.
  - The consumer loop runs as an asyncio Task (not a thread) so it shares the
    event loop with the FastAPI server.  CPU-heavy processing should be
    offloaded via asyncio.to_thread().
  - If Redis is unavailable, start() exits immediately with a warning rather
    than crashing the process.  The application degrades gracefully.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from core.redis import get_redis

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
DEAD_LETTER_PREFIX = "dlq:"
BLOCK_MS = 2_000   # XREADGROUP block timeout before re-checking stop flag


class BaseConsumer(ABC):
    """Abstract Redis Streams consumer with retry and dead-letter logic.

    Subclass this, implement handle(), and call start() inside an asyncio Task::

        task = asyncio.create_task(consumer.start())

    Subclasses must set:
        topic        (str) — stream name, one of publisher.TOPIC_* constants
        group_name   (str) — consumer group; auto-created if absent
        consumer_name (str) — unique per-process name (e.g. "alert_worker_0")
    """

    topic: str
    group_name: str
    consumer_name: str

    def __init__(self) -> None:
        self._stop = False

    async def start(self) -> None:
        """Entry point — runs the consumer loop until stop() is called.

        Handles consumer group creation, XREADGROUP polling, ack/retry/dlq.
        """
        redis = get_redis()
        if redis is None:
            logger.warning(
                "consumer_redis_unavailable consumer=%s topic=%s — consumer not started",
                self.consumer_name,
                self.topic,
            )
            return

        # Ensure consumer group exists; "$" means start from latest entry.
        try:
            await redis.xgroup_create(
                self.topic, self.group_name, id="$", mkstream=True
            )
            logger.info(
                "consumer_group_created group=%s topic=%s", self.group_name, self.topic
            )
        except Exception as exc:
            # BUSYGROUP = group already exists; anything else is a real error.
            if "BUSYGROUP" not in str(exc):
                logger.warning(
                    "consumer_group_create_error group=%s error=%s",
                    self.group_name,
                    exc,
                )

        logger.info(
            "consumer_started consumer=%s topic=%s", self.consumer_name, self.topic
        )

        while not self._stop:
            try:
                results = await redis.xreadgroup(
                    self.group_name,
                    self.consumer_name,
                    {self.topic: ">"},
                    count=10,
                    block=BLOCK_MS,
                )
                if not results:
                    continue

                for _stream, messages in results:
                    for msg_id, fields in messages:
                        await self._process_one(redis, msg_id, fields)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(
                    "consumer_loop_error consumer=%s error=%s", self.consumer_name, exc
                )
                await asyncio.sleep(1)  # brief back-off before retry

        logger.info("consumer_stopped consumer=%s", self.consumer_name)

    def stop(self) -> None:
        """Signal the consumer loop to exit on next iteration."""
        self._stop = True

    async def _process_one(self, redis, msg_id: str, fields: dict) -> None:
        """Deserialise, call handle(), ack or dead-letter."""
        raw = fields.get("payload", "{}")
        try:
            payload: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(
                "consumer_bad_json consumer=%s msg_id=%s", self.consumer_name, msg_id
            )
            await redis.xack(self.topic, self.group_name, msg_id)
            return

        attempt = 0
        last_exc: Exception | None = None
        while attempt < MAX_RETRIES:
            try:
                await self.handle(payload)
                await redis.xack(self.topic, self.group_name, msg_id)
                return
            except Exception as exc:
                attempt += 1
                last_exc = exc
                logger.warning(
                    "consumer_handle_failed consumer=%s msg_id=%s attempt=%d error=%s",
                    self.consumer_name,
                    msg_id,
                    attempt,
                    exc,
                )
                await asyncio.sleep(0.1 * attempt)  # exponential-ish back-off

        # Dead-letter after MAX_RETRIES failures
        logger.error(
            "consumer_dead_letter consumer=%s msg_id=%s error=%s",
            self.consumer_name,
            msg_id,
            last_exc,
        )
        try:
            dlq_key = f"{DEAD_LETTER_PREFIX}{self.topic}"
            await redis.xadd(
                dlq_key,
                {"original_msg_id": msg_id, "payload": raw, "error": str(last_exc)},
                maxlen=1_000,
            )
            await redis.xack(self.topic, self.group_name, msg_id)
        except Exception as dlq_exc:
            logger.error("consumer_dlq_write_failed error=%s", dlq_exc)

    @abstractmethod
    async def handle(self, payload: dict[str, Any]) -> None:
        """Process a single decoded event payload.

        Implement this in your subclass.  Raise an exception to trigger retry.
        """
