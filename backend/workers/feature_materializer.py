"""Feature materialiser — computes and writes entity features on a schedule.

Phase 2: Online Feature Store.
Phase 6 additions:
  - Graph features pass: after the regular SQL-backed features, calls
    GraphFeatureService.compute_user_graph_features() for each user and merges
    the result into the user's feature dict in both online and offline stores.
  - MV refresh: calls GraphFeatureService.refresh_materialized_views() once per
    full materialisation cycle to keep the graph MVs fresh.

Dependencies: APScheduler (AsyncIOScheduler), asyncpg, redis (via feature stores),
              services/graph/graph_features.py (Phase 6).
Performance budget: full materialise cycle < 5 minutes for 10,000 users.
                    Graph features add ~2ms per user (MV-backed; no full scan).

How it works:
  1. Every MATERIALIZER_INTERVAL_MIN minutes (default 15):
     - Fetches all active user IDs from Postgres.
     - Processes users in batches of 500.
     - For each SQL-backed FeatureSpec, runs the aggregation query.
     - Runs the graph features pass (Phase 6).
     - Writes results to Redis (online) and Postgres (offline snapshot).
     - Refreshes graph materialized views (Phase 6).
  2. On-demand materialize_now(entity_type, entity_id) for immediate refresh
     after a transaction insert — called fire-and-forget from the route.

Design decisions:
  - APScheduler runs inside the FastAPI event loop (AsyncIOScheduler), so no
    separate thread or process is needed.
  - Each user's features are fetched in parallel (asyncio.gather) up to a
    concurrency limit to avoid overwhelming Postgres.
  - Failures for individual users are logged and skipped; the batch continues.
  - The materialiser is optional: if not started (e.g., in test), scoring
    degrades to catalog defaults, which is acceptable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from core.config import get_settings
from core.db import get_pool
from services.feature_store.catalog import CATALOG_BY_ENTITY, MATERIALISABLE
from services.feature_store.offline_store import offline_feature_store
from services.feature_store.online_store import online_feature_store

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
MAX_CONCURRENCY = 20  # parallel user queries at once


class FeatureMaterializer:
    """Schedules and executes feature materialisation for all entity types.

    Usage::

        materializer = FeatureMaterializer()
        materializer.start(scheduler)   # attach to running AsyncIOScheduler
        await materializer.materialize_now("user", "1")  # on-demand refresh
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._scheduler = None

    def start(self, scheduler) -> None:
        """Register the materialisation job with an APScheduler instance.

        Args:
            scheduler: Running apscheduler.schedulers.asyncio.AsyncIOScheduler.
        """
        interval = self._settings.MATERIALIZER_INTERVAL_MIN
        scheduler.add_job(
            self._full_materialise,
            "interval",
            minutes=interval,
            id="feature_materializer",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self._scheduler = scheduler
        logger.info(
            "feature_materializer_scheduled interval_min=%d", interval
        )

    async def materialize_now(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        """On-demand refresh for one entity or a full cycle.

        Called after each transaction insert for the affected user:
            asyncio.create_task(materializer.materialize_now("user", str(user_id)))

        When entity_type/entity_id are both provided: only that entity is updated.
        When both are None: triggers a full materialisation cycle.

        Args:
            entity_type: "user" | "merchant" | None (full cycle).
            entity_id:   String ID of the entity or None.
        """
        if entity_type is not None and entity_id is not None:
            await self._materialise_one(entity_type, entity_id)
        else:
            await self._full_materialise()

    async def _full_materialise(self) -> None:
        """Run a complete materialisation pass for all active users and merchants."""
        t0 = time.perf_counter()
        logger.info("feature_materializer_cycle_start")

        try:
            pool = get_pool()
        except RuntimeError:
            logger.warning("feature_materializer_no_pool skipping cycle")
            return

        # ---- Users ---- #
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT DISTINCT user_id FROM transactions")
            user_ids = [str(r["user_id"]) for r in rows]
        except Exception as exc:
            logger.error("feature_materializer_fetch_users_failed error=%s", exc)
            return

        users_done = 0
        errors = 0
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def _process_user(uid: str) -> None:
            nonlocal users_done, errors
            async with semaphore:
                try:
                    await self._materialise_one("user", uid)
                    users_done += 1
                except Exception as exc:
                    errors += 1
                    logger.warning(
                        "feature_materializer_user_failed user=%s error=%s", uid, exc
                    )

        for i in range(0, len(user_ids), BATCH_SIZE):
            batch = user_ids[i : i + BATCH_SIZE]
            await asyncio.gather(*[_process_user(uid) for uid in batch])

        # ---- Merchants ---- #
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT DISTINCT merchant FROM transactions WHERE merchant IS NOT NULL"
                )
            merchant_ids = [str(r["merchant"]) for r in rows]
        except Exception as exc:
            logger.error("feature_materializer_fetch_merchants_failed error=%s", exc)
            merchant_ids = []

        merchants_done = 0
        async def _process_merchant(mid: str) -> None:
            nonlocal merchants_done
            async with semaphore:
                try:
                    await self._materialise_one("merchant", mid)
                    merchants_done += 1
                except Exception as exc:
                    logger.warning(
                        "feature_materializer_merchant_failed mid=%s error=%s", mid, exc
                    )

        for i in range(0, len(merchant_ids), BATCH_SIZE):
            batch = merchant_ids[i : i + BATCH_SIZE]
            await asyncio.gather(*[_process_merchant(mid) for mid in batch])

        # ---- Phase 6: Graph features pass ---- #
        graph_done = 0
        graph_errors = 0
        try:
            from services.graph.graph_features import graph_feature_service

            async def _process_user_graph(uid: str) -> None:
                nonlocal graph_done, graph_errors
                async with semaphore:
                    try:
                        await self._materialise_graph_features(uid, graph_feature_service)
                        graph_done += 1
                    except Exception as exc:
                        graph_errors += 1
                        logger.debug(
                            "feature_materializer_graph_failed user=%s error=%s", uid, exc
                        )

            for i in range(0, len(user_ids), BATCH_SIZE):
                batch = user_ids[i : i + BATCH_SIZE]
                await asyncio.gather(*[_process_user_graph(uid) for uid in batch])

            # Refresh materialized views (Phase 6) — CONCURRENTLY, no lock
            await graph_feature_service.refresh_materialized_views()

        except ImportError:
            logger.debug("feature_materializer: graph features not available (Phase 6 not installed)")

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "feature_materializer_cycle_done users=%d merchants=%d "
            "graph=%d errors=%d graph_errors=%d latency_ms=%.0f",
            users_done, merchants_done, graph_done, errors, graph_errors, elapsed_ms,
        )

    async def _materialise_one(self, entity_type: str, entity_id: str) -> None:
        """Compute all SQL-backed features for one entity and write to both stores.

        Args:
            entity_type: "user" | "merchant" | "device" | "ip".
            entity_id:   String identifier.
        """
        try:
            pool = get_pool()
        except RuntimeError:
            return

        specs = [
            s for s in MATERIALISABLE
            if s.entity_type == entity_type and s.source_query is not None
        ]
        if not specs:
            return

        features: dict[str, Any] = {}

        async with pool.acquire() as conn:
            for spec in specs:
                try:
                    sql, params = spec.source_query(entity_id)
                    row = await conn.fetchrow(sql, *params)
                    if row is not None:
                        val = row[0]
                        # Convert to the declared dtype; fall back to default on error
                        if val is None:
                            features[spec.name] = spec.default_value
                        elif spec.dtype == bool:
                            features[spec.name] = bool(val)
                        elif spec.dtype == int:
                            features[spec.name] = int(val)
                        elif spec.dtype == float:
                            features[spec.name] = float(val)
                        else:
                            features[spec.name] = val
                    else:
                        features[spec.name] = spec.default_value
                except Exception as exc:
                    logger.debug(
                        "feature_query_failed spec=%s entity=%s/%s error=%s",
                        spec.name, entity_type, entity_id, exc,
                    )
                    features[spec.name] = spec.default_value

        if not features:
            return

        # Write to online store (Redis)
        await online_feature_store.set_features(entity_type, entity_id, features)

        # Write to offline store (Postgres) for point-in-time correctness
        await offline_feature_store.snapshot(entity_type, entity_id, features)

        logger.debug(
            "feature_materialised entity=%s/%s n_features=%d",
            entity_type, entity_id, len(features),
        )

    async def _materialise_graph_features(
        self, entity_id: str, graph_service: Any
    ) -> None:
        """Compute and persist graph features for one user (Phase 6).

        Graph features are computed by GraphFeatureService (multi-step DB queries)
        rather than single SQL in the catalog.  The results are MERGED into the
        user's existing feature dict in both online and offline stores so that
        the assembled feature vector picks them up without any assembler changes.

        Args:
            entity_id:    String user ID.
            graph_service: GraphFeatureService instance.
        """
        try:
            user_id = int(entity_id)
        except (ValueError, TypeError):
            return

        graph_feats = await graph_service.compute_user_graph_features(user_id)
        if not graph_feats:
            return

        # Merge into existing online store entry (read → merge → write)
        existing = await online_feature_store.get_features("user", entity_id)
        merged = {**existing, **graph_feats}
        await online_feature_store.set_features("user", entity_id, merged)

        # Offline: snapshot graph features separately for audit trail
        await offline_feature_store.snapshot("user", entity_id, graph_feats)

        logger.debug(
            "graph_features_materialised user=%s features=%d", entity_id, len(graph_feats)
        )


# Module-level singleton
feature_materializer = FeatureMaterializer()
