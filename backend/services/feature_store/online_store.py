"""Redis-backed online feature store.

Phase 2: Online Feature Store.
Dependencies: redis[hiredis], core.redis.
Performance budget: get_features() < 2ms, get_multi() < 5ms for 10 entities.

Why Redis for online features?
  The scoring path needs 50+ features per transaction at <5ms. A Postgres query
  for every feature on every transaction would blow the 150ms budget. Redis
  HGETALL + pipeline gives us sub-millisecond retrieval for pre-materialised
  features.  The materialiser (runs every 15 min) keeps the store fresh.

Key format:  feat:{entity_type}:{entity_id}  →  JSON-serialised feature dict
TTL:         86400 seconds (24 hours) by default; configurable via FEATURE_TTL_SEC.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from core.config import get_settings
from core.redis import get_redis
from services.feature_store.catalog import CATALOG_BY_ENTITY, get_defaults

logger = logging.getLogger(__name__)


def _redis_key(entity_type: str, entity_id: str) -> str:
    return f"feat:{entity_type}:{entity_id}"


class OnlineFeatureStore:
    """Async Redis feature store with graceful degradation.

    All methods return default values (not errors) when Redis is unavailable or
    when an entity has not been materialised yet.  Callers never need to guard
    against None returns.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def get_features(
        self, entity_type: str, entity_id: str
    ) -> dict[str, Any]:
        """Retrieve features for one entity.  Returns defaults on miss or error.

        Args:
            entity_type: "user" | "device" | "ip" | "merchant" | "card"
            entity_id:   String identifier (e.g. str(user_id), device_id).

        Returns:
            Dict of feature_name → value with all catalog features present.
        """
        defaults = get_defaults(entity_type)
        redis = get_redis()
        if redis is None:
            return defaults

        t0 = time.perf_counter()
        try:
            key = _redis_key(entity_type, entity_id)
            raw = await redis.get(key)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "online_store_get entity=%s/%s hit=%s latency_ms=%.2f",
                entity_type, entity_id, raw is not None, elapsed_ms,
            )
            if raw is None:
                return defaults
            stored = json.loads(raw)
            return {**defaults, **stored}  # stored values override defaults
        except Exception as exc:
            logger.warning(
                "online_store_get_failed entity=%s/%s error=%s", entity_type, entity_id, exc
            )
            return defaults

    async def get_multi(
        self, requests: list[tuple[str, str]]
    ) -> dict[str, dict[str, Any]]:
        """Retrieve features for multiple entities in a single Redis pipeline.

        Uses pipelining so N entities → 1 network round-trip.

        Args:
            requests: List of (entity_type, entity_id) tuples.

        Returns:
            Dict keyed by "entity_type:entity_id" → feature dict.
        """
        result: dict[str, dict[str, Any]] = {}
        if not requests:
            return result

        # Always pre-fill with defaults so keys exist even on Redis miss
        for et, eid in requests:
            result[f"{et}:{eid}"] = get_defaults(et)

        redis = get_redis()
        if redis is None:
            return result

        t0 = time.perf_counter()
        try:
            keys = [_redis_key(et, eid) for et, eid in requests]
            pipe = redis.pipeline(transaction=False)
            for k in keys:
                pipe.get(k)
            values = await pipe.execute()

            for (et, eid), raw in zip(requests, values):
                if raw is not None:
                    stored = json.loads(raw)
                    result[f"{et}:{eid}"] = {**get_defaults(et), **stored}

            elapsed_ms = (time.perf_counter() - t0) * 1000
            hits = sum(1 for v in values if v is not None)
            logger.debug(
                "online_store_get_multi n=%d hits=%d latency_ms=%.2f",
                len(requests), hits, elapsed_ms,
            )
        except Exception as exc:
            logger.warning("online_store_get_multi_failed error=%s", exc)

        return result

    async def set_features(
        self,
        entity_type: str,
        entity_id: str,
        features: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Write features for one entity to Redis.

        Args:
            entity_type: Entity category.
            entity_id:   String identifier.
            features:    Dict of feature_name → value (must be JSON-serialisable).
            ttl:         TTL in seconds; defaults to FEATURE_TTL_SEC from config.
        """
        redis = get_redis()
        if redis is None:
            return

        effective_ttl = ttl if ttl is not None else self._settings.FEATURE_TTL_SEC
        key = _redis_key(entity_type, entity_id)
        try:
            await redis.set(key, json.dumps(features, default=str), ex=effective_ttl)
        except Exception as exc:
            logger.warning(
                "online_store_set_failed entity=%s/%s error=%s", entity_type, entity_id, exc
            )

    async def set_multi(
        self,
        items: list[tuple[str, str, dict[str, Any]]],
        ttl: int | None = None,
    ) -> None:
        """Write features for multiple entities in a single pipeline.

        Args:
            items: List of (entity_type, entity_id, features_dict).
            ttl:   TTL in seconds (same for all items in the batch).
        """
        redis = get_redis()
        if redis is None:
            return

        if not items:
            return

        effective_ttl = ttl if ttl is not None else self._settings.FEATURE_TTL_SEC
        t0 = time.perf_counter()
        try:
            pipe = redis.pipeline(transaction=False)
            for et, eid, features in items:
                key = _redis_key(et, eid)
                pipe.set(key, json.dumps(features, default=str), ex=effective_ttl)
            await pipe.execute()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.debug(
                "online_store_set_multi n=%d latency_ms=%.2f", len(items), elapsed_ms
            )
        except Exception as exc:
            logger.warning("online_store_set_multi_failed error=%s", exc)

    async def delete(self, entity_type: str, entity_id: str) -> None:
        """Remove a single entity's features (used in tests and forced refresh)."""
        redis = get_redis()
        if redis is None:
            return
        try:
            await redis.delete(_redis_key(entity_type, entity_id))
        except Exception as exc:
            logger.warning("online_store_delete_failed error=%s", exc)


# Module-level singleton
online_feature_store = OnlineFeatureStore()
