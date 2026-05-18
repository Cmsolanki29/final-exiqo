"""In-process event bus — runs handlers when Redis Streams is unavailable.

Phase 1 fallback: scoring and uploads still publish events; without Redis
those events are dispatched synchronously here instead of via XREADGROUP.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]

_handlers: dict[str, list[Handler]] = {}
_registered = False


def register(topic: str, handler: Handler) -> None:
    """Register an async handler for a topic (multiple handlers allowed)."""
    _handlers.setdefault(topic, []).append(handler)


def is_registered() -> bool:
    return _registered


async def dispatch(topic: str, payload: dict[str, Any]) -> None:
    """Invoke all handlers for ``topic``. Never raises to callers."""
    for handler in _handlers.get(topic, []):
        try:
            await handler(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "local_bus_handler_failed topic=%s error=%s", topic, exc
            )


def setup_default_handlers() -> None:
    """Wire Phase 1 + Phase 8 consumers for no-Redis mode (idempotent)."""
    global _registered
    if _registered:
        return

    from services.event_bus.publisher import (
        TOPIC_FEEDBACK_RECEIVED,
        TOPIC_TRANSACTIONS_SCORED,
    )
    from workers.alert_consumer import alert_consumer
    from workers.retrain_feed_consumer import retrain_feed_consumer

    async def _on_scored(payload: dict[str, Any]) -> None:
        await alert_consumer.handle(payload)

    async def _on_feedback(payload: dict[str, Any]) -> None:
        await retrain_feed_consumer.handle_feedback_event(payload)

    register(TOPIC_TRANSACTIONS_SCORED, _on_scored)
    register(TOPIC_FEEDBACK_RECEIVED, _on_feedback)
    _registered = True
    logger.info("local_bus: default handlers registered (no-Redis fallback active)")
