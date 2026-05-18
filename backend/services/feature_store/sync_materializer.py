"""Sync (psycopg2) feature materialization when async pool / Redis are unavailable."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def materialize_user_sync(conn, user_id: int) -> dict[str, Any] | None:
    """Compute core user features from Postgres and store in memory cache."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE(AVG(amount) FILTER (
                    WHERE UPPER(type) = 'DEBIT'
                      AND transaction_date >= CURRENT_DATE - INTERVAL '30 days'
                ), 0)::float AS avg_debit_30d,
                COUNT(*) FILTER (
                    WHERE UPPER(type) = 'DEBIT'
                      AND transaction_date >= CURRENT_DATE - INTERVAL '7 days'
                )::int AS txn_count_7d,
                COUNT(DISTINCT COALESCE(merchant, description)) FILTER (
                    WHERE UPPER(type) = 'DEBIT'
                )::int AS distinct_merchants
            FROM transactions
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        features = {
            "avg_debit_30d": float(row[0] or 0),
            "txn_count_7d": int(row[1] or 0),
            "distinct_merchants": int(row[2] or 0),
        }
        from services.feature_store import memory_cache

        memory_cache.set("user", str(user_id), features)
        return features
    except Exception as exc:  # noqa: BLE001
        logger.debug("sync_materialize_user failed uid=%s: %s", user_id, exc)
        return None
    finally:
        cur.close()
