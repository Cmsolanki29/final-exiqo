"""Postgres offline feature store — durable point-in-time feature snapshots.

Phase 2: Online Feature Store.
Dependencies: asyncpg, core.db.
Performance budget: snapshot() < 10ms (single INSERT), get_at_time() < 20ms.

Why an offline store alongside Redis?
  1. Redis is ephemeral — data is lost on restart unless persistence is configured.
  2. Training requires point-in-time correct features: for a transaction at T,
     we must use the feature values AS THEY WERE at T, not today's values.
     Without an offline store, every retrain would suffer label leakage.
  3. Online/offline consistency checks (Phase 5) compare live Redis values against
     these snapshots to detect serving skew.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from core.db import get_pool

logger = logging.getLogger(__name__)


class OfflineFeatureStore:
    """Async Postgres snapshot store for point-in-time feature retrieval."""

    async def snapshot(
        self,
        entity_type: str,
        entity_id: str,
        features: dict[str, Any],
        computed_at: datetime | None = None,
    ) -> None:
        """Persist a feature snapshot to Postgres.

        Called by the materialiser after every refresh cycle.  Multiple
        snapshots per entity are kept so `get_at_time` can reconstruct history.

        Args:
            entity_type:  "user" | "device" | "ip" | "merchant" | "card".
            entity_id:    String identifier.
            features:     Full feature dict at materialisation time.
            computed_at:  Timestamp of the snapshot; defaults to now(UTC).
        """
        try:
            pool = get_pool()
        except RuntimeError:
            logger.debug("offline_store_no_pool entity=%s/%s", entity_type, entity_id)
            return

        ts = computed_at or datetime.now(timezone.utc)
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO feature_snapshots (entity_type, entity_id, features, computed_at)
                    VALUES ($1, $2, $3::jsonb, $4)
                    """,
                    entity_type,
                    str(entity_id),
                    json.dumps(features, default=str),
                    ts,
                )
        except Exception as exc:
            logger.error(
                "offline_store_snapshot_failed entity=%s/%s error=%s",
                entity_type, entity_id, exc,
            )

    async def get_at_time(
        self,
        entity_type: str,
        entity_id: str,
        at_time: datetime,
    ) -> dict[str, Any] | None:
        """Retrieve the most recent snapshot of an entity before `at_time`.

        Used by the training pipeline to reconstruct point-in-time correct
        feature vectors.  Returns None if no snapshot exists before at_time.

        Args:
            entity_type:  Entity category.
            entity_id:    String identifier.
            at_time:      Upper bound on computed_at (exclusive).

        Returns:
            Feature dict or None if no snapshot found.
        """
        try:
            pool = get_pool()
        except RuntimeError:
            return None

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT features FROM feature_snapshots
                    WHERE entity_type = $1
                      AND entity_id = $2
                      AND computed_at <= $3
                    ORDER BY computed_at DESC
                    LIMIT 1
                    """,
                    entity_type,
                    str(entity_id),
                    at_time,
                )
                if row is None:
                    return None
                return json.loads(row["features"])
        except Exception as exc:
            logger.error(
                "offline_store_get_at_time_failed entity=%s/%s at=%s error=%s",
                entity_type, entity_id, at_time, exc,
            )
            return None

    async def get_latest(
        self, entity_type: str, entity_id: str
    ) -> dict[str, Any] | None:
        """Convenience wrapper — returns the most recent snapshot regardless of time."""
        return await self.get_at_time(
            entity_type, entity_id, datetime.now(timezone.utc)
        )

    async def prune_old(self, entity_type: str, keep_days: int = 90) -> int:
        """Delete snapshots older than `keep_days`.  Returns rows deleted.

        Called periodically to prevent unbounded growth of the snapshots table.
        """
        try:
            pool = get_pool()
        except RuntimeError:
            return 0
        try:
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM feature_snapshots
                    WHERE entity_type = $1
                      AND computed_at < NOW() - ($2 * INTERVAL '1 day')
                    """,
                    entity_type,
                    keep_days,
                )
                deleted = int(result.split()[-1]) if result else 0
                logger.info(
                    "offline_store_pruned entity_type=%s rows=%d", entity_type, deleted
                )
                return deleted
        except Exception as exc:
            logger.error("offline_store_prune_failed error=%s", exc)
            return 0


# Module-level singleton
offline_feature_store = OfflineFeatureStore()
