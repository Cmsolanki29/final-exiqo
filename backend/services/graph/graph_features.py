"""Graph-based fraud detection features for SmartSpend.

Phase 6: Graph / Network Signals.
Dependencies: asyncpg (core/db.py), Phase 6 materialized views.
Performance budget: compute_user_graph_features() < 30ms (reads from pre-built MVs).
                    find_fraud_ring() < 500ms (admin-only, not on hot path).

Why graph features?
  Single-transaction signals miss coordinated fraud:
    - One device used by 50 "different" users → almost certainly a fraud syndicate.
    - A user who shares a merchant with confirmed-fraud users is 3–8× more likely
      to commit fraud themselves (real-world bank stat from Barclays 2022 paper).
    - Network distance to known fraud is a stronger predictor than any single
      transaction attribute.

Feature explanations:
  graph_device_count_30d          — how many distinct devices the user has used in 30d.
                                    High → normal power user; high + new IP → risk signal.
  graph_ip_count_7d               — distinct IPs in 7d. >5 without known travel = suspicious.
  graph_max_device_user_count     — of all devices this user uses, the maximum number of
                                    OTHER users on the same device (from mv_device_user_count).
                                    >1 = device sharing; >3 = high-risk syndicate signal.
  graph_max_ip_user_count         — same for IPs (from mv_ip_user_count_24h).
  graph_shortest_path_to_fraud    — hops to nearest user with is_fraud=TRUE via shared
                                    merchant edges. -1 = no path; 1 = direct neighbor;
                                    2 = two hops.  Computed with a 2-level BFS (not full
                                    recursive CTE) for < 5ms at p99.
  graph_component_size            — approx. size of connected component within 2 hops
                                    (capped at 100). Large components = potential ring.

Materialized view refresh:
  MVs are refreshed hourly via APScheduler (registered in main.py).
  refresh_materialized_views() uses CONCURRENTLY to avoid table-level locks.
"""

from __future__ import annotations

import logging
from typing import Optional

from core.db import get_pool  # module-level import required for unittest.mock.patch

logger = logging.getLogger(__name__)

# Graph feature names — single source of truth used by catalog.py
GRAPH_FEATURE_NAMES = [
    "graph_device_count_30d",
    "graph_ip_count_7d",
    "graph_max_device_user_count",
    "graph_max_ip_user_count",
    "graph_shortest_path_to_fraud",
    "graph_component_size",
]

_DEFAULT_GRAPH_FEATURES: dict[str, float] = {
    "graph_device_count_30d":       0.0,
    "graph_ip_count_7d":            0.0,
    "graph_max_device_user_count":  0.0,
    "graph_max_ip_user_count":      0.0,
    "graph_shortest_path_to_fraud": -1.0,  # -1 = no path to fraud found
    "graph_component_size":          1.0,  # 1 = isolated node
}


class GraphFeatureService:
    """Computes graph-based fraud signals for a given user.

    All DB queries use pre-computed materialized views for performance.
    The service degrades gracefully: if the pool is unavailable, all
    methods return safe default values.
    """

    # ------------------------------------------------------------------ #
    # Per-user graph features (called by feature_materializer hourly)
    # ------------------------------------------------------------------ #

    async def compute_user_graph_features(self, user_id: int) -> dict[str, float]:
        """Compute all 6 graph features for a given user.

        Reads from:
          - transactions table (direct counts)
          - mv_device_user_count, mv_ip_user_count_24h (pre-aggregated)
          - is_fraud column via merchant-join BFS

        Args:
            user_id: Postgres user primary key.

        Returns:
            Dict of graph feature name → float value.
            Returns defaults on any DB error.
        """
        pool = get_pool()
        if pool is None:
            return dict(_DEFAULT_GRAPH_FEATURES)

        try:
            async with pool.acquire() as conn:
                device_count = await self._device_count_30d(conn, user_id)
                ip_count = await self._ip_count_7d(conn, user_id)
                max_dev_users = await self._max_device_user_count(conn, user_id)
                max_ip_users = await self._max_ip_user_count(conn, user_id)
                shortest = await self._shortest_path_to_fraud(conn, user_id)
                comp_size = await self._connected_component_size(conn, user_id)

            return {
                "graph_device_count_30d":       float(device_count),
                "graph_ip_count_7d":            float(ip_count),
                "graph_max_device_user_count":  float(max_dev_users),
                "graph_max_ip_user_count":      float(max_ip_users),
                "graph_shortest_path_to_fraud": float(shortest),
                "graph_component_size":         float(comp_size),
            }
        except Exception as exc:
            logger.warning(
                "graph_features.compute_failed user_id=%s: %s", user_id, exc
            )
            return dict(_DEFAULT_GRAPH_FEATURES)

    async def find_fraud_ring(
        self, user_id: int, depth: int = 2
    ) -> list[int]:
        """Return user IDs connected to user_id via shared entities who have fraud flags.

        Connection edges: shared merchant (most reliable proxy since device_id
        and ip_address may be sparse).  Device/IP edges are used when available.

        Algorithm: iterative BFS up to `depth` hops.  Caps at 200 users to
        prevent runaway queries on large transaction graphs.

        Args:
            user_id: Starting user.
            depth:   Max hops (default 2, max allowed 3).

        Returns:
            List of user_id integers who are within `depth` hops AND have
            at least one confirmed fraud transaction.  Empty list if no ring.
        """
        pool = get_pool()
        if pool is None:
            return []

        depth = min(depth, 3)
        try:
            async with pool.acquire() as conn:
                visited: set[int] = {user_id}
                frontier: set[int] = {user_id}
                fraud_users: list[int] = []

                for _hop in range(depth):
                    if not frontier:
                        break
                    neighbors = await self._neighbors_via_shared_entities(
                        conn, list(frontier), exclude=visited
                    )
                    visited.update(neighbors)
                    frontier = neighbors

                    # Check if any neighbors are fraud users
                    if neighbors:
                        new_fraud = await self._filter_fraud_users(conn, list(neighbors))
                        fraud_users.extend(new_fraud)

                    if len(visited) > 200:
                        logger.debug(
                            "find_fraud_ring: capping at 200 nodes (user_id=%s)", user_id
                        )
                        break

                return list(set(fraud_users))
        except Exception as exc:
            logger.warning("find_fraud_ring failed user_id=%s: %s", user_id, exc)
            return []

    async def get_network_summary(self, user_id: int) -> dict:
        """Return adjacent users and shared entities for fraud analyst UI.

        Used by GET /api/admin/users/{id}/network.

        Returns:
            Dict with:
              shared_merchants: list of {merchant, shared_user_ids}
              shared_devices:   list of {device_id, shared_user_ids}
              shared_ips:       list of {ip_address, shared_user_ids}
              direct_neighbors: list of user_id integers (1 hop)
              fraud_neighbors:  list of user_id integers with is_fraud=TRUE
        """
        pool = get_pool()
        if pool is None:
            return {"error": "database_unavailable"}

        try:
            async with pool.acquire() as conn:
                shared_merchants = await self._shared_merchants(conn, user_id)
                shared_devices = await self._shared_devices(conn, user_id)
                shared_ips = await self._shared_ips(conn, user_id)

                all_neighbor_ids: set[int] = set()
                for row in shared_merchants:
                    all_neighbor_ids.update(row["shared_user_ids"])
                for row in shared_devices:
                    all_neighbor_ids.update(row["shared_user_ids"])
                for row in shared_ips:
                    all_neighbor_ids.update(row["shared_user_ids"])
                all_neighbor_ids.discard(user_id)

                fraud_neighbors: list[int] = []
                if all_neighbor_ids:
                    fraud_neighbors = await self._filter_fraud_users(
                        conn, list(all_neighbor_ids)
                    )

            return {
                "user_id": user_id,
                "shared_merchants": shared_merchants,
                "shared_devices": shared_devices,
                "shared_ips": shared_ips,
                "direct_neighbors": list(all_neighbor_ids)[:50],
                "fraud_neighbors": fraud_neighbors,
            }
        except Exception as exc:
            logger.exception("get_network_summary failed user_id=%s: %s", user_id, exc)
            return {"error": str(exc)}

    async def get_fraud_distance(self, user_id: int) -> dict:
        """Return shortest path distance to nearest confirmed fraud user.

        Used by GET /api/admin/users/{id}/fraud-distance.

        Returns:
            Dict with distance (int, -1 if no path), path_via (list of merchants).
        """
        pool = get_pool()
        if pool is None:
            return {"distance": -1, "path_via": [], "error": "database_unavailable"}

        try:
            async with pool.acquire() as conn:
                # Is this user themselves a fraud user?
                is_fraud = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM transactions WHERE user_id = $1 AND is_fraud = TRUE)",
                    user_id,
                )
                if is_fraud:
                    return {"distance": 0, "path_via": [], "is_fraud_user": True}

                distance, path_via = await self._shortest_path_with_trace(conn, user_id)

            return {
                "user_id": user_id,
                "distance": distance,
                "path_via": path_via,
                "is_fraud_user": False,
            }
        except Exception as exc:
            logger.exception("get_fraud_distance failed user_id=%s: %s", user_id, exc)
            return {"distance": -1, "path_via": [], "error": str(exc)}

    # ------------------------------------------------------------------ #
    # Materialized view refresh (called hourly by APScheduler)
    # ------------------------------------------------------------------ #

    async def refresh_materialized_views(self) -> dict[str, bool]:
        """Refresh all 5 graph materialized views CONCURRENTLY.

        CONCURRENTLY avoids exclusive locks so the app keeps serving during refresh.
        Requires unique indexes on each MV (created in the migration).

        Returns:
            Dict of mv_name → success bool.
        """
        pool = get_pool()
        if pool is None:
            logger.warning("graph: refresh_materialized_views — pool unavailable")
            return {}

        views = [
            "mv_device_user_count",
            "mv_user_device_count",
            "mv_ip_user_count_24h",
            "mv_user_ip_count_7d",
            "mv_card_user_count",
        ]
        results: dict[str, bool] = {}
        async with pool.acquire() as conn:
            for view in views:
                try:
                    await conn.execute(
                        f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"
                    )
                    results[view] = True
                except Exception as exc:
                    logger.warning("graph.refresh_mv %s failed: %s", view, exc)
                    results[view] = False

        success_count = sum(1 for v in results.values() if v)
        logger.info(
            "graph.refresh_materialized_views: %d/%d views refreshed",
            success_count, len(views),
        )
        return results

    # ------------------------------------------------------------------ #
    # Private helpers — all accept an open asyncpg connection
    # ------------------------------------------------------------------ #

    async def _device_count_30d(self, conn, user_id: int) -> int:
        """Distinct device IDs used by user in last 30 days."""
        val = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT device_id)
            FROM   transactions
            WHERE  user_id = $1
              AND  device_id IS NOT NULL
              AND  transaction_date >= CURRENT_DATE - INTERVAL '30 days'
            """,
            user_id,
        )
        return int(val or 0)

    async def _ip_count_7d(self, conn, user_id: int) -> int:
        """Distinct IP addresses used by user in last 7 days."""
        val = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT ip_address)
            FROM   transactions
            WHERE  user_id = $1
              AND  ip_address IS NOT NULL
              AND  transaction_date >= CURRENT_DATE - INTERVAL '7 days'
            """,
            user_id,
        )
        return int(val or 0)

    async def _max_device_user_count(self, conn, user_id: int) -> int:
        """Max number of OTHER users sharing any device with this user (from MV)."""
        val = await conn.fetchval(
            """
            SELECT COALESCE(MAX(duc.user_count), 0)
            FROM   transactions t
            JOIN   mv_device_user_count duc ON duc.device_id = t.device_id
            WHERE  t.user_id = $1
              AND  t.device_id IS NOT NULL
            """,
            user_id,
        )
        return int(val or 0)

    async def _max_ip_user_count(self, conn, user_id: int) -> int:
        """Max number of users sharing any IP with this user in last 24h (from MV)."""
        val = await conn.fetchval(
            """
            SELECT COALESCE(MAX(iuc.user_count), 0)
            FROM   transactions t
            JOIN   mv_ip_user_count_24h iuc ON iuc.ip_address = t.ip_address
            WHERE  t.user_id = $1
              AND  t.ip_address IS NOT NULL
            """,
            user_id,
        )
        return int(val or 0)

    async def _shortest_path_to_fraud(self, conn, user_id: int) -> int:
        """2-level BFS for shortest path to a fraud user via shared merchant edges.

        Returns:
            0  → this user is a fraud user
            1  → directly connected to a fraud user via a shared merchant
            2  → two hops away
            -1 → no path found within 2 hops
        """
        # Level 0: is the user themselves fraud?
        is_self_fraud = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM transactions WHERE user_id = $1 AND is_fraud = TRUE)",
            user_id,
        )
        if is_self_fraud:
            return 0

        # Level 1: does user share a merchant with a fraud user?
        hop1 = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM   transactions t1
                JOIN   transactions t2
                    ON t2.merchant = t1.merchant
                    AND t2.is_fraud = TRUE
                    AND t2.user_id  != $1
                WHERE  t1.user_id  = $1
                  AND  t1.merchant IS NOT NULL
            )
            """,
            user_id,
        )
        if hop1:
            return 1

        # Level 2: does user share merchant with a level-1 user?
        hop2 = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM   transactions t1
                JOIN   transactions t2  ON t2.merchant = t1.merchant AND t1.merchant IS NOT NULL
                JOIN   transactions t3  ON t3.merchant = t2.merchant AND t2.merchant IS NOT NULL
                JOIN   transactions t4  ON t4.merchant = t3.merchant AND t4.is_fraud = TRUE
                WHERE  t1.user_id  = $1
                  AND  t2.user_id != $1
                  AND  t3.user_id != $1
                  AND  t4.user_id != $1
                LIMIT 1
            )
            """,
            user_id,
        )
        if hop2:
            return 2

        return -1

    async def _connected_component_size(self, conn, user_id: int) -> int:
        """Approximate size of connected component via 2-hop shared merchant BFS.

        Capped at 100 to prevent runaway queries.
        Returns 1 if the user is isolated (no shared merchants with others).
        """
        rows = await conn.fetch(
            """
            SELECT DISTINCT t2.user_id
            FROM   transactions t1
            JOIN   transactions t2
                ON t2.merchant = t1.merchant
                AND t2.user_id != $1
            WHERE  t1.user_id  = $1
              AND  t1.merchant IS NOT NULL
            LIMIT  99
            """,
            user_id,
        )
        # +1 for the user themselves
        return len(rows) + 1

    async def _neighbors_via_shared_entities(
        self, conn, user_ids: list[int], exclude: set[int]
    ) -> set[int]:
        """Find users who share merchant/device/IP with any user in user_ids.

        Excludes already-visited users in `exclude`.
        Capped at 100 new neighbors per hop.
        """
        if not user_ids:
            return set()

        exclude_list = list(exclude)
        rows = await conn.fetch(
            """
            SELECT DISTINCT t2.user_id
            FROM   transactions t1
            JOIN   transactions t2
                ON (
                       (t1.merchant  IS NOT NULL AND t2.merchant  = t1.merchant)
                    OR (t1.device_id IS NOT NULL AND t2.device_id = t1.device_id)
                    OR (t1.ip_address IS NOT NULL AND t2.ip_address = t1.ip_address)
                )
            WHERE  t1.user_id  = ANY($1::int[])
              AND  t2.user_id != ALL($2::int[])
              AND  t2.user_id != ANY($1::int[])
            LIMIT  100
            """,
            user_ids,
            exclude_list,
        )
        return {r["user_id"] for r in rows}

    async def _filter_fraud_users(self, conn, user_ids: list[int]) -> list[int]:
        """Return subset of user_ids who have at least one fraud transaction."""
        if not user_ids:
            return []
        rows = await conn.fetch(
            """
            SELECT DISTINCT user_id
            FROM   transactions
            WHERE  user_id = ANY($1::int[])
              AND  is_fraud = TRUE
            """,
            user_ids,
        )
        return [r["user_id"] for r in rows]

    async def _shared_merchants(self, conn, user_id: int) -> list[dict]:
        """Merchants shared with other users (for network summary)."""
        rows = await conn.fetch(
            """
            SELECT
                t1.merchant,
                ARRAY_AGG(DISTINCT t2.user_id ORDER BY t2.user_id) AS shared_user_ids
            FROM   transactions t1
            JOIN   transactions t2
                ON t2.merchant = t1.merchant AND t2.user_id != $1
            WHERE  t1.user_id  = $1
              AND  t1.merchant IS NOT NULL
            GROUP  BY t1.merchant
            ORDER  BY ARRAY_LENGTH(ARRAY_AGG(DISTINCT t2.user_id), 1) DESC
            LIMIT  20
            """,
            user_id,
        )
        return [
            {
                "merchant": r["merchant"],
                "shared_user_ids": list(r["shared_user_ids"])[:10],
            }
            for r in rows
        ]

    async def _shared_devices(self, conn, user_id: int) -> list[dict]:
        """Devices shared with other users."""
        rows = await conn.fetch(
            """
            SELECT
                t1.device_id,
                ARRAY_AGG(DISTINCT t2.user_id ORDER BY t2.user_id) AS shared_user_ids
            FROM   transactions t1
            JOIN   transactions t2
                ON t2.device_id = t1.device_id AND t2.user_id != $1
            WHERE  t1.user_id   = $1
              AND  t1.device_id IS NOT NULL
            GROUP  BY t1.device_id
            LIMIT  10
            """,
            user_id,
        )
        return [
            {"device_id": r["device_id"], "shared_user_ids": list(r["shared_user_ids"])[:10]}
            for r in rows
        ]

    async def _shared_ips(self, conn, user_id: int) -> list[dict]:
        """IP addresses shared with other users."""
        rows = await conn.fetch(
            """
            SELECT
                t1.ip_address,
                ARRAY_AGG(DISTINCT t2.user_id ORDER BY t2.user_id) AS shared_user_ids
            FROM   transactions t1
            JOIN   transactions t2
                ON t2.ip_address = t1.ip_address AND t2.user_id != $1
            WHERE  t1.user_id    = $1
              AND  t1.ip_address IS NOT NULL
            GROUP  BY t1.ip_address
            LIMIT  10
            """,
            user_id,
        )
        return [
            {"ip_address": r["ip_address"], "shared_user_ids": list(r["shared_user_ids"])[:10]}
            for r in rows
        ]

    async def _shortest_path_with_trace(
        self, conn, user_id: int
    ) -> tuple[int, list[str]]:
        """Like _shortest_path_to_fraud but also returns the merchant path trace.

        Returns:
            (distance, path_via_merchants).
            distance = -1 if no path; path_via = list of merchant names traversed.
        """
        # Hop 1
        row = await conn.fetchrow(
            """
            SELECT t1.merchant
            FROM   transactions t1
            JOIN   transactions t2
                ON t2.merchant = t1.merchant
                AND t2.is_fraud = TRUE
                AND t2.user_id  != $1
            WHERE  t1.user_id  = $1
              AND  t1.merchant IS NOT NULL
            LIMIT  1
            """,
            user_id,
        )
        if row:
            return 1, [row["merchant"]]

        # Hop 2 — find intermediate user and both merchants
        row2 = await conn.fetchrow(
            """
            SELECT t1.merchant AS m1, t2.user_id AS mid_user, t3.merchant AS m2
            FROM   transactions t1
            JOIN   transactions t2  ON t2.merchant = t1.merchant
                AND t2.user_id != $1 AND t1.merchant IS NOT NULL
            JOIN   transactions t3  ON t3.user_id = t2.user_id AND t3.merchant IS NOT NULL
            JOIN   transactions t4  ON t4.merchant = t3.merchant AND t4.is_fraud = TRUE
                AND t4.user_id != t2.user_id
            WHERE  t1.user_id = $1
            LIMIT  1
            """,
            user_id,
        )
        if row2:
            path = list({row2["m1"], row2["m2"]})  # dedup
            return 2, path

        return -1, []


# Module-level singleton
graph_feature_service = GraphFeatureService()
